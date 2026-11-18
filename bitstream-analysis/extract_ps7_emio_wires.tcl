# Extract PS7 EMIO bel-pin -> PSS tile-wire mapping from Vivado.
# Setup mirrors prjxray fuzzers/076-ps7/generate.tcl (real project + open_io_design).
create_project -force -part xc7z020clg400-2 /home/ian/Code/pzsdr/prjxray-work/ps7proj
set_property design_mode PinPlanning [current_fileset]
open_io_design -name io_1

set fp [open "/home/ian/Code/pzsdr/prjxray-work/ps7_emio_wires.csv" w]
puts $fp "pin,wires,nodes"
set pins [get_bel_pins -of_objects [get_bels -of_objects [get_sites PS7* -of_objects [get_tiles PSS*]]]]
puts "total PS7 bel pins: [llength $pins]"
foreach pin $pins {
    set pname [lindex [split $pin "/"] 2]
    if {![string match "EMIO*" $pname]} { continue }
    set sitepin [get_site_pins -quiet -of_objects [get_bel_pins $pin]]
    set nodes [get_nodes -quiet -of_objects $sitepin]
    set wires [get_wires -quiet -of_objects $nodes]
    puts $fp "$pname,$wires,$nodes"
}
close $fp
puts "DONE wrote ps7_emio_wires.csv"
exit