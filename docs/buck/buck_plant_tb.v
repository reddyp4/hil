//-----------------------------------------------------------------------------
// buck_plant_tb.v
//
// Open-loop testbench for buck_plant.
//
// Scenario:
//   1. Hold reset, then release.
//   2. Drive PWM at f_sw = 100 kHz with 50% duty for 3 ms (settle).
//   3. Step duty to 75% and let it settle for another 2 ms.
//
// Verifies: v_C should approach  d·V_in / (1 + R_L/R_load)
//   d=0.50, V_in=24V → V_out ≈ 11.901 V
//   d=0.75, V_in=24V → V_out ≈ 17.851 V
//
// Clock = 100 MHz, tick every 10 clks → Δt = 100 ns  (matches plant coeffs).
//
// Build & run (once iverilog + gtkwave are installed):
//   iverilog -g2012 -o buck_plant_tb.vvp buck_plant.v buck_plant_tb.v
//   vvp buck_plant_tb.vvp
//   gtkwave buck_plant_tb.vcd
//-----------------------------------------------------------------------------
`timescale 1ns/100ps

module buck_plant_tb;

    //-------------------------------------------------------------------------
    // Config
    //-------------------------------------------------------------------------
    localparam int N = 32;
    localparam int Q = 24;

    localparam real CLK_PERIOD_NS = 10.0;    // 100 MHz plant clock
    localparam int  CLKS_PER_TICK = 10;      // tick every 10 clks → Δt = 100 ns
    localparam int  TICKS_PER_PWM = 100;     // 100 ticks per PWM period → 100 kHz

    // Operating point (also used to compute expected steady state in prints)
    localparam real VIN_V    = 24.0;
    localparam real R_L_OHM  = 0.05;
    localparam real R_LOAD   = 6.0;

    // 24 V in Q8.24: 24 · 2^24 = 402,653,184
    localparam logic signed [N-1:0] VIN_FP = 32'sd402653184;

    //-------------------------------------------------------------------------
    // DUT I/O
    //-------------------------------------------------------------------------
    logic clk;
    logic rst_n;
    logic tick;
    logic q;
    logic signed [N-1:0] vin;
    logic signed [N-1:0] iL;
    logic signed [N-1:0] vC;

    int duty_pct;                            // 0..100

    //-------------------------------------------------------------------------
    // DUT
    //-------------------------------------------------------------------------
    buck_plant #(.N(N), .Q(Q)) dut (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick),
        .q     (q),
        .vin   (vin),
        .iL    (iL),
        .vC    (vC)
    );

    //-------------------------------------------------------------------------
    // Clock
    //-------------------------------------------------------------------------
    initial clk = 1'b0;
    always  #(CLK_PERIOD_NS/2.0) clk = ~clk;

    //-------------------------------------------------------------------------
    // Tick generator: 1-cycle pulse every CLKS_PER_TICK
    //-------------------------------------------------------------------------
    int tick_cnt;

    always_ff @(posedge clk or negedge rst_n) begin
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
    // PWM generator (counter advances once per tick; q=1 while cnt < duty)
    //-------------------------------------------------------------------------
    int pwm_cnt;
    int duty_ticks;

    always_comb duty_ticks = (duty_pct * TICKS_PER_PWM) / 100;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pwm_cnt <= 0;
            q       <= 1'b0;
        end else if (tick) begin
            if (pwm_cnt == TICKS_PER_PWM - 1)
                pwm_cnt <= 0;
            else
                pwm_cnt <= pwm_cnt + 1;
            q <= (pwm_cnt < duty_ticks) ? 1'b1 : 1'b0;
        end
    end

    //-------------------------------------------------------------------------
    // Helper: Q8.24 → real (for printable values)
    //-------------------------------------------------------------------------
    function real q_to_real(input logic signed [N-1:0] x);
        q_to_real = $itor(x) / 16777216.0;   // 2^24
    endfunction

    function real expected_vout(input int d);
        expected_vout = (VIN_V * d) / 100.0 / (1.0 + R_L_OHM / R_LOAD);
    endfunction

    //-------------------------------------------------------------------------
    // Stimulus
    //-------------------------------------------------------------------------
    initial begin
        $dumpfile("buck_plant_tb.vcd");
        $dumpvars(0, buck_plant_tb);

        rst_n    = 1'b0;
        duty_pct = 50;
        vin      = VIN_FP;

        #100;
        rst_n = 1'b1;

        $display("[t=%0t ns] Release reset. Vin=%.2f V, duty=%0d%%, expected V_out = %.3f V",
                 $time, VIN_V, duty_pct, expected_vout(duty_pct));

        // Settle at 50% duty for 3 ms (dominant time constant R_load·C = 600 µs)
        #3000000;
        $display("[t=%0t ns] After 3 ms (d=50%%):  iL = %7.4f A   vC = %7.4f V   (target ~%.3f V)",
                 $time, q_to_real(iL), q_to_real(vC), expected_vout(duty_pct));

        // Step duty 50% → 75%
        duty_pct = 75;
        $display("[t=%0t ns] *** Step duty 50%% → 75%%  (expect V_out → %.3f V)",
                 $time, expected_vout(duty_pct));

        #2000000;
        $display("[t=%0t ns] After step   (d=75%%):  iL = %7.4f A   vC = %7.4f V   (target ~%.3f V)",
                 $time, q_to_real(iL), q_to_real(vC), expected_vout(duty_pct));

        $display("--- Simulation complete ---");
        $finish;
    end

    //-------------------------------------------------------------------------
    // Progress monitor — one line every 500 µs of sim time
    //-------------------------------------------------------------------------
    initial begin
        #200;
        forever begin
            #500000;
            $display("  [t=%0t ns]  iL=%7.4f A  vC=%7.4f V  q=%b  duty=%0d%%",
                     $time, q_to_real(iL), q_to_real(vC), q, duty_pct);
        end
    end

endmodule
