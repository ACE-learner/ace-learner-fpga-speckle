# run_on_board.tcl -- JTAG download (bitstream + ELF) and run
#
# Usage:
#   xsct.bat board/scripts/run_on_board.tcl
# Paths are package-relative: ../../board/bitstream/...
# Env override: FPGA_BIT_DIR (directory containing system_wrapper.bit / yolov4_tiny.elf / ps7_init.tcl)

set HERE [file dirname [info script]]
set BS   [file normalize [file join $HERE .. bitstream]]
if {[info exists env(FPGA_BIT_DIR)]} { set BS [file normalize $env(FPGA_BIT_DIR)] }

set BIT "$BS/system_wrapper.bit"
set ELF "$BS/yolov4_tiny.elf"
set PS7 "$BS/ps7_init.tcl"
foreach f [list $BIT $ELF $PS7] {
    if {![file exists $f]} { puts "ERROR: missing $f"; exit 1 }
}

puts "=== connect JTAG ==="
if {[catch {connect} err]} { puts "CONNECT FAILED: $err"; exit 1 }

puts "=== reset system ==="
if {[catch {
    targets -set -filter {name =~ "APU*"}
    rst -system
} e]} { puts "rst -system: $e" }
after 3000

puts "=== download bitstream ==="
targets -set -filter {name =~ "APU*"}
fpga -file $BIT

puts "=== load ps7_init (DDR/clock/MIO) ==="
source $PS7
targets -set -filter {name =~ "ARM*#0"}
ps7_init
ps7_post_config

puts "=== allow memory access ==="
catch {configparams force-mem-access 1}

puts "=== download ELF and run ==="
dow $ELF
con

puts "=== DONE: program started, watch UART 115200 ==="
exit 0
