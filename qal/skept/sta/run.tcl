read_liberty /usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib
read_verilog $env(F)
link_design t
create_clock -name clk -period 20 [get_ports CLK]
set_clock_transition 0.15 [get_clocks clk]
catch { set_load $env(EXTLOAD) [get_nets q1] }
catch { set_load $env(EXTLOAD) [get_nets n1] }
set_input_delay 0 -clock clk [all_inputs -no_clocks]
report_checks -from F1 -to F2 -path_delay max -group_path_count 1 -digits 4
