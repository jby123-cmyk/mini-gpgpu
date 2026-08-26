"""cocotb tests for mul_bf16 (combinational BF16 multiply stage)."""

import cocotb
from cocotb.triggers import Timer


def pack_bf16(sign: int, exp: int, frac: int) -> int:
    """Pack BF16: [15]=sign, [14:7]=exp, [6:0]=frac."""
    return ((sign & 1) << 15) | ((exp & 0xFF) << 7) | (frac & 0x7F)

def mul_bf16_ref(a: int, b: int) -> tuple[int, int, int]:
    """Python model matching rtl/fma_unit.sv (normals only, hidden-1 assumed)."""
    s_a = (a >> 15) & 1
    s_b = (b >> 15) & 1
    exp_a = (a >> 7) & 0xFF
    exp_b = (b >> 7) & 0xFF
    m_a = 0x80 | (a & 0x7F)
    m_b = 0x80 | (b & 0x7F)

    exp_int = (exp_a + exp_b - 127) & 0x3FF  # logic [9:0]
    m_int = (m_a * m_b) & 0xFFFF

    s_o = s_a ^ s_b
    if m_int & 0x8000:
        exp_o = (exp_int + 1) & 0x1FF  # assign to [8:0]
        m_o = m_int
    else:
        exp_o = exp_int & 0x1FF
        m_o = ((m_int & 0x7FFF) << 1) & 0xFFFF

    exp_r = exp_o & 0xFF
    m_r = (m_o >> 8) & 0x7F

    bf16_o = (s_o << 15) | (exp_r << 7) | (m_r)

    return s_o, exp_o, m_o, bf16_o


async def apply_and_check(dut, a: int, b: int):
    dut.a_i.value = a
    dut.b_i.value = b
    await Timer(1, unit="ns")  # let combo logic settle

    exp_s, exp_e, exp_m, exp_bf16 = mul_bf16_ref(a, b)
    got_s = int(dut.s_o.value)
    got_e = int(dut.exp_o.value)
    got_m = int(dut.m_o.value)
    got_bf16 = int(dut.bf16_o.value)

    assert got_s == exp_s, f"sign a={a:#06x} b={b:#06x}: got {got_s} want {exp_s}"
    assert got_e == exp_e, f"exp  a={a:#06x} b={b:#06x}: got {got_e} want {exp_e}"
    assert got_m == exp_m, f"mant a={a:#06x} b={b:#06x}: got {got_m:#06x} want {exp_m:#06x}"
    assert got_bf16 == exp_bf16, f"bf16 a={a:#06x} b={b:#06x}: got {got_bf16:#06x} want {exp_bf16:#06x}"

@cocotb.test()
async def test_mul_ones(dut):
    """1.0 * 1.0 → sign=0, exp=127, mantissa product normalized."""
    one = pack_bf16(0, 127, 0)  # 1.0 in BF16
    await apply_and_check(dut, one, one)


@cocotb.test()
async def test_mul_signs(dut):
    """Sign should be XOR of input signs."""
    a = pack_bf16(1, 127, 0)  # -1.0
    b = pack_bf16(0, 127, 0)  # +1.0
    await apply_and_check(dut, a, b)


@cocotb.test()
async def test_mul_directed(dut):
    """A few normal BF16 values through the RTL-accurate model."""
    cases = [
        (pack_bf16(0, 128, 0), pack_bf16(0, 126, 0)),  # 2.0 * 0.5
        (pack_bf16(0, 127, 0x40), pack_bf16(0, 127, 0)),  # 1.5 * 1.0
        (pack_bf16(1, 130, 0x10), pack_bf16(1, 120, 0x20)),
    ]
    for a, b in cases:
        await apply_and_check(dut, a, b)


@cocotb.test()
async def test_mul_random(dut):
    """Random normals (avoid exp 0 / 255 — RTL assumes hidden 1)."""
    import random

    rng = random.Random(0)
    for _ in range(100):
        a = pack_bf16(rng.randint(0, 1), rng.randint(1, 254), rng.randint(0, 127))
        b = pack_bf16(rng.randint(0, 1), rng.randint(1, 254), rng.randint(0, 127))
        await apply_and_check(dut, a, b)
