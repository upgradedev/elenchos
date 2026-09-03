# Submission

Working draft. The description is written in the owner's voice before it is pasted into the form,
so the form is never the first place a sentence appears.

## The five deliverables

A draft is a zero. The entry is submitted as soon as all five exist, then improved in place.

| # | Deliverable | State | Where |
|---|---|---|---|
| 1 | Public repository with a visible licence | private, MIT present | https://github.com/upgradedev/elenchos |
| 2 | Demo URL a stranger can open with no account | not deployed | https://upgradedev.github.io/elenchos/ |
| 3 | Written description in the owner's voice | draft below | this file |
| 4 | Public video, under three minutes, with sound | not recorded | eligibility gate |
| 5 | Entry form reading Submitted | not submitted | owner action |

Owner actions that no agent can do, and that are tested on day one rather than on the deadline:
the video upload as public rather than unlisted, the form's CAPTCHA, and pressing Submit.

## The description, draft

Your pipeline's green check is a claim, not a control. Elenchos pushes a build that breaks the rule
and returns the green run as proof.

Maximos is an engineering director at a regulated company. Two hundred repositories across GitHub
and Azure DevOps, fifty engineers, contractor teams outside his organisation entirely. Once a year
he signs a statement that the security checks are in place. At the last audit he was asked to prove
it for one repository, and all he had was a green tick.

We measured how often that tick is worth nothing. Across 120 public repositories, none of them
ours, with the threshold written down before the count: 21 of the 47 repositories that run their
own security or quality script have it narrower than the step's name claims, and 18 of 120 carry a
step that has been neutered outright by `continue-on-error`, `|| true` or a trailing `exit 0`.

Elenchos reads a pipeline and reports what each step actually enforces, with a file and a line
number. Where a rule has no check at all, Nemotron reads the rule as a human wrote it and produces
the shell script that enforces it. Deterministic code turns that script into a workflow step, runs
it against a commit built to break the rule, and keeps the resulting green run as a receipt with
its URL, its commit and the control it beat.

Every synthesised check carries a record of what produced it: the model id, the hash of the prompt,
of the response, of the script and of the step, and whether a human or an agent wrote it. The record
is content addressed, which lets a reader detect drift against a digest they hold. It is not signed
and we do not call it tamper proof, because an unearned security claim is the exact defect this
project exists to expose.

It runs on an open weight NVIDIA model served from Nebius in European regions rather than a closed
model elsewhere, and the model sits behind one port, so a customer who needs the weights inside
their own boundary changes an adapter. Our own demo calls the hosted Token Factory API and is not
air gapped, which is written here rather than dressed up.

The division of labour between the model and the deterministic code is measured, not asserted. On
twenty rules registered in advance, Nemotron scored 16, 14 and 14 over three runs against a
threshold of 14 that was written down first, while a fixed template scored 2. Asked to produce the
YAML as well as the logic, the same model scored 10, 13 and 14, because five of twenty answers were
not valid YAML. So the model writes the check and never the file around it.

## Video

Not recorded. The first five seconds are the demo surface at 375 pixels, unedited.

Beats, cut so a single beat can be re-rendered without rebuilding the whole video:

1. a real green run on a commit that breaks the rule its step claims to enforce
2. the claim against the reality, with the file and line
3. the rule in prose, and Nemotron producing the check
4. Tavily retrieving the published rule with its date, inside the receipt
5. the receipt, reproducible in eighteen months
6. the one sentence

## Feedback section

Required by the rules and separately prizeable. Written after the entry is submitted, not instead
of submitting.
