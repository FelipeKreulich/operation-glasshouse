# 05 — Results

## Summary

The detection pipeline built in [`04-defense-detection.md`](04-defense-detection.md)
was validated against two pcap captures from the same redirector chokepoint:

1. **Beacon traffic** — the evasive Sliver beacon (`GORGEOUS_ABDOMEN`),
   configured with `--seconds 45 --jitter 20` and the `glasshouse` malleable
   C2 profile.
2. **Control traffic** — a synthetic "normal" traffic generator, making
   HTTP requests to the same redirector endpoint at uniformly random
   intervals between 5 and 185 seconds, from an isolated container with the
   beacon's `target` container stopped (to guarantee no cross-contamination
   between the two sources).

Both were captured with `tcpdump` on the `redirector` container and analyzed
with the same unmodified `detection/analyze_beacon.py` script.

## Comparison

| Metric | Beacon traffic | Control traffic |
|---|---|---|
| Source | `target` (GORGEOUS_ABDOMEN beacon) | isolated `control-source` container |
| Capture duration | ~45 min | ~15 min |
| Raw TCP connections | 98 | 20 |
| Clustered check-in events | 49 | 17 |
| Mean interval | 55.29s | 56.06s |
| Std deviation | 5.27s | 46.33s |
| **Coefficient of Variation (CV)** | **0.095** | **0.826** |
| Verdict (threshold: CV < 0.4) | **SUSPICIOUS** | Likely normal traffic |

## Why this is the result that matters

The mean interval is nearly identical between the two samples (55.29s vs.
56.06s) — if the detector were keying off interval *length*, it would have
no basis to tell them apart. What separates them is entirely the
**regularity** of the spacing.

- The beacon's jitter was configured with a theoretical spread of 25-65s
  (45s ± 20s), but the *observed* spread across 49 real check-ins was far
  tighter — only ±5.27s of standard deviation. Jitter, as implemented,
  narrows the practical variance far more than the configured range would
  suggest.
- The control traffic's intervals were drawn from a uniform distribution
  over 5-185s and, as expected, produced a standard deviation close to the
  mean itself (CV = 0.826), landing comfortably in the "likely human/organic"
  range (CV > 0.8) defined in the detection methodology.

This confirms the CV-based approach is discriminative, not just
alarm-prone: it correctly separates two traffic sources with almost
identical average check-in timing, based purely on how consistent that
timing is.

## Caveats

- **Sample size asymmetry.** The control capture ran for a shorter window
  (~15 min vs. ~45 min) and produced fewer clustered events (17 vs. 49).
  The result is still well outside the ambiguous zone for both samples, so
  this doesn't change the verdict, but a larger control sample would give a
  tighter confidence interval on the control CV.
- **Single beacon configuration.** Only one jitter/interval setting
  (45s ± 20s) was tested against one control profile (uniform 5-185s). A
  more thorough validation would sweep across multiple jitter ratios to
  find the point where detection confidence starts to degrade — i.e. how
  much jitter an operator would need to configure before the CV creeps
  into the ambiguous 0.4-0.8 band.
- **Synthetic control traffic.** The "normal" sample was a scripted
  `wget` loop with randomized sleep, not real human browsing or production
  service traffic. It's a reasonable stand-in for establishing that the
  detector isn't simply always positive, but it isn't a substitute for
  validating against real background traffic in a production network.

## Conclusion

Within the scope of this lab: a timing-only, payload-blind detector using
the coefficient of variation of clustered check-in intervals successfully
distinguished a jittered Sliver beacon (CV = 0.095) from synthetic
random-interval traffic (CV = 0.826), despite both having almost identical
average check-in spacing. This supports the core premise of the project —
that deliberate jitter, within a reasonable configured range, does not by
itself defeat timing-based beacon detection.
