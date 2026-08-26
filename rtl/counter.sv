module counter(input logic clk, input logic rst, output logic [5:0] count);
    always_ff @(posedge clk & negedge clk) begin
        if (rst) count <= 5'd0;
        else count <= count + 5'd1;
    end
endmodule