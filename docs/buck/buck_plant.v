//-----------------------------------------------------------------------------
// buck_plant.v
//
// Discrete-time synchronous-buck plant model (switched, forward Euler).
// See buck.drawio tabs "ckt" and "discrete" for schematic + derivation.
//
// Equations (FPGA-friendly form, divisions precomputed into constants):
//     i_L[k+1] = i_L[k] + C1*(q*V_in) - C2*v_C - C3*i_L
//     v_C[k+1] = v_C[k] + C4*i_L      - C5*v_C
//
// Fixed-point format: Q8.24 signed, N=32 bits (matches pfc_hft_state_space.v).
// All I/O voltages/currents are V or A multiplied by 2^Q.
//
// Default coefficients @ Δt=100ns, L=100µH, C=100µF, R_L=50mΩ, R_load=6Ω:
//     C1 = C2 = C4 = Δt/L         = 1.0e-3     → 16777  (= round(1e-3*2^24))
//     C3           = Δt·R_L/L     = 5.0e-5     → 839
//     C5           = Δt/(C·R_load)= 1.6667e-4  → 2796
//-----------------------------------------------------------------------------
`timescale 1ns/100ps

module buck_plant #(
    parameter int N = 32,                 // total word length (signed)
    parameter int Q = 24,                 // fractional bits → Q8.24

    parameter logic signed [N-1:0] C1 = 32'sd16777,
    parameter logic signed [N-1:0] C2 = 32'sd16777,
    parameter logic signed [N-1:0] C3 = 32'sd839,
    parameter logic signed [N-1:0] C4 = 32'sd16777,
    parameter logic signed [N-1:0] C5 = 32'sd2796
)(
    input  logic             clk,
    input  logic             rst_n,
    input  logic             tick,     // 1-cycle pulse per Δt; state advances on tick

    // Plant inputs
    input  logic                      q,     // PWM switch state: 1 = Q1 on, 0 = Q2 on
    input  logic signed [N-1:0]       vin,   // input source voltage,  Q8.24

    // Plant state outputs
    output logic signed [N-1:0]       iL,    // inductor current,      Q8.24
    output logic signed [N-1:0]       vC     // output cap voltage,    Q8.24
);

    //-------------------------------------------------------------------------
    // State registers
    //-------------------------------------------------------------------------
    logic signed [N-1:0] iL_reg;
    logic signed [N-1:0] vC_reg;

    assign iL = iL_reg;
    assign vC = vC_reg;

    //-------------------------------------------------------------------------
    // q·V_in — 1-bit q, so a mux not a multiplier
    //-------------------------------------------------------------------------
    logic signed [N-1:0] q_vin;
    assign q_vin = q ? vin : '0;

    //-------------------------------------------------------------------------
    // Sign-extend all N-bit operands to 2N bits BEFORE multiplication
    // to defeat Verilog's self-determined width rule (otherwise the N×N
    // product can truncate before being assigned to the 2N-bit wire).
    //-------------------------------------------------------------------------
    logic signed [2*N-1:0] C1_x, C2_x, C3_x, C4_x, C5_x;
    logic signed [2*N-1:0] qvin_x, iL_x, vC_x;

    assign C1_x   = C1;
    assign C2_x   = C2;
    assign C3_x   = C3;
    assign C4_x   = C4;
    assign C5_x   = C5;
    assign qvin_x = q_vin;
    assign iL_x   = iL_reg;
    assign vC_x   = vC_reg;

    //-------------------------------------------------------------------------
    // Full-precision products (2N bits): Q8.24 × Q8.24 = Q16.48
    //-------------------------------------------------------------------------
    logic signed [2*N-1:0] p_qvin;   // C1 · (q·V_in)
    logic signed [2*N-1:0] p_vc_2;   // C2 · v_C
    logic signed [2*N-1:0] p_iL_3;   // C3 · i_L
    logic signed [2*N-1:0] p_iL_4;   // C4 · i_L
    logic signed [2*N-1:0] p_vc_5;   // C5 · v_C

    assign p_qvin = C1_x * qvin_x;
    assign p_vc_2 = C2_x * vC_x;
    assign p_iL_3 = C3_x * iL_x;
    assign p_iL_4 = C4_x * iL_x;
    assign p_vc_5 = C5_x * vC_x;

    //-------------------------------------------------------------------------
    // State deltas: sum products in 2N bits, then arithmetic-shift back to Q.
    // Truncate upper N bits on assignment — safe because physical quantities
    // stay well inside Q8.24 range (±128) for sane buck operating points.
    //-------------------------------------------------------------------------
    logic signed [2*N-1:0] iL_delta_wide;
    logic signed [2*N-1:0] vC_delta_wide;
    logic signed [N-1:0]   iL_delta;
    logic signed [N-1:0]   vC_delta;

    assign iL_delta_wide = (p_qvin - p_vc_2 - p_iL_3) >>> Q;
    assign vC_delta_wide = (p_iL_4 - p_vc_5)          >>> Q;

    assign iL_delta = iL_delta_wide[N-1:0];
    assign vC_delta = vC_delta_wide[N-1:0];

    //-------------------------------------------------------------------------
    // Sequential state update — one forward-Euler step per `tick`
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            iL_reg <= '0;
            vC_reg <= '0;
        end else if (tick) begin
            iL_reg <= iL_reg + iL_delta;
            vC_reg <= vC_reg + vC_delta;
        end
    end

endmodule
