#!/usr/bin/bash
# -*- coding: utf-8 -*-
# @Time    : 3/21/24 
# @Author  : Xiaoke Wang
# @Group   : UGent HES
# @File    : post_process.py
# @Software: PyCharm, Ghent

#!/bin/bash

# This script processes BLIF files in a specified working directory using netlist2rent.py and rent2viz.py,
# and optionally reads VPR results with readvpr.py. It supports enabling or disabling specific parts of the process.
# Usage: ./post_process.sh <work_dir_path> -n [on|off] -v [on|off] -r [on|off] 


# Parameters:
#   <work_dir_path>: Mandatory. The path to the working directory containing BLIF files and where output files will be generated.
#   -n --net2rent [on|off]: blif to rent hypergraph, default 'on'. Optional. whether to run netlist2rent.py.
#   -v --viz [on|off]: rent hypergraph to figure, default 'on'. Optional. whether to run rent2viz.py.
#                recommend: <work_dir_path> will search .rent files in the current folder and sub-folder
#   -b --blif <blif_file1> <blif_file2>...: Optional list of BLIF files to process. If not provided, all BLIF files in the directory will be processed.
#   -r -- read [on|off]: Read VPR results for runtime critical pathlength ..., default is 'off'. Optional. whether to run readvpr.py to process VPR results. Default is 'off'.
#   -m --norm [on|off]: Using normalization rent_graph. Default is off.
#   -h help
WORK_DIR=$1
RUN_NETLIST2RENT="on"
RUN_RENT2VIZ="off"
READ_VPR="off"
COMP="off"
NORM="off"
BLIF_FILES=()
PYTHON="/home/xiaokewan/Software/anaconda3/bin/python"

usage() {
  echo "Usage: $0 <work_dir_path> -n [*on*|off] -v [*on*|off] -r [on|*off*] -m [on|off]"
  echo "  -n  [*on*|off]: blif to rent hypergraph, default 'on'."
  echo "  -b  [on|*off*]: blif files will be proceeded, default 'off'."
  echo "  -v  [*on*|off]: rent hypergraph to figure, default 'on'."
  echo "  -r  [on|*off*]: Read VPR results for runtime critical pathlength ..., default is 'off'."
  echo "  -b  [blif files]: Specify the blif files."
#  echo "  -c  [on|*off*]: Compare the result in different size. Default is off."
  echo "  -m  [on|*off*]: Using normalization rent_graph. Default is off."
  exit 0
}
if [ $# -eq 0 ] || [ "$1" == "-h" ]; then
  usage
fi

source "./config.sh"


shift # shift arguments


while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--net2rent)
      RUN_NETLIST2RENT="$2"
      shift 2
      ;;
    -v|--viz)
      RUN_RENT2VIZ="$2"
      shift 2
      ;;
    -r|--read)
      READ_VPR="$2"
      shift 2
      ;;
    -b|--blif)
      shift
      while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
        BLIF_FILES+=("$1")
        shift
      done
      ;;
    -m|--norm)
      NORM="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done


if [ -f "$WORK_DIR" ]; then
  WORK_DIR=$(dirname "${WORK_DIR}")
fi

if [ ! -d "$WORK_DIR" ]; then
    echo "Error: $WORK_DIR is not a valid directory"
    exit 1
fi

#$WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
cd "$PROJECT_ROOT/$WORK_DIR" || exit
	
# netlist2rent.py: Transfer the .blif to Hypergraph
if [ "$RUN_NETLIST2RENT" == "on" ]; then

    if [ ${#BLIF_FILES[@]} -eq 0 ]; then
        BLIF_FILES=($(find ./ -type f -name "*.blif"))
    fi
    for blif_file in "${BLIF_FILES[@]}"; do
 
        if [ "$NORM" == "off" ]; then
            echo "Processing $blif_file with netlist2rent.py"
            $PYTHON "$POST_DIR/netlist2rent.py" "$blif_file" "$PROJECT_ROOT/$WORK_DIR/rent_files" "$HMETIS_DIR"
        else
            echo "Processing $blif_file with nl2norm_rent.py"
            $PYTHON "$POST_DIR/rent_norm/nl2norm_rent.py" "$blif_file" "$PROJECT_ROOT/$WORK_DIR/rent_files" "$HMETIS_DIR"
        fi
    done
fi

# rent2viz.py: visualized partitioned netlist (rent graph)
if [ "$RUN_RENT2VIZ" == "on" ]; then
    if [ ${#BLIF_FILES[@]} -eq 0 ]; then
        RENT_FILES=($(find ./ -type f -name "*.rent"))
    else
        RENT_FILES=()
        for blif_file in "${BLIF_FILES[@]}"; do
            rent_file="rent_files/${blif_file}.rent"
            if [ -f "$rent_file" ]; then
                RENT_FILES+=("$rent_file")
            else
                echo "File NOT found: $rent_file"
            fi
        done
    fi

    for rent_file in "${RENT_FILES[@]}"; do
	      echo -e "\nRentFIle: $rent_file"
        if [ -f "$rent_file" ]; then  
            if [ "$NORM" == "off" ]; then
                echo -e "  Visualizing $rent_file with rent2viz.py"
                $PYTHON "$POST_DIR/rent2viz.py" "$rent_file" "$PROJECT_ROOT/$WORK_DIR/rent_figures"
            else
                echo -e "  Visualizing $rent_file with rent_norm2viz.py"
                $PYTHON "$POST_DIR/rent_norm/rent_norm2viz.py" "$rent_file" "$PROJECT_ROOT/$WORK_DIR/rent_figures"
            fi
        else
            echo "Warning: Expected rent file does not exist - $rent_file"
        fi
    done
fi


# read vpr results (vpr_files)
if [ "$READ_VPR" == "on" ]; then
    echo "Processing VPR results with readvpr.py from $POST_DIR working in $WORK_DIR"
    $PYTHON "$POST_DIR/readvpr.py" "$PROJECT_ROOT/$WORK_DIR/vpr_files" "$PROJECT_ROOT/$WORK_DIR"
fi

if [ "$COMP" == "on" ]; then
  echo "Comparing Diff VPR results in $WORK_DIR"
  $PYTHON "$POST_DIR/compvpr.py" "$PROJECT_ROOT/$WORK_DIR"
fi
cd - > /dev/null || exit
