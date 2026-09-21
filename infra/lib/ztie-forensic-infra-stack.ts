import { Stack, StackProps, CfnOutput, Annotations, Fn } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ssm from "aws-cdk-lib/aws-ssm";
import {
  AwsCustomResource,
  AwsCustomResourcePolicy,
  PhysicalResourceId,
} from "aws-cdk-lib/custom-resources";

/**
 * ZTIE Story 2.0 — shared Phase-2 infrastructure foundation (Forensic account).
 *
 * This is the network + IAM + compute-template bedrock that ALL of Phase 2 (and,
 * transitively, Phase 3/4's Forensic-side work) stands on. It builds NO analysis
 * logic itself: no scanners (2.1), no detonation Lambda / Step Function (2.3), no
 * telemetry capture (2.4). It creates the isolated place those things run and the
 * least-privilege identities they run as.
 *
 * Everything here lives in the **Forensic account (360999005254)** — ZTIE's
 * self-contained blast zone (RD-008). The untrusted artifact only ever executes
 * here, on an **ephemeral** EC2 host, and the host **cannot phone home**.
 *
 * Design invariants (each maps to a ratified decision):
 *   - **Fully isolated network** — the VPC has ONLY `PRIVATE_ISOLATED` subnets:
 *     no Internet Gateway, no NAT, no 0.0.0.0/0 route. The detonation host has no
 *     path to the internet. Every AWS service it must reach (SSM control channel,
 *     CloudWatch Logs, S3, SQS, Bedrock) is reached over a **VPC endpoint** kept
 *     inside the VPC. (Containment side of RD-001 / RD-008 / RD-009.)
 *   - **Host-native SSM, no Docker, no SSH** — the launch template attaches an
 *     instance profile carrying `AmazonSSMManagedInstanceCore` so SSM is the ONLY
 *     command channel. There is deliberately **no key pair** on the template — no
 *     SSH ingress exists. (RD-001.)
 *   - **5-minute hard TTL** — the launch template's UserData runs
 *     `shutdown -h +5`: every instance launched from it self-terminates ~5 minutes
 *     after boot, bounding cost and blast radius even if the orchestrator dies.
 *     (RD-007.)
 *   - **Parametric AMI** — the template resolves its image from an SSM parameter
 *     (`/ztie/ami/<flavor>`, default flavor `ubuntu-22.04`) via
 *     `MachineImage.fromSsmParameter(...)`, NOT a hard-coded AMI id, so the
 *     Image-Builder-produced golden AMI can roll forward without a code change.
 *   - **RunInstances via a STATIC launch template** — the template is a durable
 *     resource created here. The *act* of launching (`ec2:RunInstances` against
 *     this template) belongs to the detonation orchestrator (Story 2.3), NOT to
 *     CloudFormation-per-run.
 *   - **No durable data store** — consistent with RD-012, this stack adds no
 *     DynamoDB / no bucket. It is network + identity + a launch template only;
 *     the durable record stays in the Hub.
 */

/** Forensic account (360999005254) — ZTIE self-contained blast zone (RD-008). */
const FORENSIC_ACCOUNT_ID = "360999005254";

/**
 * SSM parameter path prefix for the per-flavor golden AMIs. These parameters are
 * OWNED and MAINTAINED OUTSIDE this stack (the Image Builder pipeline writes them,
 * e.g. `/ztie/ami/ubuntu-22.04` -> ami-xxxx). This stack only CONSUMES the value
 * at deploy time so the AMI can roll forward without touching CDK.
 */
const AMI_SSM_PREFIX = "/ztie/ami";

/** OS flavors ZTIE can detonate on. The parametric AMI is selected by flavor. */
export type AmiFlavor = "ubuntu-22.04" | "al2023" | "rhel-9";

export interface ZtieForensicInfraStackProps extends StackProps {
  /**
   * OS flavor whose golden AMI the launch template resolves from SSM
   * (`/ztie/ami/<flavor>`). Defaults to `ubuntu-22.04`, the flavor whose SSM
   * parameter is known to exist live (the AL2023 Image Builder build is still
   * failing at time of writing — see the story brief's Lessons Learned).
   */
  readonly amiFlavor?: AmiFlavor;
  /**
   * Hard TTL, in minutes, applied to every ephemeral detonation host via
   * `shutdown -h +<minutes>` in UserData. Defaults to 5 (RD-007). Do not raise
   * this without a ratified decision — it is a blast-radius / cost bound.
   */
  readonly detonationTtlMinutes?: number;
  /**
   * Story 2.4S / Fix B (RD-058): the Forensic artifact bucket NAME (intake stack output
   * `ArtifactBucketName`). When supplied, the ephemeral detonation host role is granted
   * `s3:PutObject` scoped STRICTLY to that bucket's `traces/*` prefix, so the host can
   * upload the `strace -o` per-PID behavioral trace files DIRECTLY to Forensic S3 before
   * exit — decoupling trace SURVIVAL from the fragile SSM stdout transport (attempts 1-6).
   *
   * Passed as a plain STRING (not a Bucket object / cross-stack ref) on purpose: the
   * bucket is created in the intake stack, which is deployed AFTER this foundation stack,
   * so importing it as a construct here would create a dependency cycle. A string + a
   * constructed ARN keeps this stack cycle-free (the grant is a pure IAM statement; it
   * does not require the bucket to exist at synth time). Omit it and no trace-upload grant
   * is added (backward-compatible; the Lambda then falls back to the SSM-stdout path).
   */
  readonly artifactBucketName?: string;
}

export class ZtieForensicInfraStack extends Stack {
  /** The isolated detonation VPC (consumed by Story 2.3). */
  public readonly vpc: ec2.IVpc;
  /** The launch template ephemeral detonation hosts are launched from (2.3). */
  public readonly detonationLaunchTemplate: ec2.LaunchTemplate;
  /** Role assumed on the ephemeral host (SSM command channel; Bedrock; logs). */
  public readonly detonationInstanceRole: iam.Role;
  /** Role the detonation orchestrator (2.3) assumes to RunInstances + drive SSM. */
  public readonly orchestratorRole: iam.Role;

  constructor(
    scope: Construct,
    id: string,
    props?: ZtieForensicInfraStackProps,
  ) {
    super(scope, id, props);

    // Guard: this foundation is for the Forensic blast zone. Warn loudly (not a
    // hard failure, so account-less `cdk synth`/CI still works) if it is being
    // deployed anywhere else — putting the detonation network/identities outside
    // Forensic would breach RD-008.
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE Phase-2 infra is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (ZTIE self-contained blast zone, RD-008); ` +
          `deploying into ${props.env.account}. Detonation must be contained in ` +
          `Forensic. Confirm this is intentional.`,
      );
    }

    const amiFlavor: AmiFlavor = props?.amiFlavor ?? "ubuntu-22.04";
    const ttlMinutes = props?.detonationTtlMinutes ?? 5;

    // ------------------------------------------------------------------------
    // 1) VPC — ISOLATED ONLY. No IGW, no NAT, no 0.0.0.0/0 route anywhere.
    // ------------------------------------------------------------------------
    // `natGateways: 0` + only `PRIVATE_ISOLATED` subnets means CDK creates no
    // Internet Gateway and no NAT Gateway, and the route tables carry only the
    // local VPC route. The detonation host literally has no egress path off the
    // VPC except through the VPC endpoints created below.
    const vpc = new ec2.Vpc(this, "DetonationVpc", {
      maxAzs: 2,
      natGateways: 0,
      // Explicit CIDR so the isolated space is predictable/auditable.
      ipAddresses: ec2.IpAddresses.cidr("10.90.0.0/16"),
      subnetConfiguration: [
        {
          name: "detonation-isolated",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 20,
        },
      ],
      // Flow logs give us a network-level audit of the isolated subnet (should be
      // near-silent except endpoint traffic) — useful evidence that nothing
      // phoned home.
      flowLogs: {
        "isolated-flow-logs": {
          trafficType: ec2.FlowLogTrafficType.ALL,
        },
      },
    });
    this.vpc = vpc;

    // Security group for the interface VPC endpoints: allow HTTPS from within the
    // VPC only. This is what lets the host talk to SSM/Logs/SQS/Bedrock without
    // any internet path.
    const endpointSg = new ec2.SecurityGroup(this, "EndpointSg", {
      vpc,
      description:
        "ZTIE Forensic: allow in-VPC HTTPS to the interface VPC endpoints only.",
      allowAllOutbound: false,
    });
    endpointSg.addIngressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      "In-VPC HTTPS to interface endpoints (SSM/Logs/SQS/Bedrock).",
    );

    // Security group for the ephemeral detonation host. NO inbound rules at all
    // (no SSH, nothing). Outbound is restricted to in-VPC HTTPS so the SSM agent
    // and telemetry can reach the endpoints — but nothing can leave the VPC.
    const detonationSg = new ec2.SecurityGroup(this, "DetonationHostSg", {
      vpc,
      description:
        "ZTIE Forensic: ephemeral detonation host. No inbound. Egress = in-VPC HTTPS to endpoints only (no internet).",
      allowAllOutbound: false,
    });
    // In-VPC HTTPS to the INTERFACE endpoints (their ENIs have private IPs inside
    // the VPC CIDR): SSM / Logs / SQS / Bedrock.
    detonationSg.addEgressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      "Host to in-VPC HTTPS (interface VPC endpoints) only. No internet egress.",
    );

    // ------------------------------------------------------------------------
    // 2) VPC ENDPOINTS — the ONLY way anything in this VPC reaches AWS.
    // ------------------------------------------------------------------------
    // Gateway endpoint: S3 (route-table based, free). Carries S3 traffic for the
    // SSM agent's S3-backed operations AND the detonation lane's artifact fetch. It
    // intercepts the REGIONAL S3 host; the detonation lane presigns regional URLs so
    // the isolated host's artifact fetch uses this path.
    vpc.addGatewayEndpoint("S3GatewayEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    // CRITICAL for the detonation-host artifact fetch: an S3 GATEWAY endpoint routes
    // to S3's PUBLIC IP ranges (its managed prefix list) — which are OUTSIDE the VPC
    // CIDR. The host SG egress above only allows the VPC CIDR, so without this the
    // host's HTTPS to S3 is silently DROPPED and curl TCP-times out on a public S3 IP
    // (verified live 2026-09-04 — the route existed in the isolated subnets, but this
    // SG rule was the wall). Allow 443 egress to EXACTLY the AWS-managed S3 prefix
    // list — nothing else. The host stays fully isolated (VPC CIDR + S3 prefix list
    // only; still no general internet egress, RD-008).
    //
    // The prefix-list id is resolved via a REAL ``ec2:DescribeManagedPrefixLists``
    // call (AwsCustomResource — a long-stable CDK API, in `custom-resources` since
    // early CDK v2), filtered by the well-known S3 prefix-list name
    // (`com.amazonaws.<region>.s3`) — NOT a hard-coded ``pl-...`` id, so it resolves
    // correctly per-region/account without depending on a specific CDK minor version
    // shipping a dedicated `PrefixList.fromLookup` L2 helper.
    const s3PrefixListLookup = new AwsCustomResource(
      this,
      "S3ManagedPrefixListLookup",
      {
        onUpdate: {
          service: "EC2",
          action: "describeManagedPrefixLists",
          parameters: {
            Filters: [
              {
                Name: "prefix-list-name",
                Values: [`com.amazonaws.${this.region}.s3`],
              },
            ],
          },
          // Bound the retained response to exactly the id we need (avoids the
          // CloudFormation custom-resource 4096-byte response-size limit and keeps
          // getResponseField's array-index path reliable).
          outputPaths: ["PrefixLists.0.PrefixListId"],
          physicalResourceId: PhysicalResourceId.of(
            `S3ManagedPrefixListLookup-${this.region}`,
          ),
        },
        policy: AwsCustomResourcePolicy.fromSdkCalls({
          resources: AwsCustomResourcePolicy.ANY_RESOURCE,
        }),
      },
    );
    const s3PrefixListId = s3PrefixListLookup.getResponseField(
      "PrefixLists.0.PrefixListId",
    );
    detonationSg.addEgressRule(
      ec2.Peer.prefixList(s3PrefixListId),
      ec2.Port.tcp(443),
      "Host to S3 via the AWS-managed S3 prefix list (gateway-endpoint artifact fetch).",
    );

    // TWO-TIER INTERFACE ENDPOINTS (RD-027).
    // ------------------------------------------------------------------------
    // Background: the original design made ALL SIX interface endpoints always-on
    // in 2 AZs (~$88/mo idle). Story 2.0E first tried making all six EPHEMERAL
    // (created per detonation, destroyed after) to drive idle cost to ~0 — but live
    // validation (2026-09-07) showed the SSM CONTROL CHANNEL cannot be created
    // per-run reliably: a just-booted host's SSM agent could not open a connection
    // to a same-run-created ssm/ssmmessages/ec2messages endpoint (curl returned
    // 000/connect-timeout even though DNS resolved, the SGs allowed it, the endpoint
    // was 'available', and host+endpoint shared one AZ), so detonation succeeded
    // only ~1 in 3 runs. Story 2.3 proved always-on SSM endpoints are rock-solid.
    //
    // Decision (RD-027): SPLIT the endpoints into two tiers by whether the host
    // needs them AT BOOT / for the control channel:
    //   * ALWAYS-ON (this stack), SINGLE AZ: ssm + ssmmessages + ec2messages — the
    //     host-native SSM command channel (RD-001). Warm + reliable; a booting agent
    //     connects immediately. Cost ~= 3 x 1 AZ ~= $22/mo.
    //   * EPHEMERAL (orchestrator, Story 2.0E), per-run: logs + sqs +
    //     bedrock-runtime — NOT needed at agent-registration time. Created
    //     just-in-time, torn down after; idle cost ~0 for this tier (~$66/mo saved).
    //
    // Net: reliable detonation + ~75% of the idle saving, with NO run-to-run residue
    // risk (residue containment is the ephemeral HOST + wiped volume, not the
    // endpoints — an interface endpoint is a managed network doorway with no surface
    // for a payload to write to). Multi-AZ was dropped for the control channel: the
    // detonation lane launches ONE host in one subnet, so one AZ suffices and halves
    // even the always-on cost. See RD-027 for the full investigation.
    //
    // Always-on control-channel endpoints, pinned to a SINGLE isolated subnet:
    const controlChannelSubnets = vpc
      .selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_ISOLATED })
      .subnets.slice(0, 1);
    const controlChannelEndpoints: Record<
      string,
      ec2.InterfaceVpcEndpointAwsService
    > = {
      SsmEndpoint: ec2.InterfaceVpcEndpointAwsService.SSM,
      SsmMessagesEndpoint: ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
      Ec2MessagesEndpoint: ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
      // NOTE: NO S3 interface endpoint. S3 is reached via the GATEWAY endpoint
      // above (prefix-list route, free, no SG, no DNS override). A brief experiment
      // added an S3 *interface* endpoint with private DNS (2026-09-04) — but with
      // the gateway endpoint also present, its private DNS conflicts and the
      // isolated host resolved S3 to a PUBLIC IP and TCP-timed-out (verified live).
    };
    for (const [logicalId, service] of Object.entries(
      controlChannelEndpoints,
    )) {
      vpc.addInterfaceEndpoint(logicalId, {
        service,
        securityGroups: [endpointSg],
        privateDnsEnabled: true,
        subnets: { subnets: controlChannelSubnets },
      });
    }

    // The EPHEMERAL tier: service names the orchestrator (Story 2.0E) creates
    // per-run and tears down after. Built from stable, well-known short-name
    // segments (explicit + version-robust) rather than a CDK internal property.
    // Published to SSM below so the Lambda has no infrastructure literals baked in.
    const ephemeralEndpointShortNames = ["logs", "sqs", "bedrock-runtime"];
    const ephemeralEndpointServiceNames = ephemeralEndpointShortNames.map(
      (short) => `com.amazonaws.${this.region}.${short}`,
    );

    // ------------------------------------------------------------------------
    // 3) IAM — least-privilege identities.
    // ------------------------------------------------------------------------
    // (a) The instance role assumed ON the ephemeral detonation host. It gets the
    //     AWS-managed SSM core policy (so SSM is the command channel) plus the
    //     narrow extra permissions the host needs to emit telemetry and (for the
    //     future correlation step) invoke Nova Pro. It does NOT get broad EC2 or
    //     data-store access.
    const detonationInstanceRole = new iam.Role(
      this,
      "DetonationInstanceRole",
      {
        assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
        description:
          "ZTIE ephemeral detonation host role: host-native SSM channel + telemetry logs + Bedrock Nova Pro invoke. No SSH, no broad EC2.",
        managedPolicies: [
          // Host-native SSM: register with SSM, receive commands, report status.
          iam.ManagedPolicy.fromAwsManagedPolicyName(
            "AmazonSSMManagedInstanceCore",
          ),
        ],
      },
    );
    this.detonationInstanceRole = detonationInstanceRole;

    // Bedrock Nova Pro invoke (RD-003). Scoped to the Nova Pro model family in
    // this region/account rather than "*" so the grant is auditable. The dynamic
    // lane may summarize/inspect via Nova Pro; broader Phase-3 correlation runs
    // Hub/Forensic-side and reuses this pattern.
    detonationInstanceRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "InvokeNovaPro",
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          // e.g. arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0
          Fn.sub(
            "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/amazon.nova-pro-v1:0",
          ),
          Fn.sub(
            "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/amazon.nova-pro-v1:*",
          ),
        ],
      }),
    );

    // Story 2.4S / Fix B (RD-058): let the ephemeral host upload the strace per-PID
    // behavioral trace files DIRECTLY to Forensic S3 (traces/{intake_id}/) before exit, so
    // the trace SURVIVES the SSM stdout hang that failed attempts 1-6. Scoped STRICTLY to
    // s3:PutObject on the artifact bucket's `traces/*` prefix — no other bucket, no GET,
    // no DELETE, no bucket-level actions. The bucket NAME is passed as a string (the bucket
    // lives in the intake stack, deployed after this one; a construct ref would create a
    // dependency cycle), and the ARN is constructed directly — a pure IAM statement that
    // needs no synth-time bucket object. Only added when the name is supplied.
    if (props?.artifactBucketName) {
      detonationInstanceRole.addToPolicy(
        new iam.PolicyStatement({
          sid: "UploadBehavioralTraceToForensicS3",
          effect: iam.Effect.ALLOW,
          actions: ["s3:PutObject"],
          resources: [
            Fn.sub("arn:${AWS::Partition}:s3:::${BucketName}/traces/*", {
              BucketName: props.artifactBucketName,
            }),
          ],
        }),
      );
    } else {
      Annotations.of(this).addWarning(
        "ZtieForensicInfraStack: no `artifactBucketName` supplied, so the detonation host " +
          "role was NOT granted s3:PutObject on traces/* — the Story 2.4S/RD-058 direct " +
          "trace upload will be unavailable and the lane falls back to the SSM-stdout " +
          "transport (which failed attempts 1-6). Pass -c artifactBucketName=<intake " +
          "ArtifactBucketName> to enable Fix B.",
      );
    }

    // (b) The orchestrator role the detonation Step Function / Lambda (Story 2.3)
    //     assumes to LAUNCH hosts from the template and drive them over SSM. It
    //     holds `ec2:RunInstances` (constrained to this account/region — the
    //     launch template and its guardrails enforce the isolated subnet + no key
    //     pair + TTL), the ability to tag/terminate the instances it creates, and
    //     the SSM SendCommand/Get* verbs to execute host-native. It must be able
    //     to PassRole the instance role to the launched host.
    const orchestratorRole = new iam.Role(this, "DetonationOrchestratorRole", {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal("lambda.amazonaws.com"),
        new iam.ServicePrincipal("states.amazonaws.com"),
      ),
      description:
        "ZTIE detonation orchestrator (Story 2.3): RunInstances from the launch template + host-native SSM SendCommand. Least-privilege; PassRole limited to the detonation instance role.",
    });
    this.orchestratorRole = orchestratorRole;

    orchestratorRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "RunAndManageEphemeralDetonationHosts",
        effect: iam.Effect.ALLOW,
        actions: [
          "ec2:RunInstances",
          "ec2:CreateTags",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
        ],
        // RunInstances touches many sub-resources; scope by account/region. The
        // launch template is the real guardrail (isolated subnet, no key pair,
        // TTL UserData), and 2.3 will further constrain with tag conditions.
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    orchestratorRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "HostNativeSsmCommandChannel",
        effect: iam.Effect.ALLOW,
        actions: [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommandInvocations",
          "ssm:ListCommands",
          "ssm:DescribeInstanceInformation",
        ],
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    // RD-027: the orchestrator creates the EPHEMERAL tier (logs/sqs/bedrock-runtime)
    // just-in-time before a detonation and deletes them after, so that tier bills
    // only for the minutes of a run. Create/Delete/Describe touch many sub-resources
    // and cannot be resource-scoped tightly, so scope by region; CreateTags lets the
    // orchestrator tag them for teardown + the start-of-run orphan sweep. This
    // grants NO ability to create an IGW/NAT/route — only interface endpoints — so
    // containment (RD-008) is unaffected.
    orchestratorRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "ManageEphemeralInterfaceEndpoints",
        effect: iam.Effect.ALLOW,
        actions: [
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:DescribeVpcEndpoints",
          "ec2:CreateTags",
        ],
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    // PassRole: the orchestrator may hand ONLY the detonation instance role to a
    // launched host, and only to EC2. Nothing broader.
    orchestratorRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "PassDetonationInstanceRoleToEc2",
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [detonationInstanceRole.roleArn],
        conditions: {
          StringEquals: { "iam:PassedToService": "ec2.amazonaws.com" },
        },
      }),
    );

    // ------------------------------------------------------------------------
    // 4) LAUNCH TEMPLATE — the static resource ephemeral hosts are launched from.
    // ------------------------------------------------------------------------
    // Parametric AMI: resolve the golden image from the per-flavor SSM parameter
    // at deploy time (NOT a hard-coded id). The parameter is Image-Builder-owned.
    const amiParameterName = `${AMI_SSM_PREFIX}/${amiFlavor}`;
    const machineImage = ec2.MachineImage.fromSsmParameter(amiParameterName, {
      os: ec2.OperatingSystemType.LINUX,
    });

    // 5-minute HARD TTL (RD-007). `shutdown -h +N` schedules a halt N minutes
    // after boot; because the instances are launched with
    // InstanceInitiatedShutdownBehavior = TERMINATE (set at RunInstances time by
    // 2.3), the halt tears the host down. This is the fail-safe: even if the
    // orchestrator crashes mid-run, the host self-destructs.
    const userData = ec2.UserData.forLinux();
    userData.addCommands(
      "#!/bin/bash",
      "set -euo pipefail",
      "# ZTIE ephemeral detonation host — hard TTL fail-safe (RD-007).",
      "# Self-terminate ~5 minutes after boot no matter what the orchestrator does.",
      `shutdown -h +${ttlMinutes}`,
      "# SSM agent is baked into the golden AMI; host-native execution (RD-001)",
      "# is driven by the orchestrator over SSM SendCommand. No inbound, no SSH.",
    );

    const detonationLaunchTemplate = new ec2.LaunchTemplate(
      this,
      "DetonationLaunchTemplate",
      {
        launchTemplateName: "ztie-detonation",
        machineImage,
        // Small, cheap, sufficient for detonation; 2.3 may override per run.
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T3,
          ec2.InstanceSize.SMALL,
        ),
        role: detonationInstanceRole,
        securityGroup: detonationSg,
        userData,
        // NO key pair — SSH does not exist for this host (RD-001). SSM is the
        // only command channel.
        requireImdsv2: true,
        // Encrypt the root volume; the host handles untrusted material.
        blockDevices: [
          {
            deviceName: "/dev/sda1",
            volume: ec2.BlockDeviceVolume.ebs(20, {
              encrypted: true,
              deleteOnTermination: true,
              volumeType: ec2.EbsDeviceVolumeType.GP3,
            }),
          },
        ],
        // Default any interface created from this template to no public IP; the
        // subnet is isolated anyway, but this is belt-and-suspenders.
        associatePublicIpAddress: false,
      },
    );
    this.detonationLaunchTemplate = detonationLaunchTemplate;

    // ------------------------------------------------------------------------
    // 5) SSM wiring — publish the foundation's coordinates for 2.3+ to consume.
    // ------------------------------------------------------------------------
    // These are ZTIE-OWNED config parameters (distinct from the Image-Builder AMI
    // params). 2.3's orchestrator reads them instead of hard-coding ids, so the
    // dynamic-lane code has no infrastructure literals baked in.
    new ssm.StringParameter(this, "LaunchTemplateIdParam", {
      parameterName: "/ztie/detonation/launch-template-id",
      stringValue: detonationLaunchTemplate.launchTemplateId!,
      description:
        "ZTIE detonation launch template id (consumed by the Story 2.3 orchestrator for ec2:RunInstances).",
    });
    new ssm.StringParameter(this, "InstanceProfileArnParam", {
      parameterName: "/ztie/detonation/instance-role-arn",
      stringValue: detonationInstanceRole.roleArn,
      description:
        "ZTIE detonation host instance role ARN (host-native SSM + Bedrock).",
    });
    new ssm.StringParameter(this, "IsolatedSubnetIdsParam", {
      parameterName: "/ztie/detonation/isolated-subnet-ids",
      stringValue: Fn.join(
        ",",
        vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_ISOLATED })
          .subnetIds,
      ),
      description:
        "ZTIE isolated subnet ids the detonation host launches into (no internet egress).",
    });
    new ssm.StringParameter(this, "AmiFlavorParam", {
      parameterName: "/ztie/detonation/ami-flavor",
      stringValue: amiFlavor,
      description:
        "OS flavor whose golden AMI the detonation launch template resolves from /ztie/ami/<flavor>.",
    });
    // RD-027: coordinates for the EPHEMERAL endpoint tier (logs/sqs/bedrock-runtime)
    // the orchestrator stands up per run. The service names (region-resolved) are
    // the exact ServiceName values for ec2:CreateVpcEndpoint; the SG id is the
    // always-on endpoint SG the ephemeral ENIs attach to; the VPC id scopes the
    // orphan sweep. Reading these means the Lambda hard-codes NO service strings,
    // SG ids, or VPC ids. (The always-on SSM control channel is NOT listed here —
    // it is created by this stack and needs no per-run action.)
    new ssm.StringParameter(this, "VpcIdParam", {
      parameterName: "/ztie/detonation/vpc-id",
      stringValue: vpc.vpcId,
      description:
        "RD-027: isolated detonation VPC id (the orchestrator creates the ephemeral endpoint tier in this VPC).",
    });
    new ssm.StringParameter(this, "EndpointServiceNamesParam", {
      parameterName: "/ztie/detonation/endpoint-service-names",
      stringValue: ephemeralEndpointServiceNames.join(","),
      description:
        "RD-027: comma-separated interface VPC endpoint service names the detonation orchestrator creates ephemerally per run (logs/sqs/bedrock-runtime). The SSM control channel is always-on and NOT in this list.",
    });
    new ssm.StringParameter(this, "EndpointSecurityGroupIdParam", {
      parameterName: "/ztie/detonation/endpoint-security-group-id",
      stringValue: endpointSg.securityGroupId,
      description:
        "RD-027: security group id the ephemeral interface VPC endpoints attach to (in-VPC HTTPS only). Same SG as the always-on control channel.",
    });

    // ------------------------------------------------------------------------
    // 6) Outputs — everything a downstream stack / the live-validation needs.
    // ------------------------------------------------------------------------
    new CfnOutput(this, "VpcId", {
      value: vpc.vpcId,
      description: "ZTIE Forensic isolated detonation VPC id.",
    });
    new CfnOutput(this, "IsolatedSubnetIds", {
      value: vpc
        .selectSubnets({
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        })
        .subnetIds.join(","),
      description:
        "Isolated (PRIVATE_ISOLATED) subnet ids — no IGW/NAT, no 0.0.0.0/0 route.",
    });
    new CfnOutput(this, "DetonationLaunchTemplateId", {
      value: detonationLaunchTemplate.launchTemplateId!,
      description:
        "Launch template id ephemeral detonation hosts are launched from (Story 2.3 RunInstances).",
    });
    new CfnOutput(this, "DetonationLaunchTemplateName", {
      value: "ztie-detonation",
      description: "Launch template name (ztie-detonation).",
    });
    new CfnOutput(this, "AmiParameterName", {
      value: amiParameterName,
      description:
        "SSM parameter the launch template resolves the AMI from (Image-Builder-owned).",
    });
    new CfnOutput(this, "DetonationInstanceRoleArn", {
      value: detonationInstanceRole.roleArn,
      description:
        "Instance role on the ephemeral host (AmazonSSMManagedInstanceCore + Nova Pro invoke).",
    });
    new CfnOutput(this, "DetonationOrchestratorRoleArn", {
      value: orchestratorRole.roleArn,
      description:
        "Role the Story 2.3 detonation orchestrator assumes (RunInstances + host-native SSM).",
    });
    new CfnOutput(this, "DetonationTtlMinutes", {
      value: String(ttlMinutes),
      description:
        "Hard TTL (minutes) applied via UserData `shutdown -h +N` on every ephemeral host (RD-007).",
    });
    new CfnOutput(this, "EphemeralEndpointServiceNames", {
      value: ephemeralEndpointServiceNames.join(","),
      description:
        "RD-027: interface VPC endpoint service names the orchestrator creates ephemerally per detonation (logs/sqs/bedrock-runtime). SSM control channel is always-on.",
    });
    new CfnOutput(this, "EndpointSecurityGroupId", {
      value: endpointSg.securityGroupId,
      description:
        "RD-027: SG the ephemeral interface endpoints (and the always-on control channel) attach to (in-VPC HTTPS only).",
    });
  }
}
