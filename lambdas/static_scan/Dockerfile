# ZTIE Story 2.1 — static-scan lane Lambda, packaged as a CONTAINER IMAGE (RD-021).
#
# WHY A CONTAINER IMAGE (not a zip + layer): the lane ships several static tools —
# cfn-lint, checkov, bandit are pip packages; cfn-guard is a Rust binary; and
# (Story 2.2G) gitleaks is a Go binary. Bundling native binaries + heavy Python
# trees exceeds the practical zip/layer limits and is far cleaner as an image. The
# no-Docker rule (RD-001) is SPECIFICALLY about the
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

# --- gitleaks (Story 2.2G — Go binary; official GitHub release tarball) ------
# gitleaks is the deterministic, compiled secret scanner. Story 2.2G makes it the
# SOLE source of truth for secret detection, superseding the embedded SECRET regex
# rules that Story 2.2 shipped in signatures.py (the DANGEROUS / MALWARE signature
# families stay — gitleaks does not cover those). Pinned version for
# reproducibility (RD-021 / RD-025). The release asset filename carries the version
# WITHOUT the leading "v" (e.g. gitleaks_8.30.1_linux_x64.tar.gz) while the git tag
# HAS the "v" (v8.30.1) — handle both. NON-EXECUTING: this only installs the binary;
# the lane later invokes it to PARSE the artifact, never to execute it.
ARG GITLEAKS_VERSION=8.30.1
RUN curl --proto '=https' --tlsv1.2 -sSfL \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
      -o /tmp/gitleaks.tar.gz \
 && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
 && chmod +x /usr/local/bin/gitleaks \
 && gitleaks version \
 && rm -f /tmp/gitleaks.tar.gz

# --- Python static tools + the Lambda handler deps --------------------------
COPY requirements.txt ./
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt

# Sanity: the pip tools + gitleaks resolve on PATH (fail the build early if not).
RUN cfn-lint --version && checkov --version && bandit --version && gitleaks version

# --- The lane code + bundled contract + guard ruleset -----------------------
# Story 2.2 adds compliance.py (finding -> NIST/ISO control mapping) and
# signatures.py (the pure signature engine). Both are pure Python bundled here.
COPY normalize.py toolplan.py scanners.py awsio.py handler.py ${LAMBDA_TASK_ROOT}/
COPY compliance.py signatures.py ${LAMBDA_TASK_ROOT}/
COPY static-findings.contract.v1.json ${LAMBDA_TASK_ROOT}/
COPY guard-rules ${LAMBDA_TASK_ROOT}/guard-rules

# The container-image Lambda contract: CMD = "<module>.<function>".
CMD [ "handler.handler" ]
