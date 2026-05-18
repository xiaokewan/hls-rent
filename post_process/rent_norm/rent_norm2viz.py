#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 4/8/24 
# @Author  : Xiaoke Wang
# @Group   : UGent HES
# @File    : rent_norm2viz.py
# @Software: PyCharm, Ghent

import os
import pickle
import matplotlib.pyplot as plt
import numpy as np
import statsmodels.api as sm
import sys
# from sklearn.linear_model import LinearRegression, RANSACRegressor
from statsmodels.nonparametric.kernel_regression import KernelReg
from sklearn import datasets, linear_model, kernel_ridge
# from post_process.merge2csv import merge_to_csv


def rent_norm(t_dic, r):
    weighted_blocks = []
    for bl_dic in t_dic:
        w = 0
        for vertice in bl_dic:
            w += (bl_dic[vertice])*(vertice**(1/r))
        weighted_blocks.append(w)
    return np.array(weighted_blocks)


def calculate_bin_means(rent_data_flat, blocks, n_bins):
    # Bin data
    max_blocks = blocks.max()
    bin_factor = max_blocks ** (1 / n_bins)
    bin_values = np.round(bin_factor ** np.arange(1, n_bins + 1))
    bin_values[-1] += 1  # Ensure covering max value

    # Mean and median per bin
    bin_means = []
    for i in range(n_bins):
        bin_mask = (blocks <= bin_values[i]) if i == 0 else ((blocks > bin_values[i - 1]) & (blocks <= bin_values[i]))
        bin_data = rent_data_flat[bin_mask]
        if bin_data.size > 0:
            blocks_mean = bin_data[:, 0].mean()
            pins_median = np.median(bin_data[:, 1])
            bin_means.append([blocks_mean, pins_median])

    bin_means = np.array(bin_means)
    return bin_means


def calculate_bin_means_norm(rent_data_flat, blocks, n_bins):
    # Bin data
    max_blocks = blocks.max()
    bin_factor = max_blocks ** (1 / n_bins)
    bin_values = np.round(bin_factor ** np.arange(1, n_bins + 1))
    bin_values[-1] += 1  # Ensure covering max value

    # Mean and median per bin
    bin_means = []

    for i in range(1, n_bins):
        bin_mask = (blocks > bin_values[i - 1]) & (blocks <= bin_values[i])
        bin_data = rent_data_flat[bin_mask]
        pin_bin_data = rent_data_flat[:, 1][bin_mask]
        blocks_bin_data = blocks[bin_mask]
        if bin_data.size > 0:
            blocks_mean = blocks_bin_data.mean()
            pins_median = np.mean(pin_bin_data)
            bin_means.append([blocks_mean, pins_median])

    bin_means = np.array(bin_means)
    return bin_means


def trend_line_ml(data):
    X = data[:, 0].reshape(-1, 1)
    # X = data[:, 0]
    y = data[:, 1]


    # # huber = linear_model.HuberRegressor(max_iter=1000, alpha=0.1, epsilon=4)
    # huber = linear_model.HuberRegressor(max_iter=1000, alpha=0.1, epsilon=1.0)
    # model = huber
    # model.fit(X, y)
    # # inlier_mask = model.inlier_mask_
    # # outlier_mask = np.logical_not(inlier_mask)
    # outlier_mask = model.outliers_
    # line = model.predict(X)
    # coef = model.coef_[0]
    #
    ransac = linear_model.RANSACRegressor(max_trials=30, min_samples=1000, residual_threshold=2.0, random_state=42)
    model = ransac
    model.fit(X, y)
    inlier_mask = ransac.inlier_mask_
    outlier_mask = np.logical_not(inlier_mask)
    line = model.predict(X)
    coef = model.estimator_.coef_[0]
    return line, coef, outlier_mask


def trend_line(data, filter=True, slope_threshold=0.3):
    if filter:
        filtered_data = []
        slopes = []
        for i in range(1, len(data) - 1):
            slope = (data[i, 1] - data[i - 1, 1]) / (data[i, 0] - data[i - 1, 0]) \
                if (data[i, 0] - data[i - 1, 0]) != 0 else 0
            slopes.append(slope) if i == 1 else None
            if (abs(slope - slopes[i-1]) <= slope_threshold) or i < 4: # 2*len(data)/5:
                if i == 1:
                    filtered_data.append(data[i - 1])
                filtered_data.append(data[i])
                slopes.append(slope)
            else:
                break
        if not filtered_data:
            return None, None, None, None
    else:
        filtered_data = data

    # filtered data for trend line
    filtered_data = np.array(filtered_data)
    x, y = filtered_data[:, 0], filtered_data[:, 1]
    x_mean, y_mean = x.mean(), y.mean()
    x_err, y_err = x - x_mean, y - y_mean
    a = (x_err * y_err).sum() / (x_err ** 2).sum()
    b = y_mean - a * x_mean
    error = np.sum((y - (a * x + b)) ** 2) / len(filtered_data)

    return np.array([[x[0], a * x[0] + b], [x[-1], a * x[-1] + b]]), a, b, error


# def trend_line(data, filter=True, slope_threshold=(0.25, 1)):
#     if filter:
#         filtered_data = []
#         for i in range(1, len(data)):
#             slope = (data[i, 1] - data[i - 1, 1]) / (data[i, 0] - data[i - 1, 0]) if (data[i, 0] - data[i - 1, 0]) != 0 else 0
#             if slope_threshold[0] <= slope <= slope_threshold[1]:
#                 filtered_data.append(data[i - 1])
#                 filtered_data.append(data[i])
#         if not filtered_data:
#             return None, None, None, None
#     else:
#         filtered_data = data
#
#     # filtered data for tend line
#     filtered_data = np.array(filtered_data)
#     x, y = filtered_data[:, 0], filtered_data[:, 1]
#     x_mean, y_mean = x.mean(), y.mean()
#     x_err, y_err = x - x_mean, y - y_mean
#     a = (x_err * y_err).sum() / (x_err ** 2).sum()
#     b = y_mean - a * x_mean
#     error = np.sum((y - (a * x + b)) ** 2) / len(filtered_data)
#
#     return np.array([[x[0], a * x[0] + b], [x[-1], a * x[-1] + b]]), a, b, error


def visualize_rent(rent_path, output_filename='Rents_rule_real.png', output_figures_folder="."):
    if not rent_path.endswith('.rent'):
        raise ValueError(f"Expected a .rent file, got {rent_path} instead.")
    with open(rent_path, "rb") as fp:  # Unpickling
        rent_data = pickle.load(fp)

    # Flatten data
    rent_data_flat = np.array([point for level in rent_data for point in level])
    blocks, pins = rent_data_flat[:, 0], rent_data_flat[:, 1]
    t_dic = rent_data_flat[:, 2]

    # bins and trend line
    n_bins = len(rent_data)
    bin_means = calculate_bin_means(rent_data_flat[:, 0:2], blocks, n_bins)
    log_bin_means = np.log2(bin_means)
    line, slope, _, _ = trend_line(log_bin_means)

    # normalizing
    norm_blocks = rent_norm(t_dic, slope)
    # y_predict, slope, outlier_mask = trend_line_ml(np.stack((np.log2(norm_blocks.astype(float)), np.log2(pins.astype(float))), axis=1))

    # # calculate norm bin means
    bin_means = calculate_bin_means_norm(rent_data_flat[:, 0:2], norm_blocks, (np.floor(np.log2(norm_blocks.max()))).astype(int))
    # # using the filter
    line, slope, _, _ = trend_line(np.log2(bin_means), True)

    print(f"    Current net's normalized rent's exponent is {slope}")


    for i in range(20):
        prev_slope = slope
        # if i != 0 and abs(prev_slope - slope) <= 0.01 :
        #     print(f"{i}: slope {slope} : prev_slope {prev_slope}")
        #     break
        norm_blocks = rent_norm(t_dic, slope)
        bin_means = calculate_bin_means_norm(rent_data_flat[:, 0:2], norm_blocks,
                                             (np.floor(np.log2(norm_blocks.max()))).astype(int))
        line, slope, _, _ = trend_line(np.log2(bin_means), True)
        print(f"    After {i} loop recursive net's normalized rent's exponent is {slope}")

    plt.figure(figsize=(12, 9))

    ## data points
    plt.scatter(norm_blocks, pins, alpha=0.1, label='Data Points')

    ## linear-regression line
    # plt.plot(norm_blocks, np.exp2(y_predict), color='red', label=f'Trend Line ML (Slope: {slope:.2f})')
    # plt.scatter(norm_blocks[outlier_mask], pins[outlier_mask], color="gold", marker=".", label="Outliers")

    ## bin dots
    plt.scatter(bin_means[:, 0], bin_means[:, 1], s=100, color='red', alpha=0.85, edgecolors='w', linewidths=2,
                marker='o', label='Bin Means')
    # bin means line
    plt.plot(np.exp2(line[:, 0]), np.exp2(line[:, 1]), color='black', linewidth=2, linestyle='--',
             label=f'Slope (r) = {slope:.4f}')
    plt.xscale("log", base=2)
    plt.yscale("log", base=2)
    # after normalization, the x-axis changed to the summation
    plt.subplots_adjust(bottom=0.15)
    plt.xlabel(r'$B_{tot} = \sum_{i=1}^{n} w_i \cdot B_i$', size=20)
    plt.ylabel('$T$ (Terminals)', size=25)

    plt.title('Rent\'s Rule Visualization After Normalization', size=25)
    plt.legend(fontsize=15)

    os.makedirs(output_figures_folder, exist_ok=True)
    plt.savefig(os.path.join(output_figures_folder, output_filename))
    # plt.show()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 rent2viz.py <rent_file_path>  <output_figures_folder>")
        sys.exit(1)

    rent_file_path = sys.argv[1]
    output_figures_folder = sys.argv[2]
    output_filename = os.path.basename(rent_file_path) + "_norm_viz.png"
    visualize_rent(rent_file_path, output_filename, output_figures_folder)
    print(f"Visualization saved to {output_filename}")
