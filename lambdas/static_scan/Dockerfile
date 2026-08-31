# ZTIE Story 2.1 — static-scan lane Lambda, packaged as a CONTAINER IMAGE (RD-021).
#
# WHY A CONTAINER IMAGE (not a zip + layer): the lane ships four static tools —
# cfn-lint, checkov, bandit are pip packages; cfn-guard is a Rust binary. Bundling a
# native binary + heavy Python trees exceeds the practical zip/layer limits and is
# far cleaner as an image. The no-Docker rule (RD-001) is SPECIFICALLY about the
# dynamic DETONATION host (where a container would distort behavioral telemetry) —
# it does NOT apply to packaging the NON-EXECUTING static scanners. This image never
# executes the artifact; the tools only parse/inspect it.
#
# Base: the official AWS Lambda Python 3.12 runtime image (Amazon Linux 2023).

FROM public.ecr.aws/lambda/python:3.12

# --- System tooling to fetch the cfn-guard binary ---------------------------
# tar + gzip + a downloader. AL2023 uses microdnf/dnf in the Lambda image.
RUN dnf install -y tar gzip findutils && dnf clean all

# --- cfn-guard (Rust binary; installed via the official release install script) --
# Pinned version for reproducibility. The install script detects arch and drops the
# binary into ~/.guard/bin; we relocate it onto PATH. Verify it runs.
ARG CFN_GUARD_VERSION=3.1.2
RUN curl --proto '=https' --tlsv1.2 -sSf \
      https://raw.githubusercontent.com/aws-cloudformation/cloudformation-guard/${CFN_GUARD_VERSION}/install-guard.sh \
      -o /tmp/install-guard.sh \
 && sh /tmp/install-guard.sh \
 && cp "$(find /root/.guard -name cfn-guard -type f | head -n1)" /usr/local/bin/cfn-guard \
 && chmod +x /usr/local/bin/cfn-guard \
 && cfn-guard --version \
 && rm -f /tmp/install-guard.sh

# --- Python static tools + the Lambda handler deps --------------------------
COPY requirements.txt ./
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt

# Sanity: the pip tools resolve on PATH (fail the build early if not).
RUN cfn-lint --version && checkov --version && bandit --version

# --- The lane code + bundled contract + guard ruleset -----------------------
COPY normalize.py toolplan.py scanners.py awsio.py handler.py ${LAMBDA_TASK_ROOT}/
COPY static-findings.contract.v1.json ${LAMBDA_TASK_ROOT}/
COPY guard-rules ${LAMBDA_TASK_ROOT}/guard-rules

# The container-image Lambda contract: CMD = "<module>.<function>".
CMD [ "handler.handler" ]
