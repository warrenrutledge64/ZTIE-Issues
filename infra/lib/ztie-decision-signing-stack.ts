import {
  Stack,
  StackProps,
  RemovalPolicy,
  CfnOutput,
  Annotations,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as kms from "aws-cdk-lib/aws-kms";
import * as iam from "aws-cdk-lib/aws-iam";

/**
 * ZTIE Story H.2 (RD-048 / RD-049) — the Hub-owned decision SIGNING key.
 *
 * This stack deploys into the **Hub** account (Pipeline-Hub, 641628980935) — the
 * strict control plane. It creates the **KMS asymmetric signing key** the Hub uses
 * to SIGN authenticated `decision.token.v1` decisions that spokes VERIFY OFFLINE
 * against the exported public key (RD-048: the Hub hands out authenticated
 * decisions; no spoke reads into the Hub).
 *
 *   Hub signer principal --kms:Sign--> [Hub asymmetric key (ECC_NIST_P256)]
 *                                              │  (public half exported once,
 *                                              │   embedded into each spoke at deploy)
 *                                              ▼
 *                                    spoke verifies OFFLINE (no call to KMS / Hub)
 *
 * Design invariants (RD-048 / RD-049):
 *   * ASYMMETRIC, SIGN_VERIFY (`ECC_NIST_P256`, signing alg `ECDSA_SHA_256`). The
 *     PRIVATE half never leaves KMS; only the Hub can produce a signature.
 *   * **Only the Hub signer principal gets `kms:Sign`** (least privilege). No spoke,
 *     and no other Hub component, can sign. If no signer principal is supplied the
 *     grant falls back to the Hub account root (coarser) with a synth-time warning.
 *   * The public key is NOT a secret — it is exported once (`aws kms get-public-key`)
 *     and embedded into each spoke's config at deploy time; the spoke verifies
 *     offline, so it never calls this key (no cross-account `kms:Verify` grant — that
 *     would be a spoke->Hub call, which RD-049 rejects).
 *   * `RETAIN` on removal + rotation-friendly: losing the key invalidates the ability
 *     to issue decisions; a rotation stands up a new key and the spokes trust a SET
 *     of `key_id`s during the window (RD-049 §7).
 *
 * This stack does NOT sign anything itself and adds NO Lambda — the Hub-side signer
 * (Story 4.4) and the manual `aws kms sign` validation recipe use this key by ARN.
 */

const HUB_ACCOUNT_ID = "641628980935";

export interface ZtieDecisionSigningStackProps extends StackProps {
  /**
   * ARN of the Hub-side principal allowed to `kms:Sign` with this key — the ONLY
   * signer. For validation now, pass the ARN of the operator/role that runs the
   * manual `aws kms sign`; later (Story 4.4) pass the Hub signer Lambda's role ARN.
   * If omitted, the grant falls back to the Hub account root (still Hub-only, but
   * coarser) and a synth-time warning is emitted — prefer passing the exact ARN
   * (RD-049 least-privilege).
   */
  readonly signerPrincipalArn?: string;
}

export class ZtieDecisionSigningStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    props?: ZtieDecisionSigningStackProps,
  ) {
    super(scope, id, props);

    // Guard: the signing key is the control plane's authority to issue decisions —
    // it must live in the Hub. A synth-time annotation, not a hard failure.
    if (props?.env?.account && props.env.account !== HUB_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE decision signing key is intended for the Hub account ` +
          `${HUB_ACCOUNT_ID} (the strict control plane, RD-048); deploying into ` +
          `${props.env.account}. The Hub is the ONLY signer. Confirm this is intentional.`,
      );
    }

    // --- KMS: the Hub-owned asymmetric signing key -------------------------
    const signingKey = new kms.Key(this, "DecisionSigningKey", {
      description:
        "ZTIE Hub decision signing key (RD-048/RD-049): asymmetric ECC_NIST_P256 SIGN_VERIFY; the Hub signs decision.token.v1, spokes verify OFFLINE against the exported public key.",
      keyUsage: kms.KeyUsage.SIGN_VERIFY,
      keySpec: kms.KeySpec.ECC_NIST_P256,
      // Losing this key destroys the ability to issue authenticated decisions;
      // retain it (rotation stands up a NEW key, it does not delete this one).
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // Least privilege: EXACTLY one principal may Sign. No Verify grant is issued to
    // anyone (spokes verify offline with the public key; there is deliberately no
    // cross-account kms:Verify path — RD-049). The account admin retains key
    // administration via the default key policy.
    const signerPrincipal: iam.IPrincipal = props?.signerPrincipalArn
      ? new iam.ArnPrincipal(props.signerPrincipalArn)
      : new iam.AccountPrincipal(HUB_ACCOUNT_ID);

    if (!props?.signerPrincipalArn) {
      Annotations.of(this).addWarning(
        `No signer principal ARN provided; granting kms:Sign to the Hub account ` +
          `root (${HUB_ACCOUNT_ID}) instead of a specific principal. Still Hub-only, ` +
          `but coarser. Prefer passing signerPrincipalArn (RD-049 least-privilege).`,
      );
    }

    signingKey.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: "AllowHubSignerSignAndGetPublicKeyOnly",
        effect: iam.Effect.ALLOW,
        principals: [signerPrincipal],
        // Sign the decision token + read the public key (to export/embed in spokes).
        // Deliberately NO kms:Verify (spokes verify offline) and NO Decrypt/Encrypt
        // (this key is sign-only).
        actions: ["kms:Sign", "kms:GetPublicKey"],
        resources: ["*"], // a key resource policy's resource is the key itself
      }),
    );

    // --- Outputs (used to embed the public key in spokes + by the signer) --
    new CfnOutput(this, "DecisionSigningKeyArn", {
      value: signingKey.keyArn,
      description:
        "ZTIE Hub decision signing key ARN (RD-049). The Hub signer signs decision.token.v1 with this (kms:Sign, ECDSA_SHA_256). This ARN is the token's key_id.",
    });
    new CfnOutput(this, "DecisionSigningKeyId", {
      value: signingKey.keyId,
      description:
        "ZTIE Hub decision signing key id. Use with `aws kms get-public-key --key-id <this>` to export the public key to embed (PEM) into each spoke at deploy (offline verify).",
    });
  }
}
