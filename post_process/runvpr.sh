#!/bin/bash

# README:
# This script is designed to run VPR (Verilog-to-Routing) tool on BLIF files.
#
# Usage:
# ./script.sh <work_dir_path> <options>
#
# Options:
#   -v, --vpr <on/off>          "on" to run VPR, "off" to skip VPR execution.
#   -b, --blif <blif_file1> <blif_file2> ... Optional list of BLIF files to process. If not provided, all BLIF files in the specified directory will be processed.
#   -h, --help                   Display this help message.
#
# Example:
# ./script.sh /path/to/work_dir -v on -b blif_file1.blif blif_file2.blif
WORK_DIR=$1
VPR_RUN=${2:-"on"} 
PAR="on"
source config.sh
usage() {
    cat <<EOF
    
README:
 This script is designed to run VPR (Verilog-to-Routing) tool on BLIF files.

Usage:
 ./script.sh <work_dir_path> <options>

Options:
   -v, --vpr <on/off>          "on" to run VPR, "off" to skip VPR execution.
   -b, --blif <blif_file1> <blif_file2>... Optional list of BLIF files to process. If not provided, all BLIF files in the specified directory will be processed.
   -h, --help                   Display this help message.

 Example:
 ./script.sh /path/to/work_dir -v on -b blif_file1.blif blif_file2.blif
EOF
}

if [[ -z "$WORK_DIR" || "$1" == "-h" || "$1" == "--help" ]]; then
    usage
    exit 1
fi

shift # skip 1st one

# Parse command line options
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -v|--vpr)
            VPR_RUN="$2"
            shift 2
            ;;
        -b|--blif)
            BLIF_FILES=("${@:2}")
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

echo "${BLIF_FILES[@]}"


# If no BLIF file parameters are provided, process all BLIF files
if [ ${#BLIF_FILES[@]} -eq 0 ]; then
    BLIF_FILES=()
    for blif_file in "$WORK_DIR"/*.blif; do
        [ -f "$blif_file" ] && BLIF_FILES+=("$(basename "$blif_file")")
    done
fi


if [ "$VPR_RUN" == "on" ] && [ "$PAR" != "on" ]; then
    if [ -d "$WORK_DIR" ]; then
        cd $PROJECT_ROOT/$WORK_DIR
        mkdir -p vpr_files

        for blif_file in $BLIF_FILES; do
            mkdir -p $PROJECT_ROOT/$WORK_DIR/vpr_files/$blif_file
            cd $PROJECT_ROOT/$WORK_DIR/vpr_files/$blif_file
            echo "Running VPR for $blif_file"
            $VTR_ROOT/vpr/vpr $VTR_ROOT/vtr_flow/arch/titan/stratixiv_arch.timing.xml $PROJECT_ROOT/$WORK_DIR/$blif_file
        done

    elif [ -f "$WORK_DIR" ]; then
        echo "When providing individual BLIF files, the WORK_DIR argument should be the directory where the BLIF files are located."
        exit 1
    else
        echo "Invalid input. Please provide either a directory containing BLIF files or individual BLIF files."
        exit 1
    fi
fi

# Still no clue why the env will change of $VTR_ROOT, update your own path to vpr and vtr here👇, also make sure $PAR="on" defined before
vtr="/home/xiaokewan/Software/vtr-verilog-to-routing-master"
vpr="/home/xiaokewan/Software/vtr-verilog-to-routing-master/vpr/vpr"
PROJECT_ROOT="$PROJECT_ROOT"

if [ "$VPR_RUN" == "on" ] && [ "$PAR" == "on" ]; then
    echo "Start GNU parallel computing: ${BLIF_FILES[@]}"
    parallel -j 3 "mkdir -p $PROJECT_ROOT/$WORK_DIR/vpr_files/{} && cd $PROJECT_ROOT/$WORK_DIR/vpr_files/{} && $vpr $vtr/vtr_flow/arch/titan/stratixiv_arch.timing.xml $PROJECT_ROOT/$WORK_DIR/{}  --write_rr_graph ./stratixiv_arch_$WORK_DIR_{}.xml" ::: "${BLIF_FILES[@]}"
fi
