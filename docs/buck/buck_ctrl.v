//-----------------------------------------------------------------------------
// buck_ctrl.v
//
// Cascaded PI controller for the synchronous buck plant.
//
//   outer (voltage):   e_v = v_ref − v_C       →  i_ref  (clamped)
//   inner (current):   e_i = i_ref − i_L       →  duty   (clamped)
//   pwm:               q = (pwm_cnt < duty · TICKS_PER_PWM)
//
// Timing
//   Both PI loops run once per PWM period at pwm_cnt == 0.
//   PWM counter advances every plant `tick` (Δt = 100 ns),
//   wraps every TICKS_PER_PWM ticks (10 µs → 100 kHz by default).
//
// Format
//   Q8.24 signed, 32-bit, matches buck_plant.v so signals wire directly.
//   PI gains are per-sample (i.e. ki already includes Ts).
//
// Anti-windup
//   Each integrator freezes whenever its own output is saturated.
//   Simple back-calculation would be better but this is sufficient to start.
//
// Starting gains are intentionally conservative — tune in buck_closed_tb.v (task #8).
//-----------------------------------------------------------------------------
`timescale 1ns/100ps

module buck_ctrl #(
    parameter int N = 32,
    parameter int Q = 24,

    parameter int TICKS_PER_PWM = 100,         // 100 ticks @ 100 ns = 10 µs → 100 kHz

    // PI gains (Q8.24).  Starting-point values — expect to tune.
    parameter logic signed [N-1:0] KP_V = 32'sd1677722,   // 0.10  outer-P
    parameter logic signed [N-1:0] KI_V = 32'sd1678,      // 1e-4  outer-I per Ts
    parameter logic signed [N-1:0] KP_I = 32'sd838860,    // 0.05  inner-P
    parameter logic signed [N-1:0] KI_I = 32'sd8389,      // 5e-4  inner-I per Ts

    // Saturation limits (Q8.24)
    parameter logic signed [N-1:0] I_REF_MAX = 32'sd167772160, // +10.0 A
    parameter logic signed [N-1:0] I_REF_MIN = 32'sd0,         //   0.0 A  (buck → CCM only)
    parameter logic signed [N-1:0] DUTY_MAX  = 32'sd16777216,  //   1.00
    parameter logic signed [N-1:0] DUTY_MIN  = 32'sd0          //   0.00
)(
    input  logic                      clk,
    input  logic                      rst_n,
    input  logic                      tick,       // one pulse per plant Δt

    // Plant measurements
    input  logic signed [N-1:0]       vC,
    input  logic signed [N-1:0]       iL,

    // Setpoint
    input  logic signed [N-1:0]       v_ref,

    // Outputs
    output logic                      q,          // PWM to Q1 (plant.q)
    output logic signed [N-1:0]       duty,       // duty, Q8.24  (0..1), monitor
    output logic signed [N-1:0]       i_ref       // outer-loop output,   monitor
);

    //-------------------------------------------------------------------------
    // Helpers — signed Q×Q multiply with right-shift, and saturation clamp.
    // Static (default) functions — fine for pure combinational use.
    //-------------------------------------------------------------------------
    function logic signed [N-1:0] qmul(
        input logic signed [N-1:0] a,
        input logic signed [N-1:0] b
    );
        logic signed [2*N-1:0] ax, bx, p;
        ax = {{N{a[N-1]}}, a};
        bx = {{N{b[N-1]}}, b};
        p  = (ax * bx) >>> Q;
        qmul = p[N-1:0];
    endfunction

    function logic signed [N-1:0] sat(
        input logic signed [N-1:0] x,
        input logic signed [N-1:0] lo,
        input logic signed [N-1:0] hi
    );
        if (x > hi)       sat = hi;
        else if (x < lo)  sat = lo;
        else              sat = x;
    endfunction

    //-------------------------------------------------------------------------
    // PWM counter — advances once per `tick`, wraps every TICKS_PER_PWM
    //-------------------------------------------------------------------------
    int pwm_cnt;
    logic pwm_wrap;
    assign pwm_wrap = (pwm_cnt == 0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            pwm_cnt <= 0;
        else if (tick)
            pwm_cnt <= (pwm_cnt == TICKS_PER_PWM - 1) ? 0 : pwm_cnt + 1;
    end

    //-------------------------------------------------------------------------
    // PWM compare:  duty (Q8.24 fraction) → integer tick count
    //   duty_ticks = (duty · TICKS_PER_PWM) >>> Q
    //-------------------------------------------------------------------------
    logic signed [2*N-1:0] duty_x;
    int                    duty_ticks;
    assign duty_x     = duty;                                   // sign-extend
    assign duty_ticks = int'((duty_x * TICKS_PER_PWM) >>> Q);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else if (tick)
            q <= (pwm_cnt < duty_ticks) ? 1'b1 : 1'b0;
    end

    //-------------------------------------------------------------------------
    // Combinational PI math — continuous assigns so the always block below
    // only holds register updates (sidesteps Icarus's lack of block-local
    // `automatic` support).
    //-------------------------------------------------------------------------
    logic signed [N-1:0] int_v, int_i;                          // integrator states
    logic signed [N-1:0] e_v,  ki_ev, i_ref_raw, i_ref_new;
    logic signed [N-1:0] e_i,  ki_ei, duty_raw,  duty_new;

    // --- outer (voltage) ---
    assign e_v       = v_ref - vC;
    assign ki_ev     = qmul(KI_V, e_v);
    assign i_ref_raw = qmul(KP_V, e_v) + int_v + ki_ev;
    assign i_ref_new = sat(i_ref_raw, I_REF_MIN, I_REF_MAX);

    // --- inner (current) --- uses the FRESH outer output (combinational path)
    assign e_i       = i_ref_new - iL;
    assign ki_ei     = qmul(KI_I, e_i);
    assign duty_raw  = qmul(KP_I, e_i) + int_i + ki_ei;
    assign duty_new  = sat(duty_raw, DUTY_MIN, DUTY_MAX);

    //-------------------------------------------------------------------------
    // Sequential state update — once per PWM period, with anti-windup
    // (freeze integrator if its own output is clamped this cycle)
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            int_v <= '0;
            int_i <= '0;
            i_ref <= '0;
            duty  <= '0;
        end else if (tick && pwm_wrap) begin
            if (i_ref_new == i_ref_raw)                 // outer not saturated
                int_v <= int_v + ki_ev;
            if (duty_new  == duty_raw)                  // inner not saturated
                int_i <= int_i + ki_ei;
            i_ref <= i_ref_new;
            duty  <= duty_new;
        end
    end

endmodule
