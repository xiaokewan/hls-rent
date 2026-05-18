set repo_root [file normalize [lindex $argv 0]]
set hdl_dir [file join $repo_root dataflow_comm_scaling backend_smoke out hdl]
set run_dir [file join $repo_root dataflow_comm_scaling backend_smoke vivado_run]
set report_dir [file join $run_dir reports]
set part_name "xc7a200tsbg484-1"
set top_name "loop_multiply_wrapper"

file mkdir $run_dir
file mkdir $report_dir
cd $run_dir
file delete -force [file join $report_dir route_status.rpt]
file delete -force [file join $report_dir timing_summary.rpt]
file delete -force [file join $report_dir utilization.rpt]
file delete -force [file join $report_dir congestion.rpt]

read_verilog [glob -directory $hdl_dir *.v]
synth_design -top $top_name -part $part_name
create_clock -period 10.000 -name clk [get_ports clk]
opt_design
place_design
route_design

report_route_status -file [file join $report_dir route_status.rpt] -force
report_timing_summary -file [file join $report_dir timing_summary.rpt]
report_utilization -file [file join $report_dir utilization.rpt]

if {[catch {report_design_analysis -congestion -file [file join $report_dir congestion.rpt]} err]} {
  puts "WARNING: report_design_analysis -congestion failed: $err"
}

write_checkpoint -force [file join $run_dir routed.dcp]
