#!/usr/bin/env python3
"""plot_waveform.py — parse buck_plant_tb.vcd and plot iL / vC / q.

Usage:  python plot_waveform.py [vcd_path] [out_png]
Defaults: buck_plant_tb.vcd  →  buck_plant_waveform.png
"""
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt

VCD   = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("buck_plant_tb.vcd")
OUT   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("buck_plant_waveform.png")

TARGETS = {"iL", "vC", "q", "duty_pct"}

TS_UNIT = {"s": 1, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15}


def parse_vcd(path):
    text = path.read_text()

    # Timescale → seconds-per-tick
    m = re.search(r"\$timescale\s+(\d+)\s*([a-z]+)\s*\$end", text)
    mult, unit = int(m.group(1)), m.group(2)
    sec_per_tick = mult * TS_UNIT[unit]

    # Variable declarations:  $var <type> <width> <id> <name>  $end
    id2name = {}
    id2width = {}
    for m in re.finditer(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+)", text):
        width, sid, name = int(m.group(1)), m.group(2), m.group(3)
        if name in TARGETS:
            id2name[sid] = name
            id2width[sid] = width

    body = text.split("$enddefinitions $end", 1)[1]

    data = {n: [] for n in TARGETS}
    t = 0
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "#":
            t = int(line[1:])
        elif line[0] in "bB":                      # vector change: b<bits> <id>
            bits, sid = line[1:].split()
            if sid in id2name:
                v = int(bits, 2)
                w = id2width[sid]
                if v & (1 << (w - 1)):             # sign-extend
                    v -= 1 << w
                data[id2name[sid]].append((t, v))
        elif line[0] in "01xzXZ":                  # scalar change: <v><id>
            sid = line[1:]
            if sid in id2name:
                v = int(line[0]) if line[0] in "01" else 0
                data[id2name[sid]].append((t, v))

    return data, sec_per_tick


def to_waveform(samples, scale=1.0):
    """List of (tick, raw) → (seconds-list, value-list) scaled."""
    if not samples:
        return [], []
    ts, vs = zip(*samples)
    return list(ts), [v * scale for v in vs]


def main():
    if not VCD.exists():
        sys.exit(f"VCD not found: {VCD}  — run the simulation first.")

    data, sec_per_tick = parse_vcd(VCD)
    Q_SCALE = 1.0 / (1 << 24)  # Q8.24 → real

    iL_t, iL_v = to_waveform(data["iL"], Q_SCALE)
    vC_t, vC_v = to_waveform(data["vC"], Q_SCALE)
    q_t,  q_v  = to_waveform(data["q"])
    d_t,  d_v  = to_waveform(data["duty_pct"])

    # Convert ticks → ms for plotting
    to_ms = lambda ticks: [t * sec_per_tick * 1e3 for t in ticks]
    iL_t, vC_t, q_t, d_t = map(to_ms, (iL_t, vC_t, q_t, d_t))

    # Expected steady-state Vout for annotation
    VIN, R_L, R_LOAD = 24.0, 0.05, 6.0
    vout = lambda d: VIN * d * 0.01 / (1 + R_L / R_LOAD)

    fig, (ax_v, ax_i, ax_q) = plt.subplots(
        3, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1]},
    )
    fig.suptitle("Buck plant — open-loop verification  (Vin=24 V, L=100 µH, C=100 µF, R_L=50 mΩ, R_load=6 Ω, f_sw=100 kHz)",
                 fontsize=11)

    # --- vC
    ax_v.plot(vC_t, vC_v, color="#1F77B4", linewidth=0.9, label="v_C (output)")
    ax_v.axhline(vout(50), color="#2CA02C", linestyle="--", linewidth=1,
                 label=f"target @ d=50% = {vout(50):.3f} V")
    ax_v.axhline(vout(75), color="#D62728", linestyle="--", linewidth=1,
                 label=f"target @ d=75% = {vout(75):.3f} V")
    ax_v.set_ylabel("v_C  [V]")
    ax_v.grid(True, alpha=0.3)
    ax_v.legend(loc="lower right", fontsize=9)

    # --- iL
    ax_i.plot(iL_t, iL_v, color="#B8860B", linewidth=0.8)
    ax_i.set_ylabel("i_L  [A]")
    ax_i.grid(True, alpha=0.3)

    # --- q
    ax_q.step(q_t, q_v, where="post", color="#333333", linewidth=0.6)
    ax_q.set_ylabel("q  (PWM)")
    ax_q.set_xlabel("time  [ms]")
    ax_q.set_ylim(-0.2, 1.2)
    ax_q.set_yticks([0, 1])
    ax_q.grid(True, alpha=0.3)

    # Mark duty step events on every axis
    for i in range(1, len(d_t)):
        if d_v[i] != d_v[i - 1]:
            for ax in (ax_v, ax_i, ax_q):
                ax.axvline(d_t[i], color="#888888", linestyle=":", linewidth=0.8)
            ax_v.text(d_t[i], ax_v.get_ylim()[1] * 0.95,
                      f"  d → {d_v[i]}%", color="#555555", fontsize=9,
                      ha="left", va="top")

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    plt.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
