# 04 — Defense: Beacon Detection

## Objective

Detect the Sliver beacon traffic generated in the offensive phase (see
`03-offense-c2-setup.md`) purely from network-level metadata — connection
timing — without inspecting payload content or relying on the malleable C2
profile being known in advance. The goal is to show that jittered beaconing,
even when deliberately randomized, remains statistically distinguishable
from organic traffic.

## Approach

Beacon traffic has a structural property that human-driven or legitimate
automated traffic usually lacks: **check-ins recur at intervals drawn from a
narrow distribution**, even when jitter is applied. A human browsing a site,
or a service polling on an irregular schedule, produces intervals with much
higher relative variance.

The detection metric used is the **Coefficient of Variation (CV)**:

CV = standard_deviation(intervals) / mean(intervals)

- **CV < 0.4** → intervals are tightly clustered around the mean →
  suggestive of automated, timer-driven beaconing.
- **CV > 0.8** → intervals are highly dispersed → more consistent with
  organic/human traffic.
- Values in between are ambiguous and would need a second signal (e.g.
  payload size regularity, destination entropy) in a production detector.

This threshold is a simplification for this lab — a real detection engine
would tune it against a labeled dataset rather than using a fixed cutoff.

## Capture setup

Traffic was captured directly on the `redirector` container, which sits
between the `target` (beacon) and `sliver-c2`:

```
docker exec redirector tcpdump -i eth0 -w /captures/beacon_traffic.pcap port 8888
```

Capture ran for roughly 45 minutes against the active beacon
(`GORGEOUS_ABDOMEN`, interval `45s ± 20s jitter`), producing a 162 KB pcap
with 914 raw packets.

## Analysis pipeline — detection/analyze_beacon.py

The script was built incrementally, and two methodological errors surfaced
along the way that are worth documenting, since they are the kind of mistake
that silently produces a wrong verdict rather than an obvious crash.

### Iteration 1 — per-packet intervals (wrong)

The first version measured the time delta between every captured packet on
port 8888, grouped by source IP. This is wrong because a single beacon
check-in is not one packet — it's a full TCP handshake plus HTTP
request/response (SYN, ACK, PSH, FIN, ...), all landing within milliseconds
of each other. Measuring packet-to-packet intervals mixes these near-zero
intra-check-in gaps with the real ~45-65s inter-check-in gap, which inflates
the standard deviation and pushes the CV well above the detection threshold
— a false negative.

Result: CV ≈ 3.36, verdict "likely normal traffic." Wrong.

### Iteration 2 — per-connection intervals (still contaminated)

The second version grouped packets by TCP connection (source IP + source
port), using the first packet of each connection as its timestamp. This is
closer, but the beacon in this setup opens more than one TCP connection per
logical check-in (observed as alternating ~0s and ~55s intervals), so
roughly half the "connections" still landed right next to each other in
time.

Result: CV ≈ 1.02, verdict "likely normal traffic." Still wrong.

### Iteration 3 — clustered check-ins (correct)

The fix: cluster connection start-times that fall within a small window (10
seconds) of each other, treating each cluster as one check-in event
regardless of how many underlying TCP connections it produced. Intervals are
then computed between cluster timestamps, not between raw packets or raw
connections.

```
def cluster_checkins(timestamps, window=10.0):
    timestamps = sorted(timestamps)
    clusters = []
    current_cluster = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts - current_cluster[-1] <= window:
            current_cluster.append(ts)
        else:
            clusters.append(current_cluster[0])
            current_cluster = [ts]
    clusters.append(current_cluster[0])
    return clusters
```

The 10-second window is a parameter choice, not a derived constant — it
works for this beacon's interval (45-65s) but would need re-tuning for a
much faster or slower beacon. A more robust version would compute this
window adaptively (e.g. some fraction of the minimum expected interval).

## Results

| Metric | Value |
|---|---|
| Raw packets captured | 914 |
| Raw TCP connections (port 8888) | 98 |
| Clustered check-in events | 49 |
| Mean interval | 55.29s |
| Std deviation | 5.27s |
| Coefficient of Variation (CV) | 0.095 |
| Verdict | SUSPICIOUS |

A CV of 0.095 is far below the 0.4 threshold. Even though the beacon was
configured with a jitter window of ±20 seconds around a 45-second base
interval (a theoretical range of roughly 25-65s), the observed standard
deviation across 49 real check-ins was only 5.27 seconds — the random jitter
narrowed the practical spread far more than it widened it, which is
consistent with how Sliver's jitter implementation samples delay rather than
producing a uniform spread across the full configured range.

## Limitations and next steps

- **No control sample.** All conclusions so far are based only on known
  malicious traffic. The method hasn't yet been validated against a known
  "normal" traffic sample to confirm it doesn't also flag organic traffic as
  suspicious. A follow-up capture (e.g. a client polling at randomized
  human-like intervals, or real browser traffic) is needed to measure false
  positive rate.
- **Single beacon configuration tested.** Only one jitter/interval
  combination (45s ± 20s) was analyzed. Detection sensitivity across
  different jitter settings (e.g. very low intervals, very high jitter
  ratios) is not yet characterized.
- **Clustering window is a manual parameter.** It was chosen empirically
  (10s) and happened to work cleanly for this beacon; a production detector
  would need this derived automatically or validated against edge cases
  (e.g. two genuinely independent, overlapping sessions from the same
  source IP).
- **IP `172.18.0.3` dropped out between captures.** An earlier capture
  showed two source IPs; this one showed only `172.18.0.2`. Worth
  confirming this reflects an expected change in which container is
  initiating traffic, rather than packet loss in the capture (the pcap
  reported a truncation warning).

## Files

- `detection/analyze_beacon.py` — capture analysis script
- `detection/captures/beacon_traffic.pcap` — raw capture used for this
  analysis
