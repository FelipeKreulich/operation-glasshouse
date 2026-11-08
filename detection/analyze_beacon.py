#!/usr/bin/env python3
"""
Operation GLASSHOUSE - Beacon Detection Engine
Analyzes a pcap file to detect beaconing behavior based on
connection interval regularity (low coefficient of variation).
"""

import sys
from scapy.all import rdpcap, IP, TCP
import pandas as pd
import numpy as np

def extract_connections(pcap_path, target_port=8888):
    """
    Extract one record per TCP connection (identified by src_ip + src_port),
    using the timestamp of the first packet (SYN) as the connection's start time.
    """
    packets = rdpcap(pcap_path)
    connections = {}

    for pkt in packets:
        if IP in pkt and TCP in pkt:
            tcp = pkt[TCP]
            if tcp.dport == target_port:
                conn_id = (pkt[IP].src, tcp.sport)
                ts = float(pkt.time)
                if conn_id not in connections or ts < connections[conn_id]:
                    connections[conn_id] = ts

    records = [
        {"src_ip": src_ip, "src_port": src_port, "start_time": start_time}
        for (src_ip, src_port), start_time in connections.items()
    ]

    return pd.DataFrame(records)

def cluster_checkins(timestamps, window=10.0):
    """
    Group connection timestamps that happen within `window` seconds of each
    other into a single check-in event, represented by the first timestamp
    in each cluster. This accounts for beacons that open multiple TCP
    connections per check-in (e.g. separate request/response connections).
    """
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

def analyze_intervals(df, src_ip):
    """Compute interval statistics between successive beacon check-ins."""
    conn_df = df[df["src_ip"] == src_ip].sort_values("start_time")

    if len(conn_df) < 3:
        print(f"[!] Not enough connections from {src_ip} to analyze ({len(conn_df)} found).")
        return

    raw_timestamps = conn_df["start_time"].values
    checkin_timestamps = cluster_checkins(raw_timestamps, window=10.0)

    if len(checkin_timestamps) < 3:
        print(f"[!] Not enough distinct check-ins after clustering ({len(checkin_timestamps)} found).")
        return

    intervals = np.diff(checkin_timestamps)

    mean_interval = np.mean(intervals)
    std_interval = np.std(intervals)
    cv = std_interval / mean_interval if mean_interval > 0 else 0

    print(f"\n=== Analysis for {src_ip} ===")
    print(f"Raw TCP connections: {len(conn_df)}")
    print(f"Clustered check-in events: {len(checkin_timestamps)}")
    print(f"Intervals between check-ins (s): {np.round(intervals, 2)}")
    print(f"Mean interval: {mean_interval:.2f}s")
    print(f"Std deviation: {std_interval:.2f}s")
    print(f"Coefficient of Variation (CV): {cv:.3f}")

    if cv < 0.4:
        print("Verdict: SUSPICIOUS - low variability suggests automated beaconing")
    else:
        print("Verdict: Likely normal traffic - high variability")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_beacon.py <pcap_file>")
        sys.exit(1)

    pcap_path = sys.argv[1]
    print(f"[*] Loading {pcap_path}...")
    df = extract_connections(pcap_path)

    if df.empty:
        print("[!] No relevant connections found in capture.")
        sys.exit(1)

    print(f"[*] Found {len(df)} distinct TCP connections on port 8888.")
    unique_sources = df["src_ip"].unique()
    print(f"[*] Unique source IPs: {list(unique_sources)}")

    for src_ip in unique_sources:
        analyze_intervals(df, src_ip)

if __name__ == "__main__":
    main()
