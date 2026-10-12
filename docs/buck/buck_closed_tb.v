//-----------------------------------------------------------------------------
// buck_closed_tb.v
//
// Closed-loop testbench: buck_plant + buck_ctrl wired together.
//
// Scenario:
//   1. Reset, release.
//   2. v_ref = 12 V (startup) — hold for 10 ms, let it settle.
//   3. Step v_ref 12 V → 18 V — hold for another 10 ms.
//
// Build & run:
//   iverilog -g2012 -o buck_closed_tb.vvp buck_plant.v buck_ctrl.v buck_closed_tb.v
//   vvp buck_closed_tb.vvp
//-----------------------------------------------------------------------------
`timescale 1ns/100ps

module buck_closed_tb;

    //-------------------------------------------------------------------------
    // Config
    //-------------------------------------------------------------------------
    localparam int N = 32;
    localparam int Q = 24;

    localparam real CLK_PERIOD_NS = 10.0;    // 100 MHz
    localparam int  CLKS_PER_TICK = 10;      // Δt = 100 ns

    // Reference / supply in Q8.24
    localparam logic signed [N-1:0] V_REF_12 = 32'sd201326592;  // 12 V · 2^24
    localparam logic signed [N-1:0] V_REF_18 = 32'sd301989888;  // 18 V · 2^24
    localparam logic signed [N-1:0] VIN_FP   = 32'sd402653184;  // 24 V · 2^24

    //-------------------------------------------------------------------------
    // DUT I/O
    //-------------------------------------------------------------------------
    logic                 clk, rst_n, tick;
    logic                 q;
    logic signed [N-1:0]  vin, vC, iL;
    logic signed [N-1:0]  v_ref, duty, i_ref;

    //-------------------------------------------------------------------------
    // DUT instances
    //-------------------------------------------------------------------------
    buck_plant #(.N(N), .Q(Q)) plant (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick),
        .q     (q),
        .vin   (vin),
        .iL    (iL),
        .vC    (vC)
    );

    // Gains tuned for ω_c_inner ≈ 2π·10 kHz, ω_c_outer ≈ 2π·1 kHz
    //   KP_I = ω_c · L / V_in     = 0.262   → 0.262·2^24 ≈ 4,395,631
    //   KI_I = KP_I · (Ts/Ti)     = 0.164   → 0.164·2^24 ≈ 2,751,463
    //   KP_V = ω_c · C            = 0.628   → 0.628·2^24 ≈ 10,536,492
    //   KI_V = KP_V · (Ts/Ti)     = 0.0395  → 0.0395·2^24 ≈   662,702
    buck_ctrl #(
        .N(N), .Q(Q),
        .KP_V (32'sd10536492),
        .KI_V (32'sd662702),
        .KP_I (32'sd4395631),
        .KI_I (32'sd2751463)
    ) ctrl (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick),
        .vC    (vC),
        .iL    (iL),
        .v_ref (v_ref),
        .q     (q),
        .duty  (duty),
        .i_ref (i_ref)
    );

    //-------------------------------------------------------------------------
    // Clock + tick generator
    //-------------------------------------------------------------------------
    initial clk = 1'b0;
    always  #(CLK_PERIOD_NS/2.0) clk = ~clk;

    int tick_cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tick_cnt <= 0;
            tick     <= 1'b0;
        end else begin
            if (tick_cnt == CLKS_PER_TICK - 1) begin
                tick_cnt <= 0;
                tick     <= 1'b1;
            end else begin
                tick_cnt <= tick_cnt + 1;
                tick     <= 1'b0;
            end
        end
    end

    //-------------------------------------------------------------------------
    // Helpers
    //-------------------------------------------------------------------------
    function real q_to_real(input logic signed [N-1:0] x);
        q_to_real = $itor(x) / 16777216.0;
    endfunction

    //-------------------------------------------------------------------------
    // Stimulus
    //-------------------------------------------------------------------------
    initial begin
        $timeformat(-9, 0, "", 10);
        $dumpfile("buck_closed_tb.vcd");
        $dumpvars(0, buck_closed_tb);

        rst_n = 1'b0;
        vin   = VIN_FP;
        v_ref = V_REF_12;

        #200;
        rst_n = 1'b1;

        $display("[t=%0t ns] Reset released. v_ref = 12.000 V", $time);

        // Settle at 12 V for 10 ms
        #5000000;
        $display("[t=%0t ns] @ v_ref=12 V:  vC = %7.4f V   iL = %7.4f A   duty = %6.4f   i_ref = %7.4f A",
                 $time, q_to_real(vC), q_to_real(iL), q_to_real(duty), q_to_real(i_ref));

        // Step reference
        v_ref = V_REF_18;
        $display("[t=%0t ns] *** Step v_ref 12 → 18 V", $time);

        #5000000;
        $display("[t=%0t ns] @ v_ref=18 V:  vC = %7.4f V   iL = %7.4f A   duty = %6.4f   i_ref = %7.4f A",
                 $time, q_to_real(vC), q_to_real(iL), q_to_real(duty), q_to_real(i_ref));

        $display("--- Simulation complete ---");
        $finish;
    end

    //-------------------------------------------------------------------------
    // Progress monitor — one line per ms
    //-------------------------------------------------------------------------
    initial begin
        #500;
        forever begin
            #1000000;
            $display("  [t=%0t ns]  vC=%7.4f V  iL=%7.4f A  duty=%6.4f  i_ref=%7.4f A  v_ref=%5.2f V",
                     $time, q_to_real(vC), q_to_real(iL),
                     q_to_real(duty), q_to_real(i_ref), q_to_real(v_ref));
        end
    end

endmodule
