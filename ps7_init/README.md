# Recovered ps7_init.tcl

`ps7_init.tcl` is the board-exact Zynq-7000 PS7 initialization for the PZSDR
P201Pro (XC7Z020, 1 GiB DDR3), recovered from the vendor FSBL and validated over
JTAG (DDR brings up, DDRC init-complete bit set, DDR reads return data).

The vendor publishes no design files, so this is provided for JTAG boot and
recovery. It is factual register-init data extracted from firmware on a board we
own; regenerate it from your own board with `../tools/gen_ps7_tcl.py` if your
firmware differs.

## Use

```
xsdb
connect
targets -set -filter {name =~ "ARM*#0"}
rst -system
source ps7_init.tcl
ps7_init
```

Phases: `ps7_mio_init` (MIO pinmux + DDRIOB), `ps7_pll_init` (ARM/DDR/IO PLLs with
lock polls), `ps7_clock_init`, `ps7_ddr_init` (DDRC timing + calibration polls),
`ps7_peripherals_init` (UART1/GPIO/USB). `ps7_init` runs them in order.

The arrays correspond to the silicon-version-3 path (`0xF8007080 = 0x30800100`).
See `../docs/ps7-init-format.md` for the data format and extraction method.

## Validation status

Validated for PS + DDR bring-up over JTAG. A full JTAG Linux boot using this
init reached the kernel on the tested board but hung in a spinlock before USB
gadget init; that hang is separate from the ethernet issue and is not resolved
here. For reliable booting use SD or QSPI (see `../docs/hardware.md`).