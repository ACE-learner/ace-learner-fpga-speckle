# rerun_reports.tcl -- 重新打开同一实现，重跑时序/功耗/资源报告
# 用法（不需要打开 GUI，批处理模式）：
#   C:\Xilinx\Vivado\2018.3\bin\vivado.bat -mode batch -notrace ^
#       -source <本文件> -tclargs <输出目录>
# 说明：
#   - 打开的是 Vivado 工程里的 impl_1（与发布位流同一次实现）
#   - 报告输出到指定目录；若未给参数则输出到当前目录下的 rerun_reports_out/
#   - 运行结束后可对比 build/reports/ 下的原始报告

set OUT [expr {[llength $argv] > 0 ? [lindex $argv 0] : "./rerun_reports_out"}]
file mkdir $OUT
set XPR "D:/fpga_work/yolov4_tiny/yolov4_tiny_iptest/yolov4_tiny_iptest.xpr"
if {![file exists $XPR]} {
    puts "ERROR: project not found: $XPR"
    puts "       edit the XPR path at top of this script first."
    exit 1
}
puts "=== open project: $XPR ==="
open_project $XPR
puts "=== open implemented run: impl_1 ==="
open_run impl_1
puts "=== report timing ==="
report_timing_summary -file $OUT/timing_summary_rerun.rpt -delay_type min_max
report_timing -file $OUT/timing_top_paths.rpt -max_paths 20 -sort_by group
puts "=== report power ==="
report_power -file $OUT/power_rerun.rpt
puts "=== report utilization ==="
report_utilization -file $OUT/utilization_rerun.rpt
report_clock_utilization -file $OUT/clock_utilization_rerun.rpt
report_drc -file $OUT/drc_rerun.rpt
puts "=== RERUN DONE: $OUT ==="
close_project
exit 0
