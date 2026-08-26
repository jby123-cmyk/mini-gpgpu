# mini-gpgpu

WIP - minimal implementation of a gpgpu with a systolic array tensor accelerator.

### Layout

```
rtl/           # systemverilog sources design filelist
tb/            # cocotb Python tests
build/         # generated: Vtop, results.xml, dump.fst
Makefile       # cocotb wrapper
```

### Requirements

MacOS + Homebrew targeted workflow

Install the tools:

```bash
brew install verilator surfer lz4
```

`lz4` is needed because we dump FST waves (`dump.fst`), which Verilator compresses with LZ4.

Python setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "cocotb~=2.0"
```

Apple Silicon Homebrew is required `PATH` (`/opt/homebrew/bin`), not Rosetta (`/usr/local`).

### Simulation config

1. **Filelist** — list RTL paths in `rtl/design.f`, one per line, relative to the repo root:
  ```
   rtl/counter.sv
   rtl/bruh.sv
  ```
2. **Top module** — set `COCOTB_TOPLEVEL` in the Makefile to the **Verilog module name** (not the filename):
  ```makefile
   COCOTB_TOPLEVEL = counter
  ```
3. **Tests** — set `COCOTB_TEST_MODULES` to the Python import path of your cocotb test module(s):
  ```makefile
   COCOTB_TEST_MODULES = tb.test_counter
  ```



### Commands

Activate the venv first (`source .venv/bin/activate`), then from the repo root:


| Command             | What it does                                                                                                           |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `make` / `make sim` | Always re-runs the sim. Verilates RTL, builds `build/Vtop`, runs cocotb, writes `build/results.xml` + `build/dump.fst` |
| `make view`         | Opens `build/dump.fst` in Surfer. Builds/runs the sim first if results/waves are missing or stale                      |
| `make clean`        | rm -rf build artifacts (cocotb's clean target)                                                                         |


Example inline overrides:

```bash
make COCOTB_TOPLEVEL=counter COCOTB_TEST_MODULES=tb.test_counter
make COCOTB_TESTCASE=test_counts view
```



### What's in `build/`

- `Vtop` / `Vtop.mk` — Verilator-generated simulator
- `results.xml` — cocotb pass/fail report
- `dump.fst` — waveform for Surfer



### Smoke test

With the defaults (`counter` + `tb.test_counter`):

```bash
source .venv/bin/activate
make sim
make view
```

You should see the cocotb test pass, then Surfer open with `clk` / `rst` / `count`.