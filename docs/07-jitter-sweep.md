# 07 — Jitter Sensitivity Sweep (methodology)

## Objective

`05-results.md` showed that a single jitter configuration (45s ± 20s) was
still detected (CV = 0.095, well under the 0.4 threshold). The open
question: **how much jitter would an operator need to configure before the
CV crosses into the ambiguous or "normal" band, and the detector stops
flagging it?**

This doc describes the methodology and tooling for that sweep. Captures
have not been run yet — this is the prepared method, to be executed as a
follow-up session.

## Method

For a fixed base interval (`--seconds 45`), generate a beacon for each
jitter value in a chosen set, capture traffic for a fixed window, and
compute the CV the same way as the rest of the project (clustered check-in
events, 10s clustering window).

Suggested jitter values to test: **0, 10, 20, 30, 40 seconds**. This spans
from no jitter at all (expected to produce a near-zero CV) through jitter
roughly equal to the base interval (expected to push CV toward, and
possibly past, the 0.4 threshold).

Each configuration needs enough check-ins for a statistically meaningful
CV — ~25 minutes per capture at a 45s interval yields roughly 30-35
check-ins, consistent with the sample sizes already validated in
`05-results.md` (49 events for the original beacon, 17 for the control
traffic).

## Running it

```bash
cd ~/operation-glasshouse/detection
chmod +x jitter_sweep.sh
./jitter_sweep.sh
```

The script walks through each configured jitter value, printing the exact
`generate beacon` command to paste into the Sliver console for that
iteration (beacon generation itself isn't automated — there's no safe way
to script the interactive console without the gRPC API), then handles
swapping the binary into `target/`, rebuilding, timing the capture, and
naming the output file consistently (`jitter_00.pcap`, `jitter_10.pcap`,
...) under `detection/captures/sweep/`.

**Important:** stop the previous beacon's `target` container (or at least
confirm the old implant isn't still checking in — see the troubleshooting
note in `04-defense-detection.md` about `beacons rm` not killing the actual
process) before starting the next configuration's capture, or the two will
contaminate each other the same way the early control-traffic captures did.
The script pauses and reminds you to do this between configs.

## Analyzing the results

```bash
python3 sweep_analysis.py captures/sweep/
```

This produces:
- A summary table (jitter, check-in count, mean/std interval, CV, verdict)
  printed to the console and written to `captures/sweep/sweep_summary.csv`
- A chart (`captures/sweep/sweep_cv_vs_jitter.png`) plotting CV against
  configured jitter, with the 0.4 detection threshold marked, if
  `matplotlib` is installed (`pip install matplotlib --break-system-packages`
  inside the detection venv if missing)

## Expected outcome (hypothesis, to be confirmed)

Based on the existing beacon implementation's behavior (where a configured
±20s jitter produced an observed std. deviation of only 5.27s — much
tighter than the configured range), the hypothesis is that CV will rise
roughly linearly with jitter but stay under the 0.4 threshold for most of
the tested range, only approaching or crossing it as jitter approaches or
exceeds the base interval itself (i.e. jitter ≈ 40-45s against a 45s base).
If that holds, it would suggest this detection method is robust against
"reasonable" jitter configurations and only defeated by jitter large enough
to meaningfully change the operator's own check-in cadence — a real
operational cost for the attacker, not a free evasion.

This section should be replaced with the actual measured results (and this
hypothesis confirmed, refined, or rejected) once the sweep has been run.
