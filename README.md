# Elenchos

**ἔλεγχος**: in Socrates, the method of refutation. In modern Greek, *audit*.

Your pipeline's green check is a claim, not a control. Elenchos pushes a build that
breaks the rule and returns the green run as proof.

> Early scaffolding. The only thing here today is an infrastructure probe.

## Why

Measured over 120 public repositories, none of them ours, every finding carrying a
`file:line`:

| | |
|---|---|
| run a repo-local security or quality script from a CI step | **47 / 120** |
| of those, the script is **narrower than its step name claims** | **21 / 47** |
| have a gate neutered by `continue-on-error`, `\|\| true` or `exit 0` | **18 / 120** |

And the platform net people assume covers the rest is thin. Basak et al. 2023
([SecretBench](https://arxiv.org/abs/2307.00714)), 818 repositories and 97,479 labelled
secrets, measured GitHub's secret scanner at **6% recall**, gitleaks at 86-88%.

## What is here now

`scripts/gpu_job_probe.py` answers one narrow infrastructure question: does a Nebius AI
Job with a GPU preset actually reach `RUNNING`, and how long does it take?

It exists because a previous build recorded three CPU jobs that were accepted, sat in
`PROVISIONING` with zero instances, and terminated in `ERROR` after roughly thirty
minutes with empty details. The cause was never established. A capacity read on
2026-08-31 showed the account does hold GPU quota, so "no quota" is not the explanation.

**One success proves nothing.** Run it repeatedly, at different hours.

```bash
python scripts/gpu_job_probe.py --projects <project-id>            # read-only
python scripts/gpu_job_probe.py --projects <project-id> --create   # creates one job
```

Default mode is read-only. Created jobs are always deleted in a `finally` block.

## Running it in CI

The workflow `.github/workflows/gpu-job-probe.yml` runs on manual dispatch and needs
three repository secrets: `NEBIUS_SA_KEY_B64`, `NEBIUS_SA_KEY_ID`, `NEBIUS_SA_ID`.
The workflow fails immediately, and loudly, if any of them is absent.

## Licence

MIT. See [LICENSE](LICENSE).
