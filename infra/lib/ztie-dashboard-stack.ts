import * as path from "path";
import {
  Stack,
  StackProps,
  RemovalPolicy,
  CfnOutput,
  Annotations,
  Duration,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";

/**
 * ZTIE Story 4.3 (RD-043) — the real-time dashboard RENDER + its AWS-native hosting.
 *
 * This stack deploys into the **Hub** account (Pipeline-Hub, 641628980935) — the
 * brains / control plane, where the dashboard, the durable tracking record, and the
 * Phase-4 read/transform Lambdas (4.1 status, 4.2 dashboard payload) live. It is the
 * PRESENTATION layer over the Story 4.2 dashboard JSON payload (`dashboard.contract.v1`);
 * it renders that payload and does NOTHING else:
 *
 *   Browser (dark-theme SPA)  --HTTPS-->  CloudFront (OAC)  -->  S3 (private static assets)
 *        |
 *        +--HTTPS (IAM/SigV4)-->  API Gateway REST  --proxy-->  hub_dashboard Lambda (4.2, UNCHANGED)
 *              GET /dashboard            (view=fleet)              READ-only DynamoDB
 *              GET /status/{intake_id}   (view=intake)
 *
 * RD-043 CONTRACT-FIRST decision: 4.3 is RENDER ONLY. It re-derives NOTHING, makes NO
 * model call, and enforces NOTHING (the human accept/reject ACTION + routing is
 * 4.4/4.6/4.7). It reuses the EXISTING Story 4.2 `hub_dashboard` orchestrator Lambda
 * completely unchanged — this stack merely stands up the GET API front that 4.2
 * deferred (the 4.2 handler already accepts the API-Gateway
 * `pathParameters`/`queryStringParameters` shape, so NO handler change is needed) and a
 * static single-page dashboard that consumes the payload. The 4.2 Lambda is referenced
 * by ARN (passed via context), so this stack does NOT modify `ZtieHubTrackingStack`.
 *
 * Design invariants carried through to the render (RD-009 / RD-013 / RD-040 / RD-028):
 *   * RENDER ONLY — the browser consumes the DERIVED `dashboard.contract.v1` payload; it
 *     never sees the raw artifact / findings text / raw trace (which never leave
 *     Forensic) and never crosses the RD-013 gate. The client escapes every derived
 *     value it renders (textContent / explicit escaping) so there is no stored XSS in
 *     the brains.
 *   * ADVISORY, NEVER ACTED UPON (RD-040) — the render surfaces the 3.5
 *     `recommended_verdict` + the explicit `advisory: true` flag alongside
 *     `decision: pending`. The APPROVE/REJECT buttons are a SURFACE only; they wire to
 *     no action here (the action is Story 4.4). The render never presents the
 *     recommendation as an effective decision.
 *   * TENANT-AWARE (RD-028) — per-SUBSCRIBER, org-shared (no per-user filtering). The
 *     render carries a `subscriber_id` on its reads so a later T.2/T.3 per-subscriber
 *     partitioning needs no render retrofit, even while ZTIE runs single-tenant
 *     ("tenant zero").
 *   * AWS-NATIVE — S3 + CloudFront + API Gateway + the existing Lambda. No external
 *     providers for hosting or operations. ServiceNow is OUT OF SCOPE.
 */

const HUB_ACCOUNT_ID = "641628980935";

export interface ZtieDashboardStackProps extends StackProps {
  /**
   * ARN of the EXISTING Story 4.2 `hub_dashboard` orchestrator Lambda (the
   * `DashboardOrchestrator` function in `ZtieHubTrackingStack`, whose name is the
   * `DashboardOrchestratorName` output). REQUIRED: the GET API front proxies to it.
   * Passed via context (`dashboardFunctionArn`) captured from the Hub stack output, so
   * this stack references the 4.2 Lambda without modifying the Hub stack.
   */
  readonly dashboardFunctionArn: string;
  /**
   * The single subscriber id this dashboard is scoped to (RD-028: per-subscriber,
   * org-shared). Defaults to the single shared Forensic account acting as "tenant
   * zero". Surfaced to the client as a build-time config so every read is
   * subscriber-scoped from day one (the read path does not yet partition by it while
   * ZTIE runs single-tenant, but the wiring is present so T.2/T.3 need no render change).
   */
  readonly subscriberId?: string;
}

export class ZtieDashboardStack extends Stack {
  /** CloudFront domain the operator loads the dashboard from. */
  public readonly dashboardUrl: string;
  /** Invoke URL of the read API the dashboard calls (IAM/SigV4). */
  public readonly dashboardApiUrl: string;

  constructor(scope: Construct, id: string, props: ZtieDashboardStackProps) {
    super(scope, id, props);

    // Guard: this is the control plane. Warn loudly if it is not the Hub account.
    if (props.env?.account && props.env.account !== HUB_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE dashboard render is intended for the Hub account ${HUB_ACCOUNT_ID} ` +
          `(brains / control plane, RD-008); deploying into ${props.env.account}. ` +
          `The dashboard + its read API live in the Hub with the tracking record and ` +
          `the 4.2 payload orchestrator. Confirm this is intentional.`,
      );
    }

    const subscriberId = props.subscriberId ?? "ztie-tenant-zero";

    // Reference the EXISTING Story 4.2 dashboard-payload orchestrator Lambda. We do NOT
    // recreate or modify it (RD-043 blast-radius: 4.3 renders 4.2's payload, it does not
    // touch the 4.2 Lambda). The GET API front proxies to it unchanged.
    const dashboardFn = lambda.Function.fromFunctionArn(
      this,
      "ImportedDashboardOrchestrator",
      props.dashboardFunctionArn,
    );

    // --- S3: private bucket holding the static dashboard assets --------------
    // Not a public website bucket: access is ONLY via CloudFront with Origin Access
    // Control (OAC). Block all public access; encrypted; enforce SSL.
    const siteBucket = new s3.Bucket(this, "DashboardSiteBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // --- CloudFront: the HTTPS front for the static SPA (OAC to S3) ----------
    // A single-page app: everything routes to index.html; HTTPS enforced; the private
    // S3 origin is reachable only through this distribution via OAC.
    const distribution = new cloudfront.Distribution(this, "DashboardCdn", {
      comment:
        "ZTIE Story 4.3 real-time dashboard (dark theme) — static SPA over the 4.2 payload.",
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      // SPA: serve index.html for any 403/404 so client-side routing works.
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: Duration.seconds(0),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });
    this.dashboardUrl = `https://${distribution.distributionDomainName}/`;

    // --- API Gateway: the READ API the dashboard calls (IAM/SigV4 auth) ------
    // Two GET endpoints fronting the UNCHANGED 4.2 Lambda via a NON-PROXY (custom)
    // integration (see below): a request template maps the HTTP request into the direct-
    // invoke event the handler expects, and an integration response passes the Lambda's
    // JSON through:
    //   GET /dashboard              -> {view: fleet}  (optional ?limit=, ?subscriber_id=)
    //   GET /status/{intake_id}     -> {view: intake, intake_id}  (optional ?subscriber_id=)
    // IAM auth (SigV4) — the same zero-trust posture as the intake API. A browser
    // console with Cognito user-pool auth is a deferred follow-on; the live validation
    // drives these endpoints via awscurl (SigV4) exactly like the intake API.
    const api = new apigateway.RestApi(this, "DashboardApi", {
      restApiName: "ztie-dashboard",
      description:
        "ZTIE Story 4.3 dashboard read API — GET /dashboard (fleet) + GET /status/{intake_id} (per-intake), IAM auth, non-proxy integration over the UNCHANGED 4.2 hub_dashboard Lambda.",
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 50,
        throttlingBurstLimit: 20,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        metricsEnabled: true,
      },
    });

    // NON-PROXY (custom) integration — NOT `proxy: true`. The 4.2 `hub_dashboard`
    // Lambda is invoked directly (built for direct invoke): it returns the BARE payload
    // object (`dashboard.contract.v1`) or a bare `{"error": {"code": N, ...}}` envelope,
    // NOT the `{statusCode, body}` shape a proxy integration requires. So we adapt at the
    // API-Gateway layer (keeping the 4.2 Lambda UNCHANGED — a hard constraint): a request
    // template maps the HTTP request into the exact event the handler expects, and an
    // integration response passes the Lambda's JSON straight through as the HTTP body,
    // mapping the 4.2 error envelope's `code` to the HTTP status via selection patterns on
    // a returned marker. The handler NEVER raises to the caller (it returns a bounded
    // error envelope), so a 200 default with error-code remap is correct.
    //
    // How the error status is mapped without touching the Lambda: the Lambda returns
    // `{"error": {"code": 400|404|422, ...}}` for bad input / not-found. We give the
    // integration extra integration-responses whose `selectionPattern` matches the JSON
    // the Lambda emits (a regex over the response body containing e.g. `"code": 404`) and
    // set the method response status accordingly. The success case (no `error` key) falls
    // through to the 200 default.
    const passthroughResponseTemplates = {
      "application/json": "$input.body",
    };
    const errorSelection = (code: number) => ({
      // Match the Lambda's `"error": {"code": <code>` marker anywhere in the body.
      selectionPattern: `[\\s\\S]*"code":\\s*${code}[\\s\\S]*`,
      statusCode: String(code),
      responseTemplates: passthroughResponseTemplates,
    });
    const commonIntegrationResponses = [
      { statusCode: "200", responseTemplates: passthroughResponseTemplates },
      errorSelection(400),
      errorSelection(404),
      errorSelection(422),
    ];
    const commonMethodResponses = [
      { statusCode: "200" },
      { statusCode: "400" },
      { statusCode: "404" },
      { statusCode: "422" },
    ];

    // GET /dashboard -> fleet view. The request template builds the direct-invoke event
    // {"view":"fleet","limit":<?limit=>} the handler expects (limit optional; the handler
    // clamps/defaults it). `subscriber_id` is accepted + passed through for the RD-028
    // per-subscriber read path.
    const dashboardResource = api.root.addResource("dashboard");
    dashboardResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(dashboardFn, {
        proxy: false,
        requestTemplates: {
          "application/json":
            '{"view":"fleet"' +
            "#if($input.params('limit') && $input.params('limit') != \"\")" +
            ',"limit":"$util.escapeJavaScript($input.params(\'limit\'))"#end' +
            "#if($input.params('subscriber_id') && $input.params('subscriber_id') != \"\")" +
            ',"subscriber_id":"$util.escapeJavaScript($input.params(\'subscriber_id\'))"#end' +
            "}",
        },
        integrationResponses: commonIntegrationResponses,
      }),
      {
        authorizationType: apigateway.AuthorizationType.IAM,
        methodResponses: commonMethodResponses,
      },
    );

    // GET /status/{intake_id} -> per-intake view. The request template builds
    // {"view":"intake","intake_id":"<path>"} from the path parameter; the handler
    // validates the UUID shape and returns a bounded 400/404 envelope on a bad/missing id.
    const statusResource = api.root
      .addResource("status")
      .addResource("{intake_id}");
    statusResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(dashboardFn, {
        proxy: false,
        requestTemplates: {
          "application/json":
            '{"view":"intake","intake_id":"$util.escapeJavaScript($input.params(\'intake_id\'))"' +
            "#if($input.params('subscriber_id') && $input.params('subscriber_id') != \"\")" +
            ',"subscriber_id":"$util.escapeJavaScript($input.params(\'subscriber_id\'))"#end' +
            "}",
        },
        integrationResponses: commonIntegrationResponses,
      }),
      {
        authorizationType: apigateway.AuthorizationType.IAM,
        methodResponses: commonMethodResponses,
      },
    );

    this.dashboardApiUrl = api.url;

    // --- Deploy the static SPA assets into the site bucket -------------------
    // The dashboard is a build-step-free vanilla HTML/CSS/JS SPA (no npm build), so the
    // exact deployed asset is produced offline and shipped as-is. A tiny config.js is
    // synthesized at deploy time carrying the API base URL + the subscriber id so the
    // client reads them without a rebuild.
    const dashboardAssetsDir = path.join(__dirname, "..", "..", "dashboard");
    const configJs =
      `// Generated at deploy time by ZtieDashboardStack (Story 4.3). Do not edit by hand.\n` +
      `window.ZTIE_CONFIG = Object.freeze({\n` +
      `  apiBaseUrl: ${JSON.stringify(api.url)},\n` +
      `  subscriberId: ${JSON.stringify(subscriberId)},\n` +
      `  contractVersion: "1.0"\n` +
      `});\n`;

    new s3deploy.BucketDeployment(this, "DashboardAssets", {
      destinationBucket: siteBucket,
      distribution,
      distributionPaths: ["/*"],
      sources: [
        s3deploy.Source.asset(dashboardAssetsDir),
        s3deploy.Source.data("config.js", configJs),
      ],
    });

    // --- Outputs (used by the live-validation handoff) ----------------------
    new CfnOutput(this, "DashboardUrl", {
      value: this.dashboardUrl,
      description:
        "CloudFront URL the operator loads the ZTIE real-time dashboard from (dark theme).",
    });
    new CfnOutput(this, "DashboardApiUrl", {
      value: api.url,
      description:
        "Base invoke URL of the dashboard read API (IAM/SigV4). GET {url}dashboard (fleet) and GET {url}status/{intake_id} (per-intake) proxy to the 4.2 hub_dashboard Lambda.",
    });
    new CfnOutput(this, "DashboardSiteBucketName", {
      value: siteBucket.bucketName,
      description:
        "Private S3 bucket holding the static dashboard assets (CloudFront OAC only).",
    });
    new CfnOutput(this, "DashboardSubscriberId", {
      value: subscriberId,
      description:
        "The subscriber id this dashboard is scoped to (RD-028: per-subscriber, org-shared; 'tenant zero' while single-tenant).",
    });
  }
}
