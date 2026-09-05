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
| **Agentic AI Lens, 2026** | The model has exactly one job and it is bounded: prose rule in, shell script out. It never writes the workflow, never chooses a target, never approves a write | **The model's output is executed, and today it is executed in a temporary directory on a CI runner behind a narrow denylist, not in an isolated sandbox.** That is a mitigation, not an isolation boundary, and it is the largest residual risk in the design. Token Factory Sandboxes give the VM isolation this needs; access is requested and not granted | pending |

## The execution isolation boundary, stated as it actually is

Elenchos executes shell scripts a model wrote. **Today that happens in a temporary directory on a
CI runner**, with a narrow denylist covering network egress, privilege escalation and destructive
filesystem patterns, and every refusal logged with the pattern it matched. That is a mitigation.
It is not an isolation boundary, and calling it one would be the unearned security claim this
project exists to expose.

`src/elenchos/prove/sandbox.py` holds the adapter for **Nebius Token Factory Sandboxes**, which
give VM isolation, execution state branching and instant restore. **It has never executed against
a real sandbox.** Access is Beta, it was requested, and it has not been granted. Without the
`contree-sdk` present the adapter falls back to a simulator, and the test asserts exactly that:
`assert "simulated" in res["provider"]`.

So the honest statement, and the one that goes in front of a judge: the blast radius of a
model-written script is currently a temporary directory on a GitHub runner. The sandbox is the
roadmap, and the surface says so in the same sentence that names it.

