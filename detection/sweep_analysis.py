#!/usr/bin/env python3
"""
Operation GLASSHOUSE - Jitter Sweep Analysis

Takes a directory of pcaps named jitter_<NN>.pcap (one per jitter_sweep.sh
run) and computes the same clustered check-in / CV statistics used in
analyze_beacon.py for each one, then prints a summary table and (if
matplotlib is available) saves a chart of CV vs. configured jitter with the
0.4 detection threshold marked.

Usage:
    python3 sweep_analysis.py captures/sweep/
"""

import sys
import re
import glob
import os

import numpy as np
import pandas as pd
from scapy.all import rdpcap, IP, TCP

TARGET_PORT = 8888
CLUSTER_WINDOW = 10.0
SUSPICIOUS_THRESHOLD = 0.4


def extract_connections(pcap_path, target_port=TARGET_PORT):
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
    return sorted(connections.values())


def cluster_checkins(timestamps, window=CLUSTER_WINDOW):
    if not timestamps:
        return []
    timestamps = sorted(timestamps)
    clusters = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts - clusters[-1] > window:
            clusters.append(ts)
    return clusters


def analyze_pcap(pcap_path):
    timestamps = extract_connections(pcap_path)
    checkins = cluster_checkins(timestamps)
    if len(checkins) < 3:
        return None
    intervals = np.diff(checkins)
    mean = float(np.mean(intervals))
    std = float(np.std(intervals))
    cv = (std / mean) if mean > 0 else 0.0
    return {
        "raw_connections": len(timestamps),
        "checkin_events": len(checkins),
        "mean_interval": mean,
        "std_interval": std,
        "cv": cv,
        "verdict": "SUSPICIOUS" if cv < SUSPICIOUS_THRESHOLD else "normal",
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sweep_analysis.py <captures_dir>")
        sys.exit(1)

    captures_dir = sys.argv[1]
    pcaps = sorted(glob.glob(os.path.join(captures_dir, "jitter_*.pcap")))

    if not pcaps:
        print(f"[!] No jitter_*.pcap files found in {captures_dir}")
        sys.exit(1)

    rows = []
    for pcap_path in pcaps:
        m = re.search(r"jitter_(\d+)\.pcap$", os.path.basename(pcap_path))
        jitter = int(m.group(1)) if m else None
        print(f"[*] Analyzing {pcap_path} (jitter={jitter}s)...")
        result = analyze_pcap(pcap_path)
        if result is None:
            print(f"    [!] Not enough check-ins in this capture, skipping.")
            continue
        result["jitter"] = jitter
        result["file"] = os.path.basename(pcap_path)
        rows.append(result)

    if not rows:
        print("[!] No usable captures found.")
        sys.exit(1)

    df = pd.DataFrame(rows).sort_values("jitter")
    df = df[["jitter", "file", "raw_connections", "checkin_events",
              "mean_interval", "std_interval", "cv", "verdict"]]

    print("\n=== Jitter Sweep Summary ===\n")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    csv_path = os.path.join(captures_dir, "sweep_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[*] Summary written to {csv_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df["jitter"], df["cv"], marker="o", label="Observed CV")
        ax.axhline(SUSPICIOUS_THRESHOLD, color="red", linestyle="--",
                   label=f"Detection threshold ({SUSPICIOUS_THRESHOLD})")
        ax.set_xlabel("Configured jitter (seconds)")
        ax.set_ylabel("Coefficient of Variation")
        ax.set_title("Operation GLASSHOUSE - Detection sensitivity vs. jitter")
        ax.legend()
        ax.grid(True, alpha=0.3)
        chart_path = os.path.join(captures_dir, "sweep_cv_vs_jitter.png")
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        print(f"[*] Chart written to {chart_path}")
    except ImportError:
        print("[!] matplotlib not installed - skipping chart "
              "(pip install matplotlib --break-system-packages)")


if __name__ == "__main__":
    main()
