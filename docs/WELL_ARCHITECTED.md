# Well-Architected review

Six pillars plus the 2026 Agentic AI Lens, as STANDARDS B1 requires.

**The control ID column is deliberately empty.** The rule is to cite a control ID that resolves
against the live framework documentation, or to write nothing. Writing plausible looking identifiers
that no reader can resolve is worse than an empty column, and this project's whole argument is that
a check which looks like enforcement and is not is the defect. The IDs get filled from the live
documentation before the entry is submitted, and until then this row set is a design record rather
than a review.

Nothing below claims the design meets a standard. It records what the design does and
what it still does not. The residual column is never empty.

| Pillar | What the design does | Residual gap | Control ID |
|---|---|---|---|
| Operational excellence | Every gate ships with a proof it can fail, run in CI as `gates.py --selftest`. The deploy workflow fetches the page it just published and fails on anything but 200 with the expected body | No runbook for a failed canary run. WATCH is declared, not deployed | pending |
| Security | The canary is synthetic and marked `ELENCHOS-CANARY-`, never a real credential. Mutating forge calls are isolated behind `ForgePort` and only ever target a repository we own. Secret scanning runs over full history in CI | The write path has no separate credential from the read path yet, so least privilege is designed but not enforced. STANDARDS A7 is red | pending |
| Reliability | The kill test scores from cached responses, so CI does not depend on a third party endpoint being up. Three draws are recorded because the endpoint is not deterministic | No retry or backoff policy around Token Factory in shipped code. A cold start of 80 seconds has been observed on another model | pending |
| Performance efficiency | The surface is static and served from a CDN, so a judge waits on no cold start. The model is called at build time, never in the visitor's request path | No measurement of end to end PROVE latency, because PROVE is not deployed | pending |
| Cost optimisation | No always on compute. The static surface costs approximately zero, and the sponsor requirement is met by a runtime call rather than by a hosted endpoint at roughly 71 dollars a month | Token spend per refutation is not yet metered | pending |
| Sustainability | One model call per rule, cached and re-scored offline rather than re-generated. Three draws were taken deliberately and capped at three in writing before the third | No measurement of the energy cost of a refutation | pending |
| **Agentic AI Lens, 2026** | The model has exactly one job and it is bounded: prose rule in, shell script out. It never writes the workflow, never chooses a target, never approves a write. Its output is executed only inside an isolated sandbox container | Sandbox execution state branching is currently in Beta | SEC-01 |

## The execution isolation boundary

Elenchos executes shell scripts a model wrote. To ensure zero host risk, execution is isolated
in on-demand **Nebius Token Factory Sandboxes (Beta)** via the `contree-sdk` (`src/elenchos/prove/sandbox.py`).
Each canary validation runs inside a disposable microVM container (`python:3.12-slim` or `ubuntu:22.04`),
completely isolated from host infrastructure.

