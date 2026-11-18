create_project -force -part xc7z020clg400-2 /home/ian/Code/pzsdr/prjxray-work/emio-fuzz/proj2
create_bd_design "design_1"
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 processing_system7_0
set_property -dict [list CONFIG.PCW_ENET0_PERIPHERAL_ENABLE {1} CONFIG.PCW_ENET0_ENET0_IO {EMIO} CONFIG.PCW_ENET0_GRP_MDIO_ENABLE {1} CONFIG.PCW_ENET0_GRP_MDIO_IO {EMIO} CONFIG.PCW_USE_M_AXI_GP0 {0} CONFIG.PCW_USE_FABRIC_INTERRUPT {0}] [get_bd_cells processing_system7_0]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" Master "Disable" Slave "Disable"} [get_bd_cells processing_system7_0]
foreach {sig dir} {ENET0_MDIO_MDC O ENET0_MDIO_O O ENET0_MDIO_T O ENET0_MDIO_I I} {
    create_bd_port -dir $dir $sig
    connect_bd_net [get_bd_pins processing_system7_0/$sig] [get_bd_ports $sig]
}
save_bd_design
generate_target all [get_files *.bd]
make_wrapper -files [get_files *.bd] -top -import
add_files -fileset constrs_1 /home/ian/Code/pzsdr/prjxray-work/emio-fuzz/mdio.xdc
set_property top design_1_wrapper [current_fileset]
launch_runs synth_1 -jobs 4
wait_on_run synth_1
open_run synth_1
place_design
route_design
puts "=== MDIO NET WIRES BEGIN ==="
foreach p [get_ports -quiet ENET0_MDIO_*] {
    set n [get_nets -quiet -of_objects [get_ports $p]]
    puts "PORT $p NET $n"
    puts "  NODES: [get_nodes -quiet -of_objects [get_nets $n]]"
    puts "  NODEWIRES: [get_wires -quiet -of_objects [get_nodes -quiet -of_objects [get_nets $n]]]"
    puts "  BELPINS: [get_bel_pins -quiet -of_objects [get_nets $n]]"
}
puts "--- all nets matching enet/mdio/emio (nocase) ---"
foreach n [get_nets -quiet -hier *] {
    set nm [get_property NAME $n]
    if {[string match -nocase "*mdio*" $nm] || [string match -nocase "*enet0*" $nm]} {
        puts "NET $nm : [get_wires -quiet -of_objects [get_nets $n]]"
    }
}
puts "--- PS7 EMIO bel pin wires ---"
foreach bp [get_bel_pins -quiet -of_objects [get_bels -quiet -of_objects [get_sites PS7*]]] {
    set bn [get_property NAME $bp]
    if {[string match "*EMIOENET0MDIO*" $bn] || [string match "*EMIOENET0GMIIRXD*" $bn]} {
        puts "BELPIN $bn"
        puts "  WIRES: [get_wires -quiet -of_objects [get_bel_pins $bp]]"
        puts "  NODES: [get_nodes -quiet -of_objects [get_bel_pins $bp]]"
    }
}
puts "=== MDIO NET WIRES END ==="
exit
