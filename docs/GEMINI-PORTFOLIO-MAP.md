# Portfolio Structure Map — for Gemini

**Hand this whole file to Gemini.** It gives the planning partner a portfolio-level
view across all four repositories under `warrenrutledge64`, so sequencing and
reuse decisions can account for how the repos relate — not just ZTIE-Issues in
isolation.

Every map below is **generated** by `scripts/gen_repo_map.py` from each repo's git
tree (REPO FACTS — directory names and counts are authoritative). Only ZTIE-Issues
carries an INTERPRETATION (phase/role) layer today; the other three are mapped
facts-only because their internal semantics have not been annotated yet.

| Repo | Entries | One-line characterization |
|---|---:|---|
| `ZTIE-Issues` | 520 | The active build — the ZTIE detonation-chamber pipeline (16 lambdas, CDK infra, governance). Full annotated map: `docs/REPO_MAP.md`. |
| `aws-restore-kit` | 50 | A serverless, no-EC2 CloudFormation-rollback service gated by ABAC; built as versioned micro-components composed by a root orchestrator. |
| `ZTIE-Security-Analysis-Pipeline` | 16 | A **planning/governance-only** repo (the ZTIE effort's plan + runbook + methodology). Created from `project-os-starter`. No code yet. |
| `project-os-starter` | 13 | The **reusable OS template** itself — the governance skeleton (still carrying `{{PROJECT_NAME}}` placeholders) that the other efforts are spawned from. |

## How the four relate (the OS-vs-instance picture)

- **`project-os-starter`** is the reusable **OS layer**: METHODOLOGY, PROJECT_PLAN,
  RUNBOOK, RESTORE, BOM, and a `DOCS/session-briefs/` skeleton, with `{{PLACEHOLDER}}`
  tokens meant to be filled per project.
- **`ZTIE-Security-Analysis-Pipeline`** and (by lineage) **`ZTIE-Issues`** are
  **instances** spawned from that template — same governance doc set, project-specific
  content filled in. `ZTIE-Issues` is the one that grew the full codebase.
- **`aws-restore-kit`** is a separate product effort with the same governance DNA
  (BOM.md, RUNBOOK.md, session-briefs) but its own domain (CFN rollback), and it also
  ships a `project-os-template/` + a `project-os-starter-bootstrap/` toolset — i.e. it
  is *also* propagating the reusable OS.

This is the reusable-OS-vs-instance separation made concrete across repos: the
template repo is the liftable OS; the others are instances at different maturities
(planning-only → fully built).

---

## `ZTIE-Issues` (520 entries) — the active build

Full annotated map (REPO FACTS + phase/role INTERPRETATION) lives in the repo at
`docs/REPO_MAP.md`, and the self-contained Gemini handoff is
`docs/GEMINI-REPO-MAP-HANDOFF.md`. Top-level shape:

```
ZTIE-Issues/
├── (10 root files: README, PROJECT_PLAN, RUNBOOK, METHODOLOGY, CONVENTIONS, BOM, RESTORE, …)
├── lambdas/    (185)   16 Python 3.12 processors (intake→preprocessor→static/detonation/collector→hub_*→pde_*)
├── docs/       (172)   governance, architecture, 114 session-briefs, 34 validation-evidence
├── scripts/    (44)    check_docs.py gate (incl. CHECK M), gen_*_contract.py, gen_repo_map.py, ztie_restore/
├── schemas/    (26)    *.contract.v1.json boundary contracts
├── infra/      (16)    CDK v2 TS — 11 stacks across 3 AWS accounts
├── lib/        (7)     decision_auth (offline Hub-signed-token verify)
├── restore-manifests/ (4) · dashboard/ (4, static SPA) · prompts/ (1)
```

## `aws-restore-kit` (50 entries)

```
aws-restore-kit/
├── (root: README, BOM.md, RUNBOOK.md, LICENSE, .gitignore)
├── infra/    (5)    CloudFormation module templates:
│                    auth-module.yaml, catalog-module.yaml, engine-module.yaml,
│                    frontend-module.yaml, template.yaml (root orchestrator)
├── tools/    (15)   project-os-starter-bootstrap/ (15) — OS bootstrap toolset
├── project-os-template/ (9)   templates/ (6) + session-briefs/ (1)
└── DOCS/     (5)    session-briefs/ (2)
```

**Read:** a serverless CFN-rollback service. The `infra/` templates are the
independent micro-components (auth / catalog / engine / frontend) composed by the
root `template.yaml`. Notably it also carries the OS-propagation tooling
(`project-os-template/`, `tools/project-os-starter-bootstrap/`).

## `ZTIE-Security-Analysis-Pipeline` (16 entries)

```
ZTIE-Security-Analysis-Pipeline/
├── (root: README, METHODOLOGY, PROJECT_PLAN, RUNBOOK, RESTORE, BOM, LICENSE, .gitignore)
└── DOCS/    (6)    session-briefs/ (3)
```

**Read:** a **planning/governance-only** repo — the full project-os governance doc
set with no code tree yet. Its README states it was created from `project-os-starter`.
If ZTIE work is ever re-homed or this is the "clean" plan-of-record, this is where the
plan/runbook live in isolation from the build.

## `project-os-starter` (13 entries)

```
project-os-starter/
├── (root: README [title still {{PROJECT_NAME}}], METHODOLOGY, PROJECT_PLAN, RUNBOOK, RESTORE, BOM, LICENSE, .gitignore)
└── DOCS/    (3)    session-briefs/ (1)
```

**Read:** the **reusable OS template** — the skeleton every effort is spawned from.
Still holds `{{PLACEHOLDER}}` tokens by design. This is the artifact to evolve when a
process improvement should propagate to *future* projects (e.g. adding the repo-map
generator + CHECK M here would make the drift-proof map a default for every new effort).

---

## Refreshing any of these maps

The generator is portable — point it at any local clone:

```bash
python3 scripts/gen_repo_map.py --repo /path/to/<repo> --ref HEAD -o /tmp/<repo>-MAP.md
```

Add a `docs/repo-map.annotations.json` in a repo to give it the same
FACTS + INTERPRETATION treatment ZTIE-Issues has, and CHECK M will keep it fresh.

> **Suggested next step (reuse):** vendor `scripts/gen_repo_map.py` + the CHECK M
> wiring into `project-os-starter` so every future effort ships with a drift-proof
> structure map from day one.
