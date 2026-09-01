# The kill test

A pre-registered test of one question, run on 2026-09-01 before any product code was written:

> Given a rule written in prose, can Nemotron produce the CI check that enforces it — well enough
> to beat a fixed template that only knows how to grep?

If the answer is no, the sponsor's model is not load-bearing and the entry does not stand in its
planned form. The rules, the fixtures, the threshold and the verdict rule were all written down
first. **The threshold did not move after the numbers appeared.**

## The result

    Oracle:    20 / 20     calibration, not a competitor
    Nemotron:  10 / 20
    Template:   2 / 20
    Difference: 8

    Threshold, written first:  >= 14/20  AND  >= 6 above the template
                               >= 14  ->  NO   (10)
                               >= 6   ->  YES  (8)

    VERDICT: FAIL. Both halves were required.

**The endpoint is not deterministic at `temperature 0`.** Re-sending the same r01 prompt returned a
different step — one that fixed the very `import os` bug that had failed it. So a single draw per
rule carries sampling noise the pre-registration never anticipated. Before a third draw was fetched,
`REPLICATION.md` fixed the protocol in writing: exactly three draws, the verdict stays with the
first whatever the others say, all three reported.

    Draw 1, the run of record   10 / 20
    Draw 2                      13 / 20
    Draw 3                      14 / 20
    Mean 12.3.  The threshold of 14 is touched by one draw in three, exactly, and never exceeded.

The verdict does not change, but the reading does, and both halves of this sentence travel together:
**the entry fails its own gate, and it fails by less than the run of record suggests.** The honest
claim is not "the model scores 10" but "the model runs at roughly 12 of 20, and the bar sits at the
top of its range rather than outside it". A pass is not available: a threshold reached once in three
draws is not `>= 14`. Eight rules pass in all three draws; four never pass at all.

Model `nvidia/nemotron-3-super-120b-a12b` through `https://api.tokenfactory.nebius.com/v1`, at
`temperature 0`. In the run of record all 20 calls returned HTTP 200 with `finish_reason=stop` and
nothing was truncated; one call in draw 2 (`r20`) hit `finish_reason=length`, and that is why it is
named here rather than buried. Raw responses: `results/nemotron_raw/`, `_run2/`, `_run3/`.

## How to reproduce it

```bash
python3 harness.py --producer oracle
python3 harness.py --producer template
python3 harness.py --producer nemotron
```

The harness runs on Ubuntu 22.04. Regenerating the model's answers needs a Nebius key and
`python producers/nemotron_fetch.py`; scoring does not, because the responses are cached.

## What "executed" means here, exactly

Each produced step is parsed as YAML, its `run:` body is executed by `bash` against two frozen
fixtures, and the exit codes are compared. A rule scores 1 only if the body **exits non-zero on the
violating fixture and zero on the clean one**. Either alone scores 0. A script decides, not a person.

**This is not a hosted GitHub Actions run**, and it is never presented as one. It measures whether a
model can turn prose into a check that actually fires, which is the claim the entry rested on.

## Why the oracle exists

I wrote all twenty checks by hand first, as a third producer, and the instrument was not allowed to
score anything until those hand-written checks returned **20/20**. Without that, a 10/20 cannot tell
"Nemotron failed" apart from "our fixtures are unanswerable".

It earned its place. The oracle fell below 20/20 twice, and both times the instrument was at fault,
not the model: a hand-rolled YAML reader that truncated bodies, and a checkout with no base branch
even though the contract promised one. Both are recorded in `../../../TRAPS.md`.

## How Nemotron failed

Five of the ten failures are not valid YAML at all — `r02 r03 r08 r10 r12` — mostly column-0 lines
inside a block scalar and stray heredoc terminators. A step that will not parse will not run on a
real runner either.

Four are execution bugs: `r01` uses `os.environ` without importing `os`; `r04` breaks on `[[ =~ ]]`
syntax; `r06` writes `'$GITHUB_EVENT_PATH'` inside a quoted heredoc, so it never expands; and `r14`
ends its pipeline with `| head -n1 >/dev/null`, which makes the exit status always 0 — **a check
that can never fail.** That last one is precisely the defect this project exists to find, produced
by the model that was supposed to enforce against it.

The tenth, `r20`, is our fixture's fault and is not charged to the model. The rule says "a
corresponding test directory" without naming a convention; the model asked for `test/`, the fixture
provides `tests/`, and both readings are reasonable. It was **not** repaired after the fact, because
fixing a fixture in the model's favour once the score is known is exactly the move that deserves
attack. Even crediting it, 11 < 14.

## The template is not a straw man

Its source is `producers/template.py` and all twenty of its outputs are in `results/template.json`,
so the baseline can be judged directly. It gets the identical contract, the identical rule text, and
it reads the rule's own polarity so a prohibition demands absence. It scores 2/20 honestly, on the
two rules where the mere presence or absence of a literal **is** the check: `continue-on-error: true`
and `LICENSE`. What it cannot do is give a check semantics, which is the whole point.

The 8-point gap cleared its half of the threshold comfortably. What failed was the absolute level.

## Files

| Path | What it is |
|---|---|
| `CONTRACT.md` | the execution contract, handed verbatim and identically to every producer |
| `rules.json` | the 20 rules, Greek original and the frozen English given to producers |
| `fixtures.json` | the 40 fixtures, declarative; materialised into a temp git checkout per run |
| `harness.py` | materialise, execute, score. The verdict is decided here |
| `producers/oracle/` | 20 hand-written steps, calibration only |
| `producers/template.py` | the fixed skeleton baseline |
| `producers/nemotron_fetch.py` | calls Token Factory, writes `results/nemotron_raw/` |
| `producers/nemotron.py` | offline cache reader; the API key never reaches the harness |
| `results/materialised/` | every fixture tree as actually built, so the merge is inspectable |
| `REPLICATION.md` | the three-draw protocol, written down before the third draw was fetched |
