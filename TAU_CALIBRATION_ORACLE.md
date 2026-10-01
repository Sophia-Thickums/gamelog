# A CALIBRATION ORACLE FOR TIME-TO-CONTACT

**How to prove a monocular approach sensor is correct before trusting it, using
an oracle whose answer you can compute by hand.**

This is the piece `gamelog` was missing. The repo's thesis is *measure a real
game, not a synthetic* — and it is right, because synthetic benchmarks like
vkmark are trivial enough to be meaningless. **But "measure a real game" creates
a new problem: a real game has no ground truth.** Nobody can say what the
correct time-to-contact to that wall should have been. So a real-workload
measurement tells you something *happened* and never whether the number is
*right*.

The resolution is not to go back to synthetics. It is to use a synthetic **only
as a calibration oracle**, where the answer is derivable in closed form, and to
run the real workload on an instrument that has already passed.

---

## The oracle

For pure forward translation, each tracked feature obeys

```
|u_i| ≈ r_i / τ
```

where `r_i` is the feature's angular distance from the focus of expansion, and
`τ` is time-to-contact in frames. So every feature is an independent estimate:

```
τ_i = r_i / |u_i|
```

and the median of `τ_i` is the estimator. **The median is self-masking**: features
on the observer's own body, on moving NPCs, on the sky, and features destroyed by
video compression are all outliers, and a median does not care about outliers.
This is why the estimator needs **no mask at all** — "no rectangle to get wrong,
because there is no rectangle."

### Why a pure scale is an exact oracle

Synthesise a frame `B` by scaling frame `A` by a factor `s` about a point. A
feature at radius `r` moves outward by `(s−1)·r`. Substituting into the estimator:

```
τ_i = r_i / |u_i| = r / ((s−1)·r) = 1 / (s−1)
```

**The radius cancels.** Every feature reports the *same* τ, exactly, regardless
of where it sits in the frame. So:

| scale | exact τ | meaning |
|---|---|---|
| 1.02 | 50 | approaching |
| 1.05 | 20 | approaching faster |
| 1.10 | 10 | fast |

This is a ground truth with **zero fitting error** — not "close enough for a
benchmark," but analytically exact. Any deviation is the instrument's, and
nothing else's.

---

## What it caught, immediately

Run against a real implementation, the oracle returned:

```
scale 1.05  ->  τ = 19.842   (exact 20)
scale 1.10  ->  τ = 10.207   (exact 10)
scale 1.02  ->  τ = 48.999   (exact 50)
```

Accurate to ~1%, with the focus of expansion recovered at (0.002, 0.003) on
scaled inputs. Good enough to trust.

And then it caught two bugs that no real-game measurement could have found:

**1. A negative control that lied.** A pure horizontal *translation* (a camera
pan, no approach at all) produced `τ = 14.9` — a finite, plausible number — and
the code called it *approaching*. The oracle's negative control is what exposed
it. **This matters structurally, not just as a bug:** τ is a ratio, and a pan
drives its denominator toward meaninglessness. |u| ≈ r/τ assumes the flow is
*expansion*; a pan gives uniform flow with no radial structure, the FOE fit goes
to noise, and the per-feature quotients land on a finite number by accident of
regularisation rather than by physics. **A sensor that can only answer
"approaching" or "not approaching" will lie about pans forever. "Unclear" is the
honest third answer.**

**2. An uncertainty gate that decorated instead of deciding.** The same failed
run reported `uncertainty = 0.698` *in the same return* that said
`approaching`. The scatter was correct; the verdict ignored it. The fix is not a
better number, it is binding the number to the decision:

```
approaching  requires low uncertainty
high scatter -> "unclear"   (refuses to vote)
```

---

## The uncertainty contract

Adopted from this work, and generalisable to any sensor:

> **No sensor returns a number. Every sensor returns
> `(value, calibrated uncertainty, last-verified timestamp)`.**

A point estimate is a claim with no error bar, and an instrument that cannot
express its own doubt will be confidently wrong in exactly the conditions where
it matters most. A sensor that has been measured against an oracle can report
*how far it is from calibrated*; one that has not, cannot.

**Sub-rule, learned the hard way in the same session, about *measuring rigs*
rather than sensors:**

> **A rig that cannot read silence cannot be trusted with a signal.**
> Run the apparatus with nothing going in and confirm it reads nothing, before
> quoting any number from it.

Two false measurements in one evening came from skipping that step — a
camera-flow figure that was really the subject's own idle animation, and an
audio transfer function whose "through" recordings contained the very workload
being measured, playing through the filter under test. In the second case the
tell was a **uniform offset across every frequency band**, which is impossible
for a filter: filters have *shape*, and a flat offset means something upstream
of the thing you think you are measuring.

---

## Texture is a failure mode, not a detail

A correction worth carrying, because synthetics hide it: **the oracle uses
texture-rich frames, where every feature tracks cleanly.** Real game walls are
often painted flat. A blank concrete face gives optical flow almost nothing to
hold, and the per-feature count collapses *before* the median goes wrong — which
means a handful of features produces a confident number about nothing.

So the surviving feature count must be its own uncertainty term. Tested on both:

```
rich texture  ->  approaching   n=95   uncertainty=0.263
flat wall     ->  unreadable    n=0    uncertainty=1.0
```

The flat wall refuses to answer rather than guessing. **Instrument the
instrument.**

---

## Using it

```bash
# the oracle, against synthetic scaled frames (known answers)
python3 tau_oracle.py --self-test

# against a real workload, after the oracle passes
python3 tau_oracle.py --live
```

The contract for adopting this: **nothing votes until its known-answer test
passes.** An instrument that fails its own oracle does not get to report on the
real workload, because a real workload cannot tell you it is wrong.

---

*Built 2026-09-30. The oracle idea, the per-feature-median estimator, and the
derotate-before-τ rule came out of an exchange with Kimi (Moonshot); the
ordering bugs, the uncertainty-gate failure, and the texture case are measured
here. Both are part of the record — the exchange is what made the instrument
correct faster than I would have alone.*
