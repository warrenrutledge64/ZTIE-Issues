"""ZTIE OD-007 — reusable wrapper-EXECUTION smoke-test harness for the detonation lane.

WHY THIS EXISTS (the offline-can't-catch-it class). FIVE straight 2.4S/2.4R live
defects were all shell/host-shape issues the offline bar could not see because it only
asserted the command *string*, never executed the emitted wrapper:

  * attempt-2 — a bare ``aws s3 cp`` resolved the GLOBAL S3 endpoint and hung; the
    best-effort ``|| true`` swallowed the failure silently.
  * attempt-3 — ``aws`` was not on the SSM ``AWS-RunShellScript`` PATH, so every host
    copy was ``aws: not found`` and failed silently.
  * the ``set -u`` ``__ZTIE_RC`` unbound crash (PR #200) — the wrapper SIGKILLed before
    the upload/emit block ran.
  * attempt-4 — the direct-upload block executed but wrote NEITHER an S3 object NOR any
    stderr to the diag log (an executed-but-inert upload sub-block; empty
    ``ZTIE-UPLOAD-DIAG`` block).

PR #200 added the FIRST test that actually EXECUTES the emitted wrapper under ``sh -u``,
but only for the instant/uninstrumented path. This module GENERALIZES that seed into a
reusable harness that runs the emitted ``capturespec.build_capture_run_commands`` wrapper
end-to-end under ``sh -u`` with a **stubbed ``aws`` on PATH** (a fake CLI that logs its
argv and can be told to exit non-zero) plus per-case stubs for ``strace`` and the artifact
shape, and returns a structured result the tests assert on: whether the upload block
actually FIRED each per-PID ``s3 cp`` + the ``_UPLOAD_COMPLETE`` sentinel copy, whether the
upload stderr reached the host diag log, which files "landed" in the fake S3, and the
wrapper's own exit/stdout. Cases covered by the companion test: instant / hanging-past-
timeout / no-shebang / strace-absent / empty-capture.

Design constraints (match the ZTIE offline sandbox):
  * stdlib-only. No boto3 / moto / pytest (the INTEGRATIONS_ONLY build sandbox has none).
  * No real AWS. ``aws`` is a stub shell script; the "S3" is a local directory the stub
    copies into, so an ``s3 cp`` that FIRES is observable as a landed file, and one that
    is inert (attempt-4) is observable as an ABSENCE.
  * The harness controls PATH exactly: a per-run ``bin/`` dir holding the stubs is placed
    AHEAD of a minimal real system dir, so real ``sh``/``setsid``/``timeout``/``head``/
    ``ls``/``grep``/``sort``/``printf``/``cat``/``mkdir``/``chmod``/``sync`` resolve while
    ``aws`` (always) and ``strace`` (optional) resolve to the stubs. This reproduces the
    SSM ``AWS-RunShellScript`` shape (a stripped PATH where the baked CLI is not present
    unless invoked by absolute path — which is exactly what capturespec does).

This is TEST SUPPORT, not shipped Lambda code. It has no ``handler`` and is never imported
at Lambda runtime; it lives in the detonation package next to the wrapper it exercises so
the reusable harness travels with the code it protects (RD-015: durable/repeatable).
"""

from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field

import capturespec as cs

# A minimal set of REAL system tools the emitted wrapper needs (resolved from the system
# after the stub dir). Everything the wrapper shells out to must be here or be a stub.
# ``strace`` is deliberately NOT here — it is provided as a stub only when a case wants
# the instrumented branch, so the "strace absent" branch is the natural default.
_REAL_TOOLS = (
    "sh",
    "setsid",
    "timeout",
    "sync",
    "head",
    "ls",
    "grep",
    "sort",
    "printf",
    "cat",
    "mkdir",
    "chmod",
    "cp",
    "env",
    "sleep",
    "true",
    "rm",
    "touch",
    "dirname",
    "basename",
)

# The absolute CLI path capturespec bakes into every host ``aws s3 cp`` (HOST_AWS_CLI).
# The harness must place the ``aws`` stub AT THIS ABSOLUTE PATH (not merely on PATH),
# because capturespec deliberately invokes the CLI by absolute path (the attempt-3 fix).
_HOST_AWS_CLI = cs.HOST_AWS_CLI


@dataclass
class HarnessResult:
    """The observable outcome of executing the emitted wrapper under ``sh -u``."""

    returncode: int
    stdout: str
    stderr: str
    # Each recorded ``aws`` invocation, as the argv list the stub saw (argv[0] == "aws").
    aws_invocations: list[list[str]] = field(default_factory=list)
    # Basenames of objects that actually LANDED in the fake S3 traces/<intake>/ prefix
    # (i.e. an ``s3 cp`` that FIRED and succeeded), including the sentinel if written.
    s3_landed: list[str] = field(default_factory=list)
    # The content of the host upload-stderr diag log (_UPLOAD_STDERR_FILE), or "" if none.
    upload_diag_log: str = ""
    # Per-PID trace files present on the fake host at emit time (basenames).
    host_trace_files: list[str] = field(default_factory=list)

    # -- convenience predicates the tests read (behavioral, not string-matching) --------
    @property
    def set_u_crashed(self) -> bool:
        """True iff the wrapper tripped ``set -u`` on an unset variable (the PR #200 bug)."""
        return "parameter not set" in self.stderr

    @property
    def aws_s3_cp_calls(self) -> list[list[str]]:
        """Only the ``aws s3 cp ...`` invocations the stub recorded."""
        return [a for a in self.aws_invocations if a[1:3] == ["s3", "cp"]]

    @property
    def sentinel_landed(self) -> bool:
        """True iff the ``_UPLOAD_COMPLETE`` completeness sentinel actually landed in S3."""
        return cs.TRACE_UPLOAD_COMPLETE_SENTINEL in self.s3_landed

    @property
    def per_pid_objects_landed(self) -> list[str]:
        """Basenames of the per-PID trace files that landed in S3 (sentinel excluded)."""
        return [k for k in self.s3_landed if k != cs.TRACE_UPLOAD_COMPLETE_SENTINEL]

    @property
    def s3_cp_dests(self) -> list[str]:
        """The S3 destination (the ``s3://...`` operand) of each ``s3 cp``, in call order.

        Robust to flags appearing after the dest — it scans each recorded invocation for
        the ``s3://`` token rather than assuming argv position.
        """
        dests: list[str] = []
        for call in self.aws_s3_cp_calls:
            dest = next((a for a in call if a.startswith("s3://")), "")
            dests.append(dest)
        return dests


def _write_exec(path: str, body: str) -> None:
    """Write ``body`` to ``path`` and mark it executable."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _aws_stub_body(*, s3_dir: str, argv_log: str, fail_s3_cp: bool) -> str:
    """A fake ``aws`` CLI (POSIX sh) that:

      * appends its full argv (one arg per line, NUL-free, record-separated) to ``argv_log``
        so the harness can reconstruct exactly what the wrapper called;
      * for ``aws s3 cp <src> <dest> ...``: unless ``fail_s3_cp``, copies the SOURCE into
        ``s3_dir/<basename-of-dest-or-src>`` so a FIRED copy is observable as a landed file;
        the sentinel form ``aws s3 cp - s3://.../_UPLOAD_COMPLETE`` reads stdin and writes
        the sentinel object. When ``fail_s3_cp`` it writes a diagnostic to stderr + exits 1
        (so the wrapper's stderr-capture + diag-log shipping is exercised on the failure
        path too).
      * ignores the regional ``--region`` / ``--endpoint-url`` / ``--only-show-errors``
        flags (they are correctness assertions the string tests already cover; here we only
        need the copy to FIRE).
    """
    # NOTE: kept deliberately small + POSIX. ``$@`` handling copes with the flags appearing
    # in any order because we scan for the first two non-flag operands after ``s3 cp``.
    fail_line = (
        'echo "ztie-aws-stub: forced s3 cp failure" 1>&2; exit 1'
        if fail_s3_cp
        else ":"
    )
    return f"""#!/bin/sh
# ztie test stub for the AWS CLI. Records argv, emulates `s3 cp` into a local dir.
_log={shlex.quote(argv_log)}
for _a in "$@"; do printf '%s\\n' "$_a" >> "$_log"; done
printf '%s\\n' '--END--' >> "$_log"

if [ "$1" = "s3" ] && [ "$2" = "cp" ]; then
  {fail_line}
  # collect the non-flag operands after `s3 cp` (src then dest)
  shift 2
  _src=""; _dest=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --*) # flag with a value we don't care about; skip its value if it has one
        case "$1" in
          --region|--endpoint-url) shift ;;
        esac
        ;;
      *)
        if [ -z "$_src" ]; then _src="$1"; elif [ -z "$_dest" ]; then _dest="$1"; fi
        ;;
    esac
    shift
  done
  _s3dir={shlex.quote(s3_dir)}
  mkdir -p "$_s3dir"
  # Emulate `aws s3 cp` object naming: if the dest ends in `/` (a prefix/"directory"),
  # the landed object takes the SOURCE basename (…/traces/<id>/behavior.strace.<pid>);
  # otherwise the dest basename is the object name (…/_UPLOAD_COMPLETE).
  case "$_dest" in
    */) _name=$(basename "$_src") ;;
    *)  _name=$(basename "$_dest") ;;
  esac
  if [ "$_src" = "-" ]; then
    cat > "$_s3dir/$_name"          # sentinel: body from stdin
  else
    cp "$_src" "$_s3dir/$_name" 2>/dev/null || :
  fi
  exit 0
fi
exit 0
"""


def _strace_stub_body(*, per_pid: list[str], emit_stderr: str) -> str:
    """A fake ``strace`` that emulates ``strace -ff -o PREFIX ... <program>``:

      * writes one per-PID trace file ``PREFIX.<pid>`` for each pid in ``per_pid`` (so the
        upload/emit loop has real files to iterate) — UNLESS ``per_pid`` is empty, which
        emulates the "strace ran but produced no per-PID file" case (2.4R FAIL #2);
      * writes ``emit_stderr`` to its own fd 2 (the wrapper redirects that to the strace
        stderr file), so the no-trace diagnostic path can be exercised;
      * still RUNS the traced program (the last non-flag argv) so the artifact's real exit
        code / hang behavior flows through (the wrapper relies on the artifact's rc).

    It parses ``-o PREFIX`` to know where to write, and treats the final argument(s) as the
    program to exec (``strace ... /bin/sh <artifact>`` or ``strace ... <artifact>``).
    """
    # Build the per-PID file writes.
    writes = "\n".join(
        f'printf %s "{shlex.quote(f"{pid} openat(AT_FDCWD, /tmp/x) = 3")}" '
        f'> "$_prefix.{pid}"'
        for pid in per_pid
    )
    stderr_line = (
        f'printf %s {shlex.quote(emit_stderr)} 1>&2' if emit_stderr else ":"
    )
    return f"""#!/bin/sh
# ztie test stub for strace. Emulates -ff -o PREFIX and execs the traced program.
_prefix=""
# find -o's value + the program (everything after the last recognized strace flag)
while [ $# -gt 0 ]; do
  case "$1" in
    -o) shift; _prefix="$1" ;;
    -ff|-tt|-y) : ;;
    -s) shift ;;
    -e) shift ;;
    --) shift; break ;;
    -*) : ;;   # any other strace flag: ignore
    *) break ;;  # first non-flag = the program to run
  esac
  shift
done
# $@ now begins with the program (e.g. `/bin/sh <artifact>` or `<artifact>`).
{stderr_line}
{writes}
# Run the traced program so its real rc / hang flows through (may be killed by timeout).
if [ $# -gt 0 ]; then "$@"; fi
"""


def run_wrapper(
    *,
    artifact_body: str,
    artifact_name: str = "a.sh",
    strace_present: bool = True,
    strace_pids: list[str] | None = None,
    strace_stderr: str = "",
    fail_s3_cp: bool = False,
    bucket: str = "b-forensic",
    intake_id: str = "11111111-1111-4111-8111-111111111111",
    region: str = "us-east-1",
    ssm_execution_timeout_s: int = 20,
    timeout_s: int = 60,
) -> HarnessResult:
    """Build the emitted capture wrapper and EXECUTE it under ``sh -u`` in a hermetic
    temp environment with a stubbed ``aws`` (and optional ``strace``) on a controlled PATH.

    Returns a :class:`HarnessResult` with the wrapper's exit/stdout/stderr AND the
    observable side effects of the upload block: which ``aws`` invocations fired, which
    objects landed in the fake S3, and the upload diag log.

    * ``artifact_body`` — the artifact file contents (e.g. an instant echo, or a hanging
      ``sleep``/``read`` to exercise the timeout-survival path).
    * ``strace_present`` — when True, an ``aws``-independent ``strace`` stub is on PATH so
      the INSTRUMENTED branch runs; when False, ``strace`` is absent so the UNINSTRUMENTED
      branch runs (no upload block — matching capturespec's structure).
    * ``strace_pids`` — the per-PID trace files the strace stub creates (default one PID).
      An empty list emulates "strace produced no per-PID file" (the no-trace diagnostic).
    * ``fail_s3_cp`` — when True the ``aws`` stub fails every ``s3 cp`` (exercises the
      self-diagnosing upload-stderr path).
    * ``ssm_execution_timeout_s`` — the outer ceiling this harness enforces to STAND IN for
      the SSM ``executionTimeout``. capturespec bounds the artifact with its own
      ``setsid timeout`` (ARTIFACT_EXEC_TIMEOUT_S); to keep the test fast we temporarily
      shrink that budget below this ceiling so a hanging artifact is terminated by the
      wrapper's own ``timeout`` (survival path) rather than by this ceiling.
    """
    strace_pids = ["4242"] if strace_pids is None else strace_pids

    with tempfile.TemporaryDirectory() as d:
        bin_dir = os.path.join(d, "bin")
        s3_dir = os.path.join(d, "s3", "traces", intake_id)
        argv_log = os.path.join(d, "aws-argv.log")
        os.makedirs(bin_dir, exist_ok=True)
        os.makedirs(s3_dir, exist_ok=True)

        # 1) Symlink the REAL system tools into the stub bin dir so the wrapper's shell
        #    resolves them, but ``aws``/``strace`` come from our stubs.
        for tool in _REAL_TOOLS:
            real = _which_real(tool)
            if real:
                link = os.path.join(bin_dir, tool)
                try:
                    os.symlink(real, link)
                except FileExistsError:
                    pass

        # 2) The ``aws`` stub is staged ONLY at the absolute HOST_AWS_CLI path — NOT on
        #    PATH. This faithfully reproduces the SSM ``AWS-RunShellScript`` shape where the
        #    baked CLI is NOT on the stripped PATH (the attempt-3 failure): the wrapper must
        #    invoke the CLI by ABSOLUTE path, so if a regression reverts to a bare ``aws``
        #    the copy would be ``not found`` and NO object lands — a failure the tests catch.
        #    (Deliberately not placed on PATH so a bare-``aws`` regression cannot be masked.)
        aws_body = _aws_stub_body(s3_dir=s3_dir, argv_log=argv_log, fail_s3_cp=fail_s3_cp)
        abs_aws = os.path.join(d, "abs-aws")  # stand-in for HOST_AWS_CLI
        _write_exec(abs_aws, aws_body)

        # 3) Optional strace stub.
        if strace_present:
            _write_exec(
                os.path.join(bin_dir, "strace"),
                _strace_stub_body(per_pid=strace_pids, emit_stderr=strace_stderr),
            )

        # 4) The artifact itself, staged where capturespec expects it (its host path).
        stage_dir = os.path.join(d, "stage")
        os.makedirs(stage_dir, exist_ok=True)
        artifact_path = os.path.join(stage_dir, artifact_name)
        _write_exec(artifact_path, artifact_body)

        # 5) Build the wrapper. Shrink the artifact exec budget so a hanging artifact is
        #    terminated by the wrapper's own ``setsid timeout`` well within the test ceiling
        #    (mirrors how, live, BUDGET+GRACE stays under the SSM executionTimeout). We also
        #    redirect HOST_AWS_CLI to our staged absolute stub for the duration of the build.
        script = _build_wrapper_script(
            artifact_path=artifact_path,
            bucket=bucket,
            intake_id=intake_id,
            region=region,
            abs_aws=abs_aws,
            exec_budget_s=max(2, min(5, ssm_execution_timeout_s - 3)),
            kill_grace_s=1,
        )

        # 6) Execute under ``sh -u`` with the controlled PATH. A minimal real fallback dir
        #    keeps the shell's own builtins/loader happy without leaking the host PATH.
        env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": d}
        proc = subprocess.run(
            ["sh", "-u", "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=d,
            timeout=timeout_s,
            check=False,
        )

        # 7) Reconstruct observations.
        aws_invocations = _parse_argv_log(argv_log)
        s3_landed = sorted(os.listdir(s3_dir)) if os.path.isdir(s3_dir) else []
        diag = ""
        # The wrapper writes its upload diag log under ``_UPLOAD_STDERR_FILE`` which lives
        # inside ``_STAGE_DIR`` (``/tmp/ztie/upload.stderr``); _build_wrapper_script rewrote
        # the ``_STAGE_DIR`` prefix to the hermetic per-run dir, so read it from there ONLY
        # (no fallback to the real /tmp/ztie — that would leak a stale file between runs).
        staged_diag = cs._UPLOAD_STDERR_FILE.replace(
            cs._STAGE_DIR, stage_dir_for_reads(d)
        )
        if os.path.isfile(staged_diag):
            with open(staged_diag, encoding="utf-8", errors="replace") as fh:
                diag = fh.read()
        host_traces = _host_trace_basenames(d)

        return HarnessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            aws_invocations=aws_invocations,
            s3_landed=s3_landed,
            upload_diag_log=diag,
            host_trace_files=host_traces,
        )


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------
def _which_real(tool: str) -> str | None:
    """Resolve a tool from the REAL system dirs only (never from a stub dir)."""
    for base in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        cand = os.path.join(base, tool)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def stage_dir_for_reads(tmp: str) -> str:
    """Where the wrapper's ``_STAGE_DIR`` files land during a harness run.

    capturespec uses the absolute ``/tmp/ztie`` for both the stage dir and the upload
    diag log. To keep the harness hermetic we rewrite that prefix to a per-run temp dir
    in :func:`_build_wrapper_script`; this returns that same rewritten dir so the caller
    can read the diag log / trace files the wrapper produced.
    """
    return os.path.join(tmp, "ztie-stage")


def _build_wrapper_script(
    *,
    artifact_path: str,
    bucket: str,
    intake_id: str,
    region: str,
    abs_aws: str,
    exec_budget_s: int,
    kill_grace_s: int,
) -> str:
    """Build the emitted wrapper and rewrite the two absolute host paths capturespec bakes
    in (``/tmp/ztie`` staging + the ``/usr/local/...`` CLI) to hermetic per-run temp paths,
    and shrink the artifact exec budget, WITHOUT modifying capturespec.

    We do this by monkey-free string substitution on the emitted command list: capturespec
    is pure and emits deterministic literals, so replacing the two known absolute prefixes
    + the timeout numbers is exact and safe. (We deliberately do NOT edit capturespec's
    constants at import time — the harness must exercise the SHIPPED literals, only
    relocating the filesystem targets so the test is hermetic.)
    """
    # temporarily set the env-tunable budget so build_capture_run_commands bakes small
    # numbers (capturespec reads ARTIFACT_EXEC_TIMEOUT_S/KILL at import; it also exposes
    # them as module attrs we can override for the build).
    orig_budget = cs.ARTIFACT_EXEC_TIMEOUT_S
    orig_grace = cs.ARTIFACT_EXEC_KILL_GRACE_S
    cs.ARTIFACT_EXEC_TIMEOUT_S = exec_budget_s
    cs.ARTIFACT_EXEC_KILL_GRACE_S = kill_grace_s
    try:
        cmds = cs.build_capture_run_commands(
            artifact_path=artifact_path,
            bucket=bucket,
            intake_id=intake_id,
            region=region,
        )
    finally:
        cs.ARTIFACT_EXEC_TIMEOUT_S = orig_budget
        cs.ARTIFACT_EXEC_KILL_GRACE_S = orig_grace

    script = "\n".join(cmds)
    # Relocate the absolute host paths to hermetic temp targets.
    tmp = os.path.dirname(os.path.dirname(artifact_path))  # .../ (the TemporaryDirectory)
    staged = stage_dir_for_reads(tmp)
    script = script.replace(cs._STAGE_DIR, staged)
    script = script.replace(cs.HOST_AWS_CLI, abs_aws)
    return script


def _parse_argv_log(path: str) -> list[list[str]]:
    """Reconstruct the recorded ``aws`` invocations from the stub's argv log.

    Each invocation is a run of args terminated by a ``--END--`` sentinel line. argv[0] is
    synthesized as ``aws`` (the stub name) so callers can filter on the subcommand.
    """
    if not os.path.isfile(path):
        return []
    invocations: list[list[str]] = []
    cur: list[str] = ["aws"]
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh.read().splitlines():
            if raw == "--END--":
                if len(cur) > 1:
                    invocations.append(cur)
                cur = ["aws"]
            else:
                cur.append(raw)
    if len(cur) > 1:
        invocations.append(cur)
    return invocations


def _host_trace_basenames(tmp: str) -> list[str]:
    """Basenames of the per-PID strace files the wrapper produced on the fake host."""
    staged = stage_dir_for_reads(tmp)
    if not os.path.isdir(staged):
        return []
    pref = os.path.basename(cs._TRACE_PREFIX)  # "behavior.strace"
    return sorted(
        name for name in os.listdir(staged) if name.startswith(pref + ".")
    )
