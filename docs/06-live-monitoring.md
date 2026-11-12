# 06 — Live Monitoring (Prometheus + Grafana)

## Objective

Turn the offline, one-off analysis from `04-defense-detection.md` into a
live dashboard: watch check-in regularity and detection verdicts update in
real time as the beacon runs, instead of capturing a pcap and running a
script by hand afterwards.

## Architecture

```
  [ target ] --beacon--> [ redirector ] --proxy_pass--> [ sliver-c2 ]
                              |
                     (same container, new)
                              |
                      [ exporter.py ]  --sniffs tcp/8888 on all ifaces
                              |
                       :9105/metrics
                              |
                        [ prometheus ]  --scrapes every 10s
                              |
                         [ grafana ]  --dashboard on :3000
```

The live detector runs **inside the `redirector` container itself**, not as
a separate sidecar. This is a deliberate choice, not a shortcut: a Docker
bridge network behaves like a real switch, not a hub — a third container
attached to the same network will **not** see unicast traffic between two
other containers (e.g. `target` <-> `redirector`) just by sniffing its own
interface. The only place that traffic is actually visible without extra
tricks (port mirroring, ARP manipulation) is on an endpoint of the
conversation itself — which is exactly why the manual `tcpdump` captures in
`04-defense-detection.md` were run via `docker exec redirector tcpdump ...`
in the first place. The exporter just automates and streams what that
manual process was already doing.

## What the exporter does

`monitoring/exporter/exporter.py` sniffs `tcp port 8888` across all of the
redirector's interfaces (Linux "any" / cooked capture, same idea as
`tcpdump -i any`), and for each **new** TCP connection (SYN packet) applies
the same clustering logic as `analyze_beacon.py`: connections from the same
source IP within a 10-second window are treated as one check-in event, not
several.

For each source IP it maintains a rolling window of the last 20 check-in
events and exposes:

| Metric | Meaning |
|---|---|
| `glasshouse_checkin_total` | Counter of clustered check-in events |
| `glasshouse_checkin_interval_seconds` | Most recent interval between check-ins |
| `glasshouse_checkin_mean_interval_seconds` | Rolling mean interval |
| `glasshouse_checkin_stddev_seconds` | Rolling standard deviation |
| `glasshouse_checkin_cv` | Rolling coefficient of variation |
| `glasshouse_verdict` | `1` = suspicious (CV < 0.4), `0` = normal (CV > 0.8), `0.5` = ambiguous, `-1` = not enough data yet |
| `glasshouse_last_checkin_timestamp` | Unix timestamp of last check-in (used as an "active source" proxy) |

All labeled by `source` (the source IP).

## Why "active sources" instead of querying Sliver directly for sessions

A more complete dashboard would show actual Sliver beacon/session metadata
(name, hostname, OS) pulled from the C2 server itself via its gRPC API. That
API is mTLS-authenticated and would need its own client certs wired into
the monitoring stack — a reasonable next step, but out of scope here. As a
stand-in, "how many source IPs have checked in within the last 2 minutes"
(`glasshouse_last_checkin_timestamp`) is used as a proxy for "active C2
sessions," which is accurate enough for a closed single-beacon lab but
wouldn't distinguish between two concurrent beacons from the same IP.

## Cold start

`glasshouse_verdict` reports `-1` (insufficient data) until at least 5
intervals (6 check-in events) have been observed for a given source. With a
~45-65s beacon interval, expect 5-8 minutes before the dashboard produces a
verdict after startup or after a new source first appears.

## Using it

```bash
docker compose up -d --build
```

- Prometheus: http://<pi-ip>:9090 (raw metrics / ad-hoc queries)
- Grafana: http://<pi-ip>:3000 (login: `admin` / `glasshouse`, set in
  `docker-compose.yml` — change this before exposing the Pi beyond your own
  network)

The dashboard **Operation GLASSHOUSE — Live Detection** is provisioned
automatically on first boot (no manual dashboard import needed).

## Limitations

- Single detection signal (timing/CV only) — no payload, destination
  entropy, or TLS fingerprint correlation.
- "Active sources" is a coarse proxy for session count, as noted above.
- The rolling window (last 20 events) means the dashboard reacts slowly to
  a beacon that just changed its interval/jitter configuration — by design,
  since a shorter window would make the CV noisier.
