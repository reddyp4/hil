
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

