# Repair the QSPI U-Boot environment

On some boards the QSPI U-Boot environment (`mtd1`, `qspi-uboot-env`) is missing
variables, so QSPI autoboot fails: `qspiboot` runs but `read_sf` is undefined,
`bootm` gets no kernel, and it falls into DFU (also broken, `dfu_sf_info`
undefined) then drops to the `PZSDR>` prompt.

The complete environment is present in the SD `uEnv.txt`. The fix is to restore
the missing variables to QSPI with `fw_setenv`.

## Missing variables

Compared against the stock `uEnv.txt`, the QSPI env lacked:
`qspiboot`, `read_sf`, `dfu_sf_info`, `dfu_ram_info`, `maxcpus`, `sdboot`.

## Apply

From Linux on the device (SSH `root@192.168.2.1`, password `analog`), with
`fw_setenv` configured for `/dev/mtd1` (see `/etc/fw_env.config`):

1. Extract the missing variables from a complete `uEnv.txt` into `fw_setenv`
   script form (`key value`, first `=` replaced by a space; value keeps its
   internal spaces and `=`):

   ```
   python3 - <<'PY'
   missing = {"qspiboot","read_sf","dfu_sf_info","dfu_ram_info","maxcpus","sdboot"}
   out = []
   for line in open("uEnv.txt"):
       line = line.rstrip("\n")
       if "=" in line:
           k, v = line.split("=", 1)
           if k in missing:
               out.append(k + " " + v)
   open("fw_fix.txt", "w").write("\n".join(out) + "\n")
   PY
   ```

2. Apply in batch (minimizes flash writes, handles CRC and erase):

   ```
   fw_setenv --script fw_fix.txt
   ```

3. Verify:

   ```
   fw_printenv read_sf qspiboot maxcpus
   ```

`fw_setenv` recomputes the environment CRC. If a write ever fails, U-Boot falls
back to its default environment and SD boot still works (it imports `uEnv.txt`),
so the board remains recoverable.

## Verify autoboot

Remove the SD card, keep the boot switch in the SD/QSPI position, and power
cycle. The board should boot QSPI straight to Linux (login prompt), not stop at
`PZSDR>` or enter DFU. The kernel cmdline will carry `uboot=U-Boot PZSDR-P201PRO
...` (added by `qspiboot`).

Verified on the tested board: QSPI autoboots to kernel 5.10, ethernet RX works
(`eth0 rx_packets` increments), `GPIO_CLK_CTRL = 0x11`.

## Note

This restores the boot environment only. The ethernet GPIO-clock bug is in the
FSBL, not the environment; see `ethernet-gpio-clk.md`. The original QSPI FSBL
already has the GPIO clock enabled, so QSPI boot does not need that fix.