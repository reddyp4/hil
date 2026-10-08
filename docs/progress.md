
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
