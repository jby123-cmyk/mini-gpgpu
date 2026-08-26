"""cocotb tests for add_fp32 (combinational FP32 accumulate stage).

Inputs match mul_bf16 outputs: (s_i, exp_i[8:0], m_i[15:0]) plus FP32 acc_i.
Bit-accurate model mirrors rtl/fma_unit.sv add_fp32.
"""

from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer

NORM_BIT = 23


def pack_fp32(sign: int, exp: int, frac: int) -> int:
    return ((sign & 1) << 31) | ((exp & 0xFF) << 23) | (frac & 0x7FFFFF)


def _as_u(val: int, bits: int) -> int:
    return val & ((1 << bits) - 1)


def _to_signed(val: int, bits: int) -> int:
    val = _as_u(val, bits)
    if val & (1 << (bits - 1)):
        val -= 1 << bits
    return val


def count_leading_zeroes(x: int, width: int = 27) -> int:
    if x == 0:
        return width
    for i in range(width - 1, -1, -1):
        if x & (1 << i):
            return (width - 1) - i
    return width


def add_fp32_ref(acc_i: int, s_i: int, exp_i: int, m_i: int) -> tuple[int, int]:
    """Return (acc_o, overflow) matching add_fp32 RTL."""
    s_acc = (acc_i >> 31) & 1
    exp_acc = (acc_i >> 23) & 0xFF
    frac_acc = acc_i & 0x7FFFFF

    m_acc_mag = (0b01 << 23) | frac_acc
    m_i_mag = (m_i & 0xFFFF) << 8

    m_acc_sd = _as_u((-m_acc_mag) if s_acc else m_acc_mag, 26)
    m_i_sd = _as_u((-m_i_mag) if s_i else m_i_mag, 26)

    exp_sub = _as_u(exp_acc - (exp_i & 0x1FF), 9)
    acc_lt_i = (exp_sub >> 8) & 1
    shift_raw = _as_u((~exp_sub & 0xFF) + 1, 8) if acc_lt_i else (exp_sub & 0xFF)
    shift_amt = 25 if shift_raw > 25 else shift_raw

    exp_large = (exp_i & 0x1FF) if acc_lt_i else exp_acc
    m_large = m_i_sd if acc_lt_i else m_acc_sd
    m_small = m_acc_sd if acc_lt_i else m_i_sd

    m_small_sh = _as_u(_to_signed(m_small, 26) >> shift_amt, 26)

    # {m[25], m} sign-extend to 27 bits, then add
    m_sum = _as_u(_to_signed(m_large, 26) + _to_signed(m_small_sh, 26), 27)

    s_o = (m_sum >> 26) & 1
    m_mag = _as_u((~m_sum + 1) if s_o else m_sum, 27)
    zero_m = m_mag == 0

    if zero_m:
        return pack_fp32(s_o, 0, 0), 0

    lz = count_leading_zeroes(m_mag, 27)
    lead_idx = 26 - lz

    if lead_idx >= NORM_BIT:
        norm_sh = lead_idx - NORM_BIT
        m_norm = m_mag >> norm_sh
        exp_full = _as_u(exp_large + norm_sh, 10)
    else:
        norm_sh = NORM_BIT - lead_idx
        m_norm = _as_u(m_mag << norm_sh, 27)
        exp_full = _as_u(exp_large - norm_sh, 10)

    underflow = (exp_full >> 9) & 1
    overflow = (not underflow) and (exp_full >= 255)
    frac = m_norm & 0x7FFFFF

    if underflow:
        return pack_fp32(s_o, 0, 0), 0
    if overflow:
        return pack_fp32(s_o, 0xFF, 0), 1
    return pack_fp32(s_o, exp_full & 0xFF, frac), 0


def product_1p0(sign: int = 0, exp: int = 127) -> tuple[int, int, int]:
    """Encoding of ±2^(exp-127) as mul_bf16 would (leading 1 at m[15])."""
    return sign & 1, exp & 0x1FF, 0x8000


async def apply_and_check(dut, acc_i: int, s_i: int, exp_i: int, m_i: int):
    dut.acc_i.value = acc_i
    dut.s_i.value = s_i
    dut.exp_i.value = exp_i
    dut.m_i.value = m_i
    await Timer(1, unit="ns")

    exp_acc, exp_ovf = add_fp32_ref(acc_i, s_i, exp_i, m_i)
    got_acc = int(dut.acc_o.value)
    got_ovf = int(dut.overflow.value)

    assert got_ovf == exp_ovf, (
        f"overflow acc={acc_i:#010x} s={s_i} exp={exp_i} m={m_i:#06x}: "
        f"got {got_ovf} want {exp_ovf}"
    )
    assert got_acc == exp_acc, (
        f"acc_o acc={acc_i:#010x} s={s_i} exp={exp_i} m={m_i:#06x}: "
        f"got {got_acc:#010x} want {exp_acc:#010x}"
    )


@cocotb.test()
async def test_add_one_plus_one(dut):
    """1.0 + 1.0 → 2.0"""
    await apply_and_check(dut, pack_fp32(0, 127, 0), *product_1p0(0, 127))


@cocotb.test()
async def test_add_cancel(dut):
    """1.0 + (-1.0) → 0"""
    await apply_and_check(dut, pack_fp32(0, 127, 0), *product_1p0(1, 127))


@cocotb.test()
async def test_add_different_exp(dut):
    """2.0 + 1.0 → 3.0"""
    await apply_and_check(dut, pack_fp32(0, 128, 0), *product_1p0(0, 127))


@cocotb.test()
async def test_add_product_larger(dut):
    """0.5 + 2.0 → 2.5"""
    await apply_and_check(dut, pack_fp32(0, 126, 0), *product_1p0(0, 128))


@cocotb.test()
async def test_add_signed_acc(dut):
    """-1.0 + 0.5 → -0.5"""
    await apply_and_check(dut, pack_fp32(1, 127, 0), *product_1p0(0, 126))


@cocotb.test()
async def test_add_overflow_to_inf(dut):
    """Huge + huge → Inf, overflow=1"""
    await apply_and_check(dut, pack_fp32(0, 254, 0x7FFFFF), 0, 254, 0xFFFF)


@cocotb.test()
async def test_add_random_normals(dut):
    """Random normals through the RTL-accurate model."""
    rng = random.Random(1)
    for _ in range(200):
        acc = pack_fp32(rng.randint(0, 1), rng.randint(1, 250), rng.randint(0, 0x7FFFFF))
        s_i = rng.randint(0, 1)
        exp_i = rng.randint(1, 250)
        m_i = 0x8000 | rng.randint(0, 0x7FFF)
        await apply_and_check(dut, acc, s_i, exp_i, m_i)
