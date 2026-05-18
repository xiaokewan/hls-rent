#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 3/21/24 
# @Author  : Marieke Louage, Xiaoke Wang
# @Group   : UGent HES
# @File    : readvpr.py
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

    time_regex = r"The entire flow of VPR took ([\d.]+) seconds"
    cpd_regex = r"Final critical path delay \(least slack\): ([\d.]+) ns, Fmax: ([\d.]+) MHz"
    wirelength_regex = r"Total wirelength: ([\d]+), average net length: ([\d.]+)"
    estimate_distance_regex = r"BB estimate of min-dist \(placement\) wire length:\s+(\d+)"

    packing_time_regex = r"# Packing took ([\d.]+) seconds"
    routing_time_regex = r"# Routing took ([\d.]+) seconds"
    placement_time_regex = r"# Placement took ([\d.]+) seconds"
    fpga_size_regex = r"FPGA sized to (\d+) x (\d+) \(auto\)"

    # search existing data
    time = re.search(time_regex, content)
    cpd = re.search(cpd_regex, content)
    wirelength = re.search(wirelength_regex, content)
    estimate_distances = re.findall(estimate_distance_regex, content)
    packing_time = re.search(packing_time_regex, content)
    routing_time = re.search(routing_time_regex, content)
    placement_time = re.search(placement_time_regex, content)
    fpga_size = re.search(fpga_size_regex, content)
    if fpga_size:
        width = int(fpga_size.group(1))
        height = int(fpga_size.group(2))
        area = width * height  # Calculate the area
    else:
        width = height = area = None
    return {
        "time": float(time.group(1)) if time else None,
        "cpd": float(cpd.group(1)) if cpd else None,
        "fmax": float(cpd.group(2)) if cpd else None,
        "total_wirelength": int(wirelength.group(1)) if wirelength else None,
        "average_net_length": float(wirelength.group(2)) if wirelength else None,
        "estimate_distance_1": int(estimate_distances[0]) if len(estimate_distances) > 0 else None,
        "estimate_distance_2": int(estimate_distances[1]) if len(estimate_distances) > 1 else None,
        "packing_time": float(packing_time.group(1)) if packing_time else None,
        "routing_time": float(routing_time.group(1)) if routing_time else None,
        "placement_time": float(placement_time.group(1)) if placement_time else None,
        "fpga_size": f"{fpga_size.group(1)} x {fpga_size.group(2)}" if fpga_size else None,
        "fpga_area": area if area else None
    }


def extract_rent_exponent(filename):
    match = re.search(r"rent_exp_([0-9.]*[0-9])", filename)
    return float(match.group(1)) if match else None


def save_to_csv(data, filename):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


def fit_and_plot_exponential(filename, columns_to_fit):
    data = pd.read_csv(filename)

    def exponential_func(x, a, b, c):
        return a * np.exp(-b * x) + c

    fitted_parameters = {}
    for column in columns_to_fit:
        # Sort the data points based on the "rent_value" column
        sorted_data = data.sort_values(by='rent_exp')
        clean_data = sorted_data.dropna(subset=[column])

        if clean_data.empty:
            print(f"Warning: No data available for column '{column}' in file '{filename}'")
            continue

        try:
            popt, _ = curve_fit(exponential_func, clean_data['rent_exp'], clean_data[column])
            fitted_parameters[column] = popt
        except RuntimeError:
            print(f"Error: Unable to fit exponential curve for column '{column}' in file '{filename}'")
            continue
    colors = [
        '#1f77b4',  # muted blue
        '#ff7f0e',  # safety orange
        '#2ca02c',  # cooked asparagus green
        '#d62728',  # brick red
        '#9467bd',  # muted purple
        '#8c564b',  # chestnut brown
        '#e377c2',  # raspberry yogurt pink
        '#7f7f7f',  # middle gray
        '#bcbd22',  # curry yellow-green
        '#17becf'  # blue-teal
    ]

    num_plots = len(fitted_parameters)
    fig, axs = plt.subplots(num_plots, 1, figsize=(10, 6 * num_plots))

    for i, (column, popt) in enumerate(fitted_parameters.items()):
        fitted_values = exponential_func(clean_data['rent_exp'], *popt)  # Use clean_data here
        a, b, c = popt
        label = f'Original {column}\nFit: {a:.5f} * exp({-b:.2f} * r) + {c:.2f}'
        print(f"i:{i}, column:{column}, len_r_exp:{len(clean_data['rent_exp'])}, len:{len(clean_data[column])}")
        axs[i].scatter(clean_data['rent_exp'], clean_data[column], label=label,
                       color=colors[i % len(colors)])  # Use clean_data here
        axs[i].plot(clean_data['rent_exp'], fitted_values, label='', color=colors[i], linewidth=3, alpha=0.7)
        axs[i].set_xlabel('Rent Exponent')
        axs[i].set_ylabel('Value')
        axs[i].set_title(f'Exponential Fit for {column}')
        axs[i].legend()
        axs[i].grid(True)

    plt.tight_layout()
    directory = os.path.dirname(filename)
    plt.savefig(os.path.join(directory, 'rent_exp_influence2vpr_flow.png'))
    plt.show()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python readvpr.py <log_folder> <output_figures_folder>")
        sys.exit(1)

    log_folder = sys.argv[1]
    output_figures_folder = sys.argv[2]

    log_files = [os.path.join(root, f)
                 for root, dirs, files in os.walk(log_folder)
                 for f in files if f == "vpr_stdout.log"]

    data = []
    for filepath in log_files:
        log_data = {}
        log_data["rent_exp"] = extract_rent_exponent(filepath)
        log_data.update(parse_log_file(filepath))

        data.append(log_data)

    data = sorted(data, key=lambda x: x['rent_exp'])
    # rent_exps = [d["rent_exp"] for d in data]
    # cpds = [d["cpd"] for d in data]
    # times = [d["time"] for d in data]
    # total_wirelengths = [d["total_wirelength"] for d in data]

    # get the last name for having Blocks amount in csv name
    csv_filename = os.path.join(output_figures_folder, os.path.basename(os.path.dirname(log_folder)) + '_vpr_data.csv')
    save_to_csv(data, csv_filename)
    fit_and_plot_exponential(csv_filename, columns_to_fit=['time', 'cpd', 'total_wirelength', 'estimate_distance_1', 'estimate_distance_2', 'packing_time', 'routing_time', 'placement_time'])

    # example for using diff data plotting in a same graph
    # draw_fit_in_diff_files([ "./rent_sweep/norm_rent_sweep_10000/norm_rent_sweep_10000_vpr_data.csv", "./rent_sweep/norm_rent_sweep_15000/norm_rent_sweep_15000_vpr_data.csv", "./rent_sweep/norm_rent_sweep_20000/norm_rent_sweep_20000_vpr_data.csv"], columns_to_fit = ['time', 'cpd', 'total_wirelength'])
