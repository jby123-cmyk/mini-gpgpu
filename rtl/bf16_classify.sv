module bf16_classify (
    input  logic [15:0] value_i,
    output logic        sign_o,
    output logic        is_zero_o,
    output logic        is_subnormal_o,
    output logic        is_normal_o,
    output logic        is_inf_o,
    output logic        is_nan_o
);

    logic [7:0] exponent;
    logic [6:0] fraction;

    assign sign_o = value_i[15];
    assign exponent = value_i[14:7];
    assign fraction = value_i[6:0];

    assign is_zero_o      = (exponent == 8'h00) && (fraction == 7'h00);
    assign is_subnormal_o = (exponent == 8'h00) && (fraction != 7'h00);
    assign is_normal_o    = (exponent != 8'h00) && (exponent != 8'hff);
    assign is_inf_o       = (exponent == 8'hff) && (fraction == 7'h00);
    assign is_nan_o       = (exponent == 8'hff) && (fraction != 7'h00);

endmodule
