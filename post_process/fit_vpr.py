#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 4/12/24 
# @Author  : Xiaoke Wang
# @Group   : UGent HES
# @File    : fit_vpr.py
# @Software: PyCharm, Ghent
import sys, os

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import os


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

    num_plots = len(fitted_parameters)
    fig, axs = plt.subplots(num_plots, 1, figsize=(10, 6 * num_plots))

    for i, (column, popt) in enumerate(fitted_parameters.items()):
        fitted_values = exponential_func(clean_data['rent_exp'], *popt)  # Use clean_data here
        axs[i].scatter(clean_data['rent_exp'], clean_data[column], label=f'Original {column}')  # Use clean_data here
        axs[i].plot(clean_data['rent_exp'], fitted_values, label=f'Fitted {column}')
        axs[i].set_xlabel('Rent Exponent')
        axs[i].set_ylabel('Value')
        axs[i].set_title(f'Exponential Fit for {column}')
        axs[i].legend()
        axs[i].grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('Usage: python fit_vpr.py <directory_path>')
        sys.exit(1)

    directory_path = sys.argv[1]

    # Check if the directory exists
    if not os.path.isdir(directory_path):
        print(f'Error: {directory_path} is not a valid directory.')
        sys.exit(1)

    # Get all CSV files in the directory
    csv_files = [file for file in os.listdir(directory_path) if file.endswith('.csv')]

    if len(csv_files) == 0:
        print(f'No CSV files found in {directory_path}.')
        sys.exit(1)

    # Process each CSV file
    for filename in csv_files:
        full_path = os.path.join(directory_path, filename)
        columns_to_fit = ['time', 'cpd', 'total_wirelength']
        print(f'Processing file: {full_path}')
        fit_and_plot_exponential(full_path, columns_to_fit)