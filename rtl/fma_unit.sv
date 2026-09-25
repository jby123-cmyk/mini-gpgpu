//test linting --------------------------------------------------------------------------------------------------------------------------------------------------------

module fma_unit (input logic clk, rst, valid_i, valid_o
                 input logic [15:0] a_i,
                 input logic [15:0] b_i,
                 input logic [31:0] acc_i
                 output logic [31:0] acc_o
                 output logic overflow);
    logic s_mid;
    logic [8:0] exp_mid;
    logic [15:0] m_mid;

    mul_bf16 (.a_i(a_i), .b_i(b_i), .s_o(s_mid), .exp_o(exp_mid), .m_o(m_mid));

    add_fp32 (.acc_i(acc_i), .s_i(s_mid), .exp_i(exp_mid), .m_i(m_mid), .acc_o(acc_o), .overflow(overflow));

    always_ff (@posedge clk) begin
        if (rst) begin
            
        end
    end 
endmodule

module mul_bf16 (input logic [15:0] a_i, 
                 input logic [15:0] b_i,

                `ifdef TESTMODE
                    output logic [15:0] bf16_o, // bf16 output 
                    output logic overflow,
                `endif

                 output logic s_o, 
                 output logic [8:0] exp_o,
                 output logic [15:0] m_o
);
    // Unpack inputs
    logic s_a, s_b;
    logic [8:0] exp_a, exp_b;
    logic [7:0] m_a, m_b;

    assign s_a = a_i[15];
    assign s_b = b_i[15];
    assign exp_a = {1'b0, a_i[14:7]};
    assign exp_b = {1'b0, b_i[14:7]};
    assign m_a = {1'b1, a_i[6:0]};
    assign m_b = {1'b1, b_i[6:0]};

    // Intermediate signals
    logic [9:0] exp_int;
    logic [15:0] m_int;

    assign exp_int = exp_a + exp_b - 127;
    assign m_int = m_a * m_b; 

    // Output processing
    assign s_o = s_a ^ s_b;
    assign exp_o = m_int[15] ? (exp_int[8:0] + 9'd1) : exp_int[8:0];
    assign m_o = m_int[15] ? m_int : {m_int[14:0], 1'b0}; 

    `ifdef TESTMODE
        assign bf16_o = {s_o, exp_o[7:0], m_o[14:8]};
        assign overflow = exp_o[8];
    `endif  
endmodule 

// FP32 accumulate stage for mul_bf16 product (s_i, exp_i[8:0], m_i[15:0]).
// Fixed-point layout in 26-bit signed mantissas: hidden/leading 1 at bit 23.
//   acc:  {0, 01, frac[22:0]}
//   prod: {0, 0, m_i[15:0], 8'b0}  // m_i already has leading 1 at [15]
module add_fp32 (
    input  logic [31:0] acc_i,
    input  logic        s_i,
    input  logic [8:0]  exp_i,
    input  logic [15:0] m_i,
    `ifdef TESTMODE
        output logic [15:0] bf16_i,
        output logic bf16_overflow,
    `endif
    output logic [31:0] acc_o,
    output logic        overflow
);
    localparam int NORM_BIT = 23;

    `ifdef TESTMODE
        assign bf16_i = {s_i, exp_i[7:0], m_i[14:8]};
        assign bf16_overflow = exp_i[8];
    `endif  

    // -------------------------------------------------------------------------
    // Input unpacking
    // -------------------------------------------------------------------------
    logic        s_acc;
    logic [8:0]  exp_acc;
    logic [25:0] m_acc_mag, m_i_mag;
    logic [25:0] m_acc_sd, m_i_sd;

    assign s_acc     = acc_i[31];
    assign exp_acc   = {1'b0, acc_i[30:23]};
    assign m_acc_mag = {1'b0, 2'b01, acc_i[22:0]};
    assign m_i_mag   = {2'b00, m_i, 8'b0};

    assign m_acc_sd = s_acc ? (~m_acc_mag + 26'd1) : m_acc_mag;
    assign m_i_sd   = s_i   ? (~m_i_mag   + 26'd1) : m_i_mag;

    // -------------------------------------------------------------------------
    // Compare exponents
    // -------------------------------------------------------------------------
    logic [8:0] exp_sub;
    logic       acc_lt_i;
    logic [7:0] shift_raw, shift_amt;
    logic [8:0] exp_large;
    logic [25:0] m_large, m_small, m_small_sh;

    assign exp_sub   = exp_acc - exp_i;
    assign acc_lt_i  = exp_sub[8]; 
    assign shift_raw = acc_lt_i ? (~exp_sub[7:0] + 8'd1) : exp_sub[7:0];
    assign shift_amt = (shift_raw > 8'd25) ? 8'd25 : shift_raw;

    assign exp_large  = acc_lt_i ? exp_i : exp_acc;
    assign m_large    = acc_lt_i ? m_i_sd : m_acc_sd;
    assign m_small    = acc_lt_i ? m_acc_sd : m_i_sd;
    assign m_small_sh = 26'($signed(m_small) >>> shift_amt);

    // -------------------------------------------------------------------------
    // Signed add
    // -------------------------------------------------------------------------
    logic [26:0] m_sum, m_mag;
    logic        s_o;
    logic        zero_m;

    assign m_sum  = {m_large[25], m_large} + {m_small_sh[25], m_small_sh};
    assign s_o    = m_sum[26];
    assign m_mag  = s_o ? (~m_sum + 27'd1) : m_sum;
    assign zero_m = ~|m_mag;

    // -------------------------------------------------------------------------
    // Leading zero count and output processing 
    // -------------------------------------------------------------------------
    function automatic logic [4:0] count_leading_zeroes;
        input logic [26:0] x;
        begin
            count_leading_zeroes = 5'd27; 
            for (int i = 26; i >= 0; i--) begin
                if (x[i]) begin
                    count_leading_zeroes = 5'(26 - i);
                    break;
                end
            end
        end
    endfunction

    logic [4:0]  lz, lead_idx, norm_sh;
    logic [26:0] m_norm;
    logic [9:0]  exp_full;
    logic [22:0] frac;
    logic        underflow;

    assign lz       = count_leading_zeroes(m_mag);
    assign lead_idx = zero_m ? 5'd0 : 5'(6'd26 - lz);

    always_comb begin
        m_norm   = '0;
        norm_sh  = '0;
        exp_full = {1'b0, exp_large};
        frac     = '0;
        if (zero_m) begin
            // leave zeros
        end else if (lead_idx >= 5'(NORM_BIT)) begin
            // carry / too far left → shift right
            norm_sh  = lead_idx - 5'(NORM_BIT);
            m_norm   = m_mag >> norm_sh;
            exp_full = {1'b0, exp_large} + 10'(norm_sh);
            frac     = m_norm[22:0];
        end else begin
            // cancellation / too far right → shift left
            norm_sh  = 5'(NORM_BIT) - lead_idx;
            m_norm   = m_mag << norm_sh;
            exp_full = {1'b0, exp_large} - 10'(norm_sh);
            frac     = m_norm[22:0];
        end
    end

    assign underflow = ~zero_m & exp_full[9]; 
    assign overflow  = ~zero_m & ~underflow & (exp_full >= 10'd255);

    assign acc_o = zero_m   ? {s_o, 31'b0} :
                   underflow ? {s_o, 31'b0} :
                   overflow  ? {s_o, 8'hFF, 23'b0} : // Inf
                               {s_o, exp_full[7:0], frac};
endmodule
