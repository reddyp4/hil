#!/usr/bin/env python3
"""plot_closed.py — closed-loop waveform from buck_closed_tb.vcd.

Shows voltage tracking (vC vs v_ref), inner current tracking (iL vs i_ref),
and the controller's duty output.

Usage:  python plot_closed.py [vcd_path] [out_png]
"""
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt

VCD = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("buck_closed_tb.vcd")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("buck_closed_waveform.png")

TARGETS = {"iL", "vC", "q", "v_ref", "i_ref", "duty"}

TS_UNIT = {"s": 1, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15}


def parse_vcd(path):
    text = path.read_text()
    m = re.search(r"\$timescale\s+(\d+)\s*([a-z]+)\s*\$end", text)
    sec_per_tick = int(m.group(1)) * TS_UNIT[m.group(2)]

    id2name, id2width = {}, {}
    for m in re.finditer(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+)", text):
        width, sid, name = int(m.group(1)), m.group(2), m.group(3)
        if name in TARGETS and sid not in id2name:
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
        elif line[0] in "bB":
            bits, sid = line[1:].split()
            if sid in id2name:
                v = int(bits, 2)
                w = id2width[sid]
                if v & (1 << (w - 1)):
                    v -= 1 << w
                data[id2name[sid]].append((t, v))
        elif line[0] in "01xzXZ":
            sid = line[1:]
            if sid in id2name:
                v = int(line[0]) if line[0] in "01" else 0
                data[id2name[sid]].append((t, v))
    return data, sec_per_tick


def unpack(samples, scale=1.0):
    if not samples:
        return [], []
    ts, vs = zip(*samples)
    return list(ts), [v * scale for v in vs]


def main():
    if not VCD.exists():
        sys.exit(f"VCD not found: {VCD}")

    data, sec_per_tick = parse_vcd(VCD)
    QS = 1.0 / (1 << 24)

    iL_t, iL_v     = unpack(data["iL"], QS)
    vC_t, vC_v     = unpack(data["vC"], QS)
    vref_t, vref_v = unpack(data["v_ref"], QS)
    iref_t, iref_v = unpack(data["i_ref"], QS)
    duty_t, duty_v = unpack(data["duty"], QS)

    to_ms = lambda ticks: [t * sec_per_tick * 1e3 for t in ticks]
    iL_t, vC_t, vref_t, iref_t, duty_t = map(to_ms, (iL_t, vC_t, vref_t, iref_t, duty_t))

    fig, (ax_v, ax_i, ax_d) = plt.subplots(
        3, 1, figsize=(11, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 2]},
    )
    fig.suptitle(
        "Buck plant + cascaded PI controller — closed-loop "
        "(ω_c inner ≈ 10 kHz, outer ≈ 1 kHz; Vin=24 V, L=100 µH, C=100 µF, R_load=6 Ω)",
        fontsize=10,
    )

    # --- vC + v_ref overlay
    ax_v.step(vref_t, vref_v, where="post", color="#2CA02C",
              linestyle="--", linewidth=1.2, label="v_ref")
    ax_v.plot(vC_t, vC_v, color="#1F77B4", linewidth=0.9, label="v_C (output)")
    ax_v.set_ylabel("v_C / v_ref  [V]")
    ax_v.grid(True, alpha=0.3)
    ax_v.legend(loc="lower right", fontsize=9)

    # --- iL + i_ref overlay
    ax_i.step(iref_t, iref_v, where="post", color="#D62728",
              linestyle="--", linewidth=1.2, label="i_ref (outer PI output)")
    ax_i.plot(iL_t, iL_v, color="#B8860B", linewidth=0.8, label="i_L (actual)")
    ax_i.set_ylabel("i_L / i_ref  [A]")
    ax_i.grid(True, alpha=0.3)
    ax_i.legend(loc="lower right", fontsize=9)

    # --- duty
    ax_d.step(duty_t, duty_v, where="post", color="#333333", linewidth=0.9)
    ax_d.set_ylabel("duty  (0..1)")
    ax_d.set_xlabel("time  [ms]")
    ax_d.set_ylim(-0.05, 1.1)
    ax_d.axhline(1.0, color="#aaaaaa", linestyle=":", linewidth=0.6)
    ax_d.grid(True, alpha=0.3)

    # Mark v_ref step events on all axes
    for i in range(1, len(vref_t)):
        if vref_v[i] != vref_v[i - 1]:
            for ax in (ax_v, ax_i, ax_d):
                ax.axvline(vref_t[i], color="#888", linestyle=":", linewidth=0.8)
            ax_v.text(vref_t[i], ax_v.get_ylim()[1] * 0.97,
                      f"  v_ref → {vref_v[i]:.1f} V", color="#555",
                      fontsize=9, ha="left", va="top")

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    plt.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
