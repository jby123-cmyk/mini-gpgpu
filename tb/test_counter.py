import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles


@cocotb.test()
async def test_counts(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # test signals
    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    start = int(dut.count.value)
    await ClockCycles(dut.clk, 5)
    assert int(dut.count.value) == (start + 5) % 16
