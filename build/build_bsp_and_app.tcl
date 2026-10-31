set WS "D:/fpga_work/sdk_ws"
setws $WS
puts "projects: [getprojects]"
foreach b {yolov4_tiny_bsp zynq_fsbl_bsp} {
    if {[catch {regenbsp -bsp $b} e]} { puts "regenbsp $b -> ERROR: $e" } else { puts "regenbsp $b -> OK" }
}
catch {projects -clean} c; puts "clean: $c"
catch {projects -build} b; puts "build all: $b"
catch {projects -build -type app -name zynq_fsbl} f; puts "build fsbl: $f"
puts "=== products ==="
foreach f [list "$WS/yolov4_tiny/Debug/yolov4_tiny.elf" "$WS/zynq_fsbl/Debug/zynq_fsbl.elf"] {
    if {[file exists $f]} { puts "OK   $f ([file size $f] bytes)" } else { puts "MISS $f" }
}
puts "DONE"