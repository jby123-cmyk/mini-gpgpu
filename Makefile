REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

SIM ?= verilator
TOPLEVEL_LANG ?= verilog

FILELIST := $(REPO_ROOT)/rtl/design.f

# Expand filelist into real source paths for cocotb Make deps + Verilator inputs.
# (Do not put "-f ..." in VERILOG_SOURCES — Make treats "-f" as a missing target.)
VERILOG_SOURCES := $(shell grep -v '^\s*\#' $(FILELIST) | grep -v '^\s*$$' | grep -v '^+' | sed 's|^|$(REPO_ROOT)/|')

SIM_BUILD := $(REPO_ROOT)/build
COCOTB_RESULTS_FILE := $(SIM_BUILD)/results.xml

COCOTB_TOPLEVEL = counter
COCOTB_TEST_MODULES = tb.test_counter

LZ4_PREFIX := $(shell brew --prefix lz4)

COMPILE_ARGS += --trace --trace-fst --trace-structs \
	-CFLAGS "-std=c++17 -I$(LZ4_PREFIX)/include" \
	-LDFLAGS "-L$(LZ4_PREFIX)/lib -llz4"

WAVEFORM := $(SIM_BUILD)/dump.fst
SIM_ARGS += --trace --trace-file $(WAVEFORM)

include $(shell cocotb-config --makefiles)/Makefile.sim

# dump.fst is a side effect of the sim run that writes COCOTB_RESULTS_FILE
$(WAVEFORM): $(COCOTB_RESULTS_FILE)
	@test -f $@ || (echo "ERROR: expected waveform $@ was not produced" >&2; exit 1)

.PHONY: view
view: $(WAVEFORM)
	surfer $(WAVEFORM)