#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 5/19/24 
# @Author  : Xiaoke Wang
# @Group   : UGent HES
# @File    : readvpr_bm.py
# @Software: PyCharm, Ghent


import os
import re
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import sys
import csv
import pandas as pd
import numpy as np


def parse_log_file(filepath):
    with open(filepath, 'r') as file:
        content = file.read()
    blocks_regex = r"Circuit Statistics:\s+Blocks: (\d+)"
    time_regex = r"The entire flow of VPR took ([\d.]+) seconds"
    cpd_regex = r"Final critical path delay \(least slack\): ([\d.]+) ns"
    wirelength_regex = r"Total wirelength: ([\d]+), average net length: ([\d.]+)"
    estimate_distance_regex = r"BB estimate of min-dist \(placement\) wire length:\s+(\d+)"
    packing_time_regex = r"# Packing took ([\d.]+) seconds"
    routing_time_regex = r"# Routing took ([\d.]+) seconds"
    placement_time_regex = r"# Placement took ([\d.]+) seconds"
    fpga_size_regex = r"FPGA sized to (\d+) x (\d+) \(auto\)"

    # search existing data
    blocks = re.search(blocks_regex, content)
    time = re.search(time_regex, content)
    cpd = re.search(cpd_regex, content)
    wirelength = re.search(wirelength_regex, content)
    estimate_distances = re.findall(estimate_distance_regex, content)
    fpga_size = re.search(fpga_size_regex, content)
    if fpga_size:
        width = int(fpga_size.group(1))
        height = int(fpga_size.group(2))
        area = width * height  # Calculate the area
    else:
        width = height = area = None

    packing_time = re.search(packing_time_regex, content)
    routing_time = re.search(routing_time_regex, content)
    placement_time = re.search(placement_time_regex, content)
    return {
        "blocks": int(blocks.group(1)) if blocks else None,
        "time": float(time.group(1)) if time else None,
        "cpd": float(cpd.group(1)) if cpd else None,
        # "fmax": float(cpd.group(2)) if cpd else None,
        "total_wirelength": int(wirelength.group(1)) if wirelength else None,
        "average_net_length": float(wirelength.group(2)) if wirelength else None,
        "estimate_distance_1": int(estimate_distances[0]) if len(estimate_distances) > 0 else None,
        "estimate_distance_2": int(estimate_distances[1]) if len(estimate_distances) > 1 else None,
        "packing_time": float(packing_time.group(1)) if packing_time else None,
        "routing_time": float(routing_time.group(1)) if routing_time else None,
        "placement_time": float(placement_time.group(1)) if placement_time else None,
        "fpga_size": f"{width} x {height}" if fpga_size else None,
        "fpga_area": area if area else None
    }


# def extract_rent_exponent(filename):
#     match = re.search(r"rent_exp_([0-9.]*[0-9])", filename)
#     return float(match.group(1)) if match else None


def save_to_csv(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)





if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python readvpr_bm.py <log_folder> <output_figures_folder>")
        sys.exit(1)

    log_folder = sys.argv[1]
    output_figures_folder = sys.argv[2]

    log_files = [os.path.join(root, f)
                 for root, dirs, files in os.walk(log_folder)
                 for f in files if f == "vpr_stdout.log"]

    data = []
    for filepath in log_files:
        log_data = {}
        directory_name = os.path.basename(os.path.dirname(filepath))
        log_data["name"] = os.path.splitext(directory_name)[0]
        log_data.update(parse_log_file(filepath))

        data.append(log_data)

    # get the last name for having Blocks amount in csv name
    csv_filename = os.path.join(output_figures_folder, os.path.basename(os.path.dirname(log_folder)) + '_vpr_data.csv')
    save_to_csv(data, csv_filename)

    # example for using diff data plotting in a same graph
    # draw_fit_in_diff_files([ "./rent_sweep/norm_rent_sweep_10000/norm_rent_sweep_10000_vpr_data.csv", "./rent_sweep/norm_rent_sweep_15000/norm_rent_sweep_15000_vpr_data.csv", "./rent_sweep/norm_rent_sweep_20000/norm_rent_sweep_20000_vpr_data.csv"], columns_to_fit = ['time', 'cpd', 'total_wirelength'])
