#!/usr/bin/env python3
"""
Operation GLASSHOUSE - Live Detection Exporter

Sniffs traffic on the redirector (all interfaces) for the configured C2
port, clusters raw TCP connections into check-in events per source IP
(same logic as detection/analyze_beacon.py, but streaming instead of
batch), and exposes the running statistics as Prometheus metrics.

This intentionally never looks at payload content - only connection
timing - consistent with the rest of the project's detection approach.
"""

import collections
import statistics
import time
import threading

from scapy.all import sniff, IP, TCP
from prometheus_client import start_http_server, Gauge, Counter

# --- Configuration ---------------------------------------------------------

C2_PORT = 8888
CLUSTER_WINDOW_SECONDS = 10.0   # connections within this window = one check-in event
ROLLING_WINDOW_EVENTS = 20      # how many recent check-ins to compute CV over
MIN_EVENTS_FOR_VERDICT = 5      # don't produce a verdict until we have this many intervals
SUSPICIOUS_CV_THRESHOLD = 0.4
NORMAL_CV_THRESHOLD = 0.8
METRICS_PORT = 9105

# --- Prometheus metrics -----------------------------------------------------

checkin_total = Counter(
    "glasshouse_checkin_total", "Total clustered check-in events observed", ["source"]
)
checkin_interval = Gauge(
    "glasshouse_checkin_interval_seconds", "Most recent interval between check-ins", ["source"]
)
checkin_mean_interval = Gauge(
    "glasshouse_checkin_mean_interval_seconds", "Rolling mean check-in interval", ["source"]
)
checkin_stddev = Gauge(
    "glasshouse_checkin_stddev_seconds", "Rolling standard deviation of check-in intervals", ["source"]
)
checkin_cv = Gauge(
    "glasshouse_checkin_cv", "Rolling coefficient of variation of check-in intervals", ["source"]
)
verdict_gauge = Gauge(
    "glasshouse_verdict", "Detection verdict: 1=suspicious, 0=normal, -1=insufficient data", ["source"]
)
last_seen = Gauge(
    "glasshouse_last_checkin_timestamp", "Unix timestamp of the most recent check-in", ["source"]
)

# --- State -------------------------------------------------------------------

lock = threading.Lock()
# per-source: last clustered event timestamp, and a rolling deque of event timestamps
last_event_ts = {}
event_history = collections.defaultdict(lambda: collections.deque(maxlen=ROLLING_WINDOW_EVENTS + 1))


def update_stats(source):
    """Recompute rolling mean/std/CV/verdict for a source after a new event."""
    events = list(event_history[source])
    if len(events) < 2:
        verdict_gauge.labels(source=source).set(-1)
        return

    intervals = [events[i] - events[i - 1] for i in range(1, len(events))]
    checkin_interval.labels(source=source).set(intervals[-1])

    if len(intervals) < MIN_EVENTS_FOR_VERDICT:
        verdict_gauge.labels(source=source).set(-1)
        return

    mean = statistics.mean(intervals)
    std = statistics.pstdev(intervals)
    cv = (std / mean) if mean > 0 else 0

    checkin_mean_interval.labels(source=source).set(mean)
    checkin_stddev.labels(source=source).set(std)
    checkin_cv.labels(source=source).set(cv)

    if cv < SUSPICIOUS_CV_THRESHOLD:
        verdict_gauge.labels(source=source).set(1)
    elif cv > NORMAL_CV_THRESHOLD:
        verdict_gauge.labels(source=source).set(0)
    else:
        verdict_gauge.labels(source=source).set(0.5)  # ambiguous band


def handle_packet(pkt):
    if not (IP in pkt and TCP in pkt):
        return
    tcp = pkt[TCP]
    if tcp.dport != C2_PORT:
        return
    # Only count new connection attempts (SYN, not SYN-ACK/data) to approximate
    # "one record per TCP connection", same as the offline analyzer.
    if tcp.flags != "S":
        return

    source = pkt[IP].src
    ts = float(pkt.time)

    with lock:
        prev = last_event_ts.get(source)
        if prev is not None and (ts - prev) <= CLUSTER_WINDOW_SECONDS:
            # part of the same check-in event (e.g. multiple TCP connections
            # opened within the same beacon check-in) - ignore
            return

        last_event_ts[source] = ts
        event_history[source].append(ts)
        checkin_total.labels(source=source).inc()
        last_seen.labels(source=source).set(ts)
        update_stats(source)


def main():
    start_http_server(METRICS_PORT)
    print(f"[*] GLASSHOUSE exporter listening on :{METRICS_PORT}/metrics")
    print(f"[*] Sniffing tcp port {C2_PORT} on all interfaces...")
    # iface="any" uses Linux cooked capture across every interface in this
    # container's network namespace (net-offense + net-c2 + net-detection).
    sniff(iface="any", filter=f"tcp port {C2_PORT}", prn=handle_packet, store=False)


if __name__ == "__main__":
    main()
