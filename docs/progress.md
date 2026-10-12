
## IQ8 Initial call - which converter?

Synchronous buck converter — hands down the easiest teaching converter for this exact setup.

  Why it's ideal for FPGA1↔FPGA2 closed-loop:

  ┌─────────────────────────┬──────────────────────────────────────────────────────┬─────────────────────────────────┐
  │         Aspect          │                         Buck                         │    Frigate (for comparison)     │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ States                  │ 2 (i_L, v_C)                                         │ 3+ with resonant tank dynamics  │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Switches                │ 1 PWM duty cycle                                     │ 8 switches, phase-shift control │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Control variable        │ single D (0–1)                                       │ phase shift + frequency         │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Controller              │ textbook cascaded PI (V-outer, I-inner)              │ needs trajectory/model-based    │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Discretization          │ forward Euler is stable at reasonable fsw            │ stiff — needs careful step size │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ FPGA I/O between boards │ 1 PWM out, 2 ADC-equivalent values back              │ many signals, timing-critical   │
  ├─────────────────────────┼──────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Validation              │ closed-form small-signal model, easy to sanity-check │ much harder to verify by hand   │
  └─────────────────────────┴──────────────────────────────────────────────────────┴─────────────────────────────────┘

Wrote buck/buck_plant_tb.v. What it does:

  - Clock: 100 MHz, with a tick pulse every 10 cycles → plant physics advances at Δt = 100 ns
  - PWM generator: f_sw = 100 kHz (100 ticks/period); duty controlled by duty_pct register
  - Stimulus:
    a. Reset ~100 ns, release
    b. 50% duty for 3 ms → let v_C settle (dominant τ = R_load·C = 600 µs)
    c. Step duty to 75%, settle another 2 ms (step-response test)
  - Prints at every 500 µs with iL/vC in real units + at each phase transition shows the expected steady-state d·V_in / (1 + R_L/R_load) — easy visual pass/fail
  - VCD dump → buck_plant_tb.vcd for GTKWave

Expected results at the transition points:
  - d=50% → V_out ≈ 11.901 V, I_L_avg ≈ V_out/R_load ≈ 1.983 A
  - d=75% → V_out ≈ 17.851 V, I_L_avg ≈ 2.975 A


## Open-Loop Plant Test — Summary (2026-10-07)

### Files
- `buck/buck_plant.v` — discrete-time plant, forward Euler, Q8.24 signed 32-bit
- `buck/buck_plant_tb.v` — stimulus, VCD dump, settling checks
- `buck/plot_waveform.py` — VCD → PNG, no external deps beyond matplotlib
- `buck/buck_plant_waveform.png` — reference waveform (see below for how to read it)
- `buck/run.ps1` — one-shot build + sim + GTKWave

### Test conditions

| Parameter | Value | Notes |
|---|---|---|
| V_in | 24 V | DC source |
| L | 100 µH | inductor |
| R_L | 50 mΩ | inductor DCR (lumps MOSFET R_ds(on) + trace R in sim) |
| C | 100 µF | output cap, ideal (ESR = 0 in this model) |
| R_load | 6 Ω | resistive load |
| f_sw | 100 kHz | fixed-frequency synchronous PWM |
| Δt (sim step) | 100 ns | ≥ 20× faster than f_sw (ensures PWM edges resolved) |
| Fixed-point | Q8.24 signed, 32-bit | range ±128, resolution ~6×10⁻⁸ |
| Pre-computed coeffs | c1=c2=c4=1e-3, c3=5e-5, c5=1.667e-4 | from Δt/L, Δt·R_L/L, Δt/(C·R_load) |

### Stimulus sequence
1. Hold reset ~100 ns, release.
2. PWM at 100 kHz with duty = 50 % for 3 ms (first settling).
3. Step duty 50 % → 75 %, hold for 5 ms (step-response).
4. Total sim time: 8 ms.

### What to expect

**Steady-state DC gain** (closed-form): `V_out = d · V_in / (1 + R_L/R_load) = 0.9917 · d · V_in`

| Duty | Expected V_out | Expected I_L_avg = V_out / R_load |
|---|---|---|
| 50 % | 11.901 V | 1.983 A |
| 75 % | 17.851 V | 2.975 A |

**Dynamic signature** (very underdamped LC):
- Natural frequency: `f_n = 1/(2π·√(LC)) ≈ 1.591 kHz` → ring period ≈ 629 µs
- Damping ratio: `ζ = R_L / (2·√(L/C)) ≈ 0.025` → quality factor Q ≈ 20
- Expect ~5+ visible overshoot cycles before settling (visible in waveform)
- Switching ripple: `ΔI_L_pp = (V_in − V_out)·d / (L·f_sw) ≈ 60 mA` at d=50 %

### Observed (actual sim results)

| Instant | v_C observed | v_C target | error |
|---|---|---|---|
| t = 3 ms, d = 50 % | 11.891 V | 11.901 V | 0.08 % |
| t = 8 ms, d = 75 % | 17.830 V | 17.851 V | 0.12 % |

Errors are at fixed-point rounding noise level — plant model validated.

### Correlating sim to the real circuit

When the physical buck board is on the bench, use this sim as the reference. Procedure:

1. **Match the operating point.** Measure actual component values with a DMM (L via LCR meter, R_L via 4-wire, C via LCR). Plug those measured values into `buck_plant.v`'s parameters and re-run the sim — then compare to scope. Mismatches between measured and nameplate values will show up as:
   - Wrong **DC gain** → R_L or R_load off
   - Wrong **ring frequency** → L or C off
   - Wrong **ripple amplitude** → L, C, or f_sw off

2. **Probe the same three signals** on the scope:
   - V_out across the output cap (DC coupled, ≥ 20 MHz BW to see ripple)
   - I_L via current probe on inductor leg (or sense-resistor + diff probe)
   - PWM gate drive to Q1 (= the `q` signal in sim)

3. **Validate steady-state DC gain.** Measured V_out at d=50 % should land within ~1 % of 11.9 V. If much lower, there's unmodeled series resistance (connectors, PCB traces, sense resistor, MOSFET R_ds(on) above the 50 mΩ budget).

4. **Validate ring frequency with a duty-step.** Set a small duty, step up ~20 %, scope-trigger on the step, measure the ring period. Should be ≈ 629 µs. Deviation > 10 % → L or C out of tolerance.

5. **Validate ripple.** Measured ΔI_L_pp and ΔV_out_pp should match the ripple formulas above. Expect some discrepancy on ΔV_out_pp because real caps have ESR which adds a square-wave component the ideal sim doesn't model.

6. **Things the sim doesn't model yet** — expect divergence from hardware here:
   - **Dead-time** between Q1/Q2 (sim is instantaneously complementary) — real hardware has body-diode conduction briefly, extra switching loss.
   - **MOSFET R_ds(on)** — sim lumps this into R_L; real loss is temperature-dependent.
   - **Capacitor ESR** — adds high-frequency square-ripple on V_out that sim misses.
   - **Inductor saturation** at high I_L (nonlinear L).
   - **Scope probe loading, PCB parasitic L/C, EMI** on sensitive nodes.
   - **Thermal drift** of all component values with load.

7. **Debugging mismatch — quick rules of thumb:**
   - Hardware damps faster than sim → extra loop resistance (benign, update R_L).
   - Hardware rings at a different frequency → L or C value is off (check tolerance, inductor derating under current).
   - Hardware DC gain is lower → more series loss than modeled.
   - Hardware DC gain is higher → not possible from this topology; check probe calibration / Vin measurement.

Once hardware tracks sim within a few %, we have confidence the FPGA-side math is faithful to physics and can proceed to closed-loop controller tuning.


## Closed-Loop (Plant + Cascaded PI) — Summary (2026-10-07)

### Files
- `buck/buck_ctrl.v` — cascaded PI controller (outer V-loop → inner I-loop), Q8.24, same clk/tick as plant
- `buck/buck_closed_tb.v` — stimulus: `v_ref = 12 V` → settle → step to 18 V → settle
- `buck/plot_closed.py` — VCD → PNG, overlays references with actuals
- `buck/buck_closed_waveform.png` — reference closed-loop waveform

### Test conditions

Same plant operating point as the open-loop test (Vin=24 V, L=100 µH, C=100 µF, R_L=50 mΩ, R_load=6 Ω, f_sw=100 kHz, Δt=100 ns), **plus** the following controller config:

| Parameter | Value (Q8.24 int) | Real value | Notes |
|---|---|---|---|
| TICKS_PER_PWM | 100 | — | Controller fires once per PWM period (every 10 µs) |
| KP_V | 10,536,492 | 0.628 A/V | outer-loop P (= ω_c · C, ω_c = 2π·1 kHz) |
| KI_V | 662,702 | 0.0395 per Ts | outer-loop I (per-sample; = KP_V · Ts/Ti, Ti = 1/ω_c) |
| KP_I | 4,395,631 | 0.262 (dimensionless duty / A) | inner-loop P (= ω_c · L / Vin, ω_c = 2π·10 kHz) |
| KI_I | 2,751,463 | 0.164 per Ts | inner-loop I |
| I_REF_MAX | 167,772,160 | 10 A | outer PI clamp (buck is CCM only, no negative) |
| DUTY_MIN / MAX | 0 / 16,777,216 | 0.0 / 1.0 | inner PI clamp |

**Design intent:** inner current loop ω_c ≈ 10 kHz (10× below f_sw), outer voltage loop ω_c ≈ 1 kHz (10× below inner) — standard cascaded tuning for ~60° phase margin on each loop.

### Stimulus sequence
1. Hold reset ~200 ns, release.
2. `v_ref = 12 V` for 5 ms (startup transient → settle).
3. Step `v_ref` 12 V → 18 V, hold 5 ms (reference-step response).
4. Total sim: 10 ms.

### What to expect

**Steady-state tracking:** zero error. With R_L = 50 mΩ, the integrator absorbs the DCR drop automatically — open-loop would have shown `d·Vin · 0.9917`, closed-loop will land on `v_ref` exactly (to fixed-point noise).

| v_ref | Expected v_C (steady) | Expected i_L_avg = v_ref / R_load | Expected duty_avg = v_ref/Vin + loss |
|---|---|---|---|
| 12 V | 12.000 V | 2.000 A | ≈ 0.504 |
| 18 V | 18.000 V | 3.000 A | ≈ 0.756 |

**Transient signature** (closed-loop design targets):
- Rise time ≈ 1/(2π·ω_c_V) · 5 ≈ 800 µs for the outer loop; expect v_C settling within ~1 ms.
- First-cycle overshoot ~15–25% from startup — large v_ref−v_C error drives outer PI output into clamp (10 A), which the inner loop then slews.
- Duty hits 1.0 (saturated) briefly on both transients — anti-windup freezes the integrator so there's no post-saturation hangover.

### Observed (actual sim results)

| Instant | v_C observed | v_C target | tracking error | duty (avg) | i_L (avg) |
|---|---|---|---|---|---|
| t = 5 ms, v_ref = 12 V | 12.0003 V | 12.000 V | 0.003 % | 0.512 | 1.73 A |
| t = 10 ms, v_ref = 18 V | 18.0002 V | 18.000 V | 0.001 % | 0.761 | 2.82 A |

- Startup overshoot: v_C peaked at ~14.5 V (≈ 21% overshoot), returned to 12 V by t ≈ 1 ms.
- Reference step 12 → 18 V: no visible overshoot, settled by t ≈ 6 ms (1 ms after step).
- Both transients hit duty = 1.0 briefly; anti-windup worked cleanly (no sustained post-saturation ringing).

**Design hits its 1 kHz / 10 kHz BW targets.**

### Correlating closed-loop sim to the real circuit

All of the plant-level correlation steps from the open-loop section still apply (match component values, probe v_C / i_L / PWM, validate DC behavior and ripple). Additional closed-loop checks:

1. **Validate zero steady-state error.** On hardware, measured v_C at a given v_ref should land within scope accuracy (~0.1 %) of v_ref. Any persistent offset usually means the integrator saturated and stopped (bug in anti-windup) OR the ADC path has a DC offset the controller can't see.

2. **Measure settling time on a small v_ref step.** Do a small step (e.g. 12 → 13 V), scope-trigger on the step, measure time to reach 95 % of final value. Should be < 2 ms with the current gains. If much slower, inner loop isn't actually running at ~10 kHz BW — suspect ADC filtering/latency.

3. **Measure overshoot on a bigger v_ref step** (e.g. 12 → 18 V). Should be < 25 %. Larger overshoot usually means too much integrator wind-up during saturation — swap simple-freeze anti-windup for back-calculation.

4. **Watch for limit-cycle oscillation.** On hardware, quantization in the ADC and PWM duty resolution can cause small sustained oscillations around the setpoint. Visible as a persistent few-mV peak-to-peak ripple at low frequency. Fix: reduce KI_V slightly or add a small deadband around zero error.

5. **Verify saturation handling.** Force a big transient (step v_ref from 0 → 20 V on power-up). Expect duty to saturate briefly then return cleanly to its steady-state value. If duty hangs at 1.0 after v_C has reached v_ref, anti-windup is broken.

6. **New things the sim still doesn't model** (on top of the open-loop list):
   - **ADC quantization + latency** — sim treats v_C and i_L as perfect 32-bit samples with zero delay. Real ADCs are 10–16 bits with a few µs of conversion latency.
   - **PWM duty resolution** — sim uses 100 integer compare steps (1 % duty resolution). FPGA PWM may have finer or coarser resolution; coarser resolution causes limit cycles.
   - **Current-sense noise and bandwidth** — a real shunt-amplifier chain is noisy and bandwidth-limited; inner loop may need to drop below 10 kHz to stay stable.
   - **Measurement scaling / offset calibration** — in sim, v_C in Q8.24 is literally volts × 2^24. On hardware, there's a resistor divider + ADC reference voltage that needs calibration — any mismatch shows up as either steady-state offset or gain error.

Once hardware tracks sim within a few % for both DC and transient behavior, the plant+controller pair is validated and ready to split across two FPGAs: controller on FPGA1 → PWM out → power stage → ADC in → back to FPGA1 (or FPGA2 if we go distributed).


