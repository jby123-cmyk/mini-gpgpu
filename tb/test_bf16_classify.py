"""Cocotb tests for bf16_classify.

Run from the repository root:
    make COCOTB_TOPLEVEL=bf16_classify COCOTB_TEST_MODULES=tb.test_bf16_classify
"""

import cocotb
from cocotb.triggers import Timer


async def check_classification(dut, value, *, sign, zero, subnormal, normal, inf, nan):
    dut.value_i.value = value
    await Timer(1, unit="ns")

    assert int(dut.sign_o.value) == sign
    assert int(dut.is_zero_o.value) == zero
    assert int(dut.is_subnormal_o.value) == subnormal
    assert int(dut.is_normal_o.value) == normal
    assert int(dut.is_inf_o.value) == inf
    assert int(dut.is_nan_o.value) == nan

    classes = (
        dut.is_zero_o,
        dut.is_subnormal_o,
        dut.is_normal_o,
        dut.is_inf_o,
        dut.is_nan_o,
    )
    assert sum(int(signal.value) for signal in classes) == 1


@cocotb.test()
async def test_zero_encodings(dut):
    await check_classification(
        dut, 0x0000, sign=0, zero=1, subnormal=0, normal=0, inf=0, nan=0
    )
    await check_classification(
        dut, 0x8000, sign=1, zero=1, subnormal=0, normal=0, inf=0, nan=0
    )


@cocotb.test()
async def test_subnormal_and_normal_encodings(dut):
    await check_classification(
        dut, 0x0001, sign=0, zero=0, subnormal=1, normal=0, inf=0, nan=0
    )
    await check_classification(
        dut, 0x3F80, sign=0, zero=0, subnormal=0, normal=1, inf=0, nan=0
    )
    await check_classification(
        dut, 0xBF80, sign=1, zero=0, subnormal=0, normal=1, inf=0, nan=0
    )


@cocotb.test()
async def test_infinity_and_nan_encodings(dut):
    await check_classification(
        dut, 0x7F80, sign=0, zero=0, subnormal=0, normal=0, inf=1, nan=0
    )
    await check_classification(
        dut, 0xFF80, sign=1, zero=0, subnormal=0, normal=0, inf=1, nan=0
    )
    await check_classification(
        dut, 0x7FC1, sign=0, zero=0, subnormal=0, normal=0, inf=0, nan=1
    )
