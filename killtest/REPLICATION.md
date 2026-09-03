# Replication, declared before the third draw was fetched

**2026-09-01.** During the audit the endpoint was found to be **non-deterministic at
`temperature 0`**: re-sending the r01 prompt returned a different step, and that one happened to fix
the exact `import os` bug that failed r01 in the run of record. A single draw per rule therefore
carries sampling noise the pre-registration did not anticipate.

**What is fixed, and is not up for revision:**

1. The **verdict of record is the first execution, the pre-registered one: 10/20, FAIL.** No later
   draw replaces it, whatever it says.
2. The threshold stays `>= 14/20 AND >= 6 above the template`. It does not move.
3. **Exactly three draws total.** Draw 1 (the run of record) and draw 2 are already scored, at 10
   and 13. One more is fetched, and then sampling stops, whatever the number is.
4. All three are reported together, in full, including any that would flatter the model.

The purpose is to characterise the estimator, not to re-run the test until it passes. If the three
draws straddle the threshold, that is itself the finding: the pre-registered single-draw protocol
was underpowered, and it is reported as a limitation rather than resolved in our favour.

## Result

    Draw 1, the run of record   10 / 20     results/nemotron.json
    Draw 2                      13 / 20     results/nemotron_run2.json
    Draw 3                      14 / 20     results/nemotron_run3.json

    Mean 12.3 / 20.  Threshold 14.  Touched by one draw in three, exactly, and never exceeded.

**VERDICT: unchanged. FAIL.** The run of record is draw 1 and it scored 10. Draw 3 landing exactly
on 14 is the reason the three-draw protocol was written down *before* it was fetched: had it been
sampled without that declaration, taking it would have been indistinguishable from sampling until
the test passed.

## What this actually tells us, stated straight

The spread is 10 to 14 on identical prompts, identical fixtures and identical scoring. That is a
wide band for a 20-item test, and it means **the pre-registered single-draw design was
underpowered.** It did not anticipate a `temperature 0` endpoint that returns different answers to
the same prompt.

So the honest reading is not "the model scores 10". It is: **the model's rate on these twenty rules
is somewhere around 12 of 20, and the bar of 14 sits at the very top of its range rather than
outside it.** The entry fails its own gate, and it fails it by less than the run of record suggests.

Both halves of that sentence are load-bearing, and neither is allowed to be dropped when this is
summarised. What is *not* available is a pass: a threshold reached by one draw in three, never
exceeded, is not `>= 14`.

