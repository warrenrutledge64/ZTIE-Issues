import {
  Stack,
  StackProps,
  Duration,
  RemovalPolicy,
  CfnOutput,
  Annotations,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as iam from "aws-cdk-lib/aws-iam";

/**
 * ZTIE Story 4.6 (RD-047) — the Pipeline-Sandbox landing zone (the ZTIE -> PDE door).
 *
 * This stack deploys into the **Pipeline-Sandbox** account (586917955591) — the
 * ZTIE -> PDE handoff LANDING zone. It stands up the ONE controlled destination an
 * ACCEPTED, hash-verified artifact is pushed to when it leaves the Forensic blast
 * zone toward production. The moment the artifact lands here it is under **PDE
 * control** and ZTIE's responsibility ends (Sandbox isolation + functional
 * user-acceptance of the already-cleared artifact are PDE responsibilities, not
 * ZTIE's — ZTIE does security clearance only and never re-executes the artifact).
 *
 * What it creates:
 *   1. A **Pipeline-Sandbox-OWNED** S3 landing bucket (private, block-public,
 *      enforce-SSL, versioned, SSE-S3). It is the PDE's bucket; ZTIE never owns it.
 *   2. A **cross-account bucket policy** granting EXACTLY the Forensic pusher role
 *      (Story 4.6 `pde_handoff` Lambda role, ARN passed via context)
 *      `s3:PutObject` (+ `s3:PutObjectTagging`) on EXACTLY ONE key prefix
 *      (default `accepted/`) — nothing broader, nothing else. One-directional,
 *      ZTIE-initiated, least-privilege (RD-047 / RD-013).
 *
 * The grant is deliberately the ONLY thing that couples this Sandbox bucket to
 * ZTIE. The bucket is SSE-S3 (its own default encryption), so a plaintext
 * cross-account `PutObject` from Forensic needs NO cross-account KMS grant (a
 * Sandbox CMK would force the Forensic pusher to also hold `kms:GenerateDataKey` on
 * it — deliberately avoided).
 *
 * Design invariants (RD-009 / RD-013 / RD-047):
 *   * The artifact reaches here Forensic -> Sandbox DIRECTLY; it is NEVER copied
 *     through the Hub (the Hub stays out of the blast zone).
 *   * The Forensic pusher role can ONLY PutObject under the one prefix; it cannot
 *     read, list, delete, or touch anything else in this account.
 *   * FAIL-CLOSED landing: an object only lands here on a genuine human ACCEPT + a
 *     verified sha256 — the gate that enforces that lives in the Forensic pusher
 *     (Story 4.6), not here.
 */

// Pipeline-Sandbox account (586917955591) — the ZTIE -> PDE handoff landing zone.
const PIPELINE_SANDBOX_ACCOUNT_ID = "586917955591";

export interface ZtieSandboxLandingStackProps extends StackProps {
  /**
   * ARN of the Forensic-side Story 4.6 pusher (`pde_handoff`) Lambda execution
   * role. This is the ONLY principal granted `s3:PutObject` on the landing bucket
   * (scoped to the one prefix). From the ZtiePdeHandoffStack output
   * `PdeHandoffRoleArn` on a re-deploy. If omitted, the grant falls back to the
   * Forensic account root (still one-directional + one-prefix + PutObject-only, but
   * coarser) and a synth-time warning is emitted — prefer passing the role ARN for
   * tightest least-privilege (RD-047).
   */
  readonly forensicPusherRoleArn?: string;
  /**
   * The Forensic account id whose pusher role is trusted (used only for the
   * account-root fallback grant when `forensicPusherRoleArn` is not supplied).
   * Default 360999005254.
   */
  readonly forensicAccountId?: string;
  /**
   * The single key prefix the Forensic pusher may write under (least-privilege).
   * Default `accepted/`. Must match the pusher Lambda's `SANDBOX_LANDING_PREFIX`.
   */
  readonly landingPrefix?: string;
}

export class ZtieSandboxLandingStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    props?: ZtieSandboxLandingStackProps,
  ) {
    super(scope, id, props);

    // Guard: this is the PDE landing zone. Warn loudly if it is not the
    // Pipeline-Sandbox account (a synth-time annotation, not a hard failure).
    if (
      props?.env?.account &&
      props.env.account !== PIPELINE_SANDBOX_ACCOUNT_ID
    ) {
      Annotations.of(this).addWarning(
        `ZTIE Sandbox landing zone is intended for the Pipeline-Sandbox account ` +
          `${PIPELINE_SANDBOX_ACCOUNT_ID} (the ZTIE -> PDE handoff landing zone, ` +
          `RD-047); deploying into ${props.env.account}. Confirm this is intentional.`,
      );
    }

    const forensicAccountId = props?.forensicAccountId ?? "360999005254";
    // Normalize the prefix to end with exactly one "/" so the resource-arn scope
    // (`arn:.../<prefix>*`) grants the whole prefix and nothing above it.
    let landingPrefix = props?.landingPrefix ?? "accepted/";
    if (!landingPrefix.endsWith("/")) {
      landingPrefix += "/";
    }

    // --- S3: the Pipeline-Sandbox-owned landing bucket ---------------------
    // SSE-S3 (not a CMK) so the cross-account PutObject from Forensic needs no
    // cross-account KMS grant. Private, block-public, enforce-SSL, versioned.
    const landingBucket = new s3.Bucket(this, "PdeLandingBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          // Bound cost: landed artifacts are the PDE's to consume; expire
          // noncurrent versions after a bounded window.
          noncurrentVersionExpiration: Duration.days(90),
          abortIncompleteMultipartUploadAfter: Duration.days(7),
        },
      ],
    });

    // --- Cross-account, least-privilege, one-directional PutObject grant ---
    // The Forensic pusher role (Story 4.6) may ONLY PutObject (+ tag) under the one
    // landing prefix. Nothing else in this account is reachable from Forensic.
    const scopedObjectArn = landingBucket.arnForObjects(`${landingPrefix}*`);
    const pusherPrincipal: iam.IPrincipal = props?.forensicPusherRoleArn
      ? new iam.ArnPrincipal(props.forensicPusherRoleArn)
      : new iam.AccountPrincipal(forensicAccountId);

    if (!props?.forensicPusherRoleArn) {
      Annotations.of(this).addWarning(
        `No Forensic pusher role ARN provided; granting s3:PutObject to the ` +
          `Forensic account root (${forensicAccountId}) instead of the specific ` +
          `pusher role. Still one-directional + one-prefix + PutObject-only, but ` +
          `coarser. Prefer passing forensicPusherRoleArn (RD-047 least-privilege).`,
      );
    }

    landingBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: "AllowForensicPusherPutOnLandingPrefixOnly",
        effect: iam.Effect.ALLOW,
        principals: [pusherPrincipal],
        // PutObject to land the artifact + PutObjectTagging so the pusher may tag
        // the landed object (traceability). Deliberately NO get/list/delete.
        actions: ["s3:PutObject", "s3:PutObjectTagging"],
        resources: [scopedObjectArn],
      }),
    );

    // --- Outputs (used by the two-account deploy + live-validation handoff) --
    new CfnOutput(this, "SandboxLandingBucketName", {
      value: landingBucket.bucketName,
      description:
        "Pipeline-Sandbox landing S3 bucket (Story 4.6). Pass as sandboxLandingBucket to the Forensic ZtiePdeHandoffStack (its pusher writes here cross-account).",
    });
    new CfnOutput(this, "SandboxLandingBucketArn", {
      value: landingBucket.bucketArn,
      description: "Pipeline-Sandbox landing S3 bucket ARN (Story 4.6).",
    });
    new CfnOutput(this, "SandboxLandingPrefix", {
      value: landingPrefix,
      description:
        "The single key prefix the Forensic pusher is scoped to (least-privilege). Must match the pusher Lambda's SANDBOX_LANDING_PREFIX.",
    });
    new CfnOutput(this, "SandboxLandingAccountId", {
      value: this.account,
      description:
        "The Pipeline-Sandbox account id the artifact lands in. Pass as sandboxAccountId to the Forensic ZtiePdeHandoffStack (recorded in the handoff outcome).",
    });
  }
}
