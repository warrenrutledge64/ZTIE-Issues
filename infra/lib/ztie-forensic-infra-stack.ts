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
 *   - **EPHEMERAL interface endpoints (RD-027)** — the six INTERFACE VPC endpoints
 *     (SSM / SSM Messages / EC2 Messages / CloudWatch Logs / SQS / Bedrock Runtime)
 *     are NO LONGER created here. Interface endpoints bill per-AZ-per-hour 24/7
 *     whether or not a detonation is running (~$88/mo idle for 6 endpoints x 2 AZs),
 *     yet they are only *used* for the ~minutes of an actual detonation. So the
 *     detonation orchestrator (Story 2.3 / 2.0E) now creates them just-in-time
 *     before a run and tears them down in a `finally` after, driving idle
 *     interface-endpoint cost to ~zero WITHOUT weakening any containment invariant
 *     (endpoints appearing/disappearing does not add an IGW/NAT/0.0.0.0/0 route).
 *     This stack keeps ONLY the FREE, always-on scaffolding: the isolated VPC +
 *     subnets, the **S3 GATEWAY** endpoint (route-table based, $0), the endpoint
 *     security group (so the orchestrator has a stable SG to attach the ephemeral
 *     ENIs to), the IAM roles, the launch template, and the SSM coordinates. See
 *     RD-027 and the endpoint-service-name SSM parameter published below.
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
    // Always-on, free security group the EPHEMERAL interface endpoints attach to
    // (RD-027). The endpoints come and go per run, but their SG is a stable durable
    // anchor so the orchestrator can reference it by id without creating one per
    // run. Allows in-VPC HTTPS only.
    const endpointSg = new ec2.SecurityGroup(this, "EndpointSg", {
      vpc,
      description:
        "ZTIE Forensic: allow in-VPC HTTPS to the (ephemeral) interface VPC endpoints only.",
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

    // NOTE (RD-027): the six INTERFACE endpoints (SSM / SSM Messages / EC2 Messages
    // / CloudWatch Logs / SQS / Bedrock Runtime) are DELIBERATELY NOT created here.
    // They bill per-AZ-per-hour 24/7 (~$88/mo idle for 6 x 2 AZs) but are only used
    // during a detonation, so the orchestrator (Story 2.0E) creates them
    // just-in-time and tears them down after — see the endpoint-service-name +
    // endpoint-SG coordinates published to SSM below, which the orchestrator reads
    // to build the ephemeral endpoints without hard-coding any service names.
    //
    // S3 is UNCHANGED: it is reached via the GATEWAY endpoint above (route-table
    // based, free, no SG, no DNS override), which stays always-on. A brief
    // experiment (2026-09-04) added an S3 *interface* endpoint with private DNS —
    // but with the gateway endpoint also present, its private DNS conflicts and the
    // isolated host resolved S3 to a PUBLIC IP and TCP-timed-out (verified live).
    // AWS calls out this gateway+interface private-DNS conflict for S3.
    //
    // The ordered list of interface endpoint SERVICE NAMES the orchestrator must
    // stand up per run, published to SSM so the Lambda has no infrastructure
    // literals baked in. Bedrock Runtime is retained (Phase 3 correlation is
    // intended to invoke Nova Pro from inside the isolated VPC; an idle ephemeral
    // endpoint costs $0 anyway, so keeping it costs nothing and avoids a Phase-3
    // landmine — see RD-027).
    //
    // We build the concrete `com.amazonaws.<region>.<short-name>` service names
    // from stable, well-known short-name segments rather than relying on a CDK
    // internal property, so the string the orchestrator passes to
    // ec2:CreateVpcEndpoint is explicit and version-robust. These six are the exact
    // set the durable stack used to create as always-on interface endpoints.
    const ephemeralEndpointShortNames = [
      "ssm",
      "ssmmessages",
      "ec2messages",
      "logs",
      "sqs",
      "bedrock-runtime",
    ];
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

    // Ephemeral interface VPC endpoints (RD-027): the orchestrator creates the six
    // interface endpoints just-in-time before a detonation and deletes them after,
    // so they bill only for the minutes of a run (not 24/7). CreateVpcEndpoint /
    // DeleteVpcEndpoints touch many sub-resources and cannot be resource-scoped
    // tightly, so scope by region; the Describe verbs let the orchestrator find its
    // own endpoints (by tag) for teardown + the start-of-run orphan sweep. This
    // grants NO ability to create an IGW/NAT/route — only interface endpoints —
    // so containment (RD-008) is unaffected.
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
    new ssm.StringParameter(this, "VpcIdParam", {
      parameterName: "/ztie/detonation/vpc-id",
      stringValue: vpc.vpcId,
      description:
        "RD-027: isolated detonation VPC id (the orchestrator creates the ephemeral interface endpoints in this VPC).",
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
    // RD-027: coordinates for the EPHEMERAL interface endpoints the orchestrator
    // stands up per run. The service names (region-resolved) are the exact
    // ServiceName values for ec2:CreateVpcEndpoint; the SG id is the always-on
    // endpoint SG the ephemeral ENIs attach to (in-VPC HTTPS only). Reading these
    // means the Lambda hard-codes NO service strings or SG ids.
    new ssm.StringParameter(this, "EndpointServiceNamesParam", {
      parameterName: "/ztie/detonation/endpoint-service-names",
      stringValue: ephemeralEndpointServiceNames.join(","),
      description:
        "RD-027: comma-separated interface VPC endpoint service names the detonation orchestrator creates ephemerally per run (SSM/SSMMessages/EC2Messages/Logs/SQS/BedrockRuntime).",
    });
    new ssm.StringParameter(this, "EndpointSecurityGroupIdParam", {
      parameterName: "/ztie/detonation/endpoint-security-group-id",
      stringValue: endpointSg.securityGroupId,
      description:
        "RD-027: security group id the ephemeral interface VPC endpoints attach to (in-VPC HTTPS only). Always-on and free; only the endpoints themselves are ephemeral.",
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
        "RD-027: interface VPC endpoint service names the orchestrator creates ephemerally per detonation (idle interface-endpoint cost -> ~0).",
    });
    new CfnOutput(this, "EndpointSecurityGroupId", {
      value: endpointSg.securityGroupId,
      description:
        "RD-027: always-on SG the ephemeral interface endpoints attach to (in-VPC HTTPS only).",
    });
  }
}
