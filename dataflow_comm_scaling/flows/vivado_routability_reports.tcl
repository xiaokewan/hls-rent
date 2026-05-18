# Generate routability-related Vivado reports from an implemented design.
#
# Usage inside Vivado:
#   vivado -mode batch -source dataflow_comm_scaling/flows/vivado_routability_reports.tcl \
#     -tclargs reports/vivado/aes
#
# If a project run named impl_1 exists, the script opens it. Otherwise it
# assumes the current in-memory design is already placed/routed.

set out_dir "vivado_routability_reports"
if {$argc >= 1} {
  set out_dir [lindex $argv 0]
}
file mkdir $out_dir

if {[llength [get_runs impl_1 -quiet]] > 0} {
  open_run impl_1
}

report_route_status -file [file join $out_dir route_status.rpt] -force
report_timing_summary -file [file join $out_dir timing_summary.rpt] -force
report_utilization -file [file join $out_dir utilization.rpt] -force

if {![catch {report_design_analysis -congestion -file [file join $out_dir congestion.rpt] -force} err]} {
  puts "Wrote congestion report"
} else {
  puts "WARNING: report_design_analysis -congestion failed: $err"
}

if {![catch {report_qor_suggestions -file [file join $out_dir qor_suggestions.rpt] -force} err]} {
  puts "Wrote QoR suggestions report"
} else {
  puts "WARNING: report_qor_suggestions failed: $err"
}
