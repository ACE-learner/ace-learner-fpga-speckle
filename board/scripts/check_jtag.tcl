# check_jtag.tcl —— 只检查 JTAG 链路，不下载任何东西
# 输出用固定标记，方便外层脚本解析
if {[catch {connect} err]} {
    puts "MARK_CONNECT=FAIL"
    puts "MARK_ERROR=$err"
    exit 1
}
puts "MARK_CONNECT=OK"

set tg [targets]
puts "MARK_TARGETS_BEGIN"
puts $tg
puts "MARK_TARGETS_END"

if {[string match "*xc7z020*" $tg]} {
    puts "MARK_FPGA=xc7z020"
} else {
    puts "MARK_FPGA=NONE"
}
if {[string match "*Cortex-A9*" $tg]} {
    puts "MARK_ARM=YES"
} else {
    puts "MARK_ARM=NO"
}
exit 0
