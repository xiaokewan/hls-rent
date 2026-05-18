#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 3/20/24 
# @Author  : Marieke Louage, Xiaoke Wang
# @Group   : UGent HES
# @File    : rent2viz.py.py
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


# def trend_line(data):
#     x, y = data[:, 0], data[:, 1]
#     x_mean, y_mean = x.mean(), y.mean()
#     x_err, y_err = x - x_mean, y - y_mean
#     a = (x_err * y_err).sum() / (x_err ** 2).sum()
#     b = y_mean - a * x_mean
#     error = np.sum((y - (a * x + b)) ** 2) / len(data)
#     return np.array([[x[0], a * x[0] + b], [x[-1], a * x[-1] + b]]), a, b, error


def trend_line(data, slope_threshold=0.4):
    filtered_data = []
    slopes = []
    for i in range(1, len(data) - 1):
        slope = (data[i, 1] - data[i - 1, 1]) / (data[i, 0] - data[i - 1, 0]) \
            if (data[i, 0] - data[i - 1, 0]) != 0 else 0
        slopes.append(slope) if i == 1 else None
        if (abs(slope - slopes[i - 1]) <= slope_threshold) or i < 4:  # 2*len(data)/5:
            if i == 1:
                filtered_data.append(data[i - 1])
            filtered_data.append(data[i])
            slopes.append(slope)
        else:
            break
    if not filtered_data:
        return None, None, None, None

    # filtered data for tendline
    filtered_data = np.array(filtered_data)
    x, y = filtered_data[:, 0], filtered_data[:, 1]
    x_mean, y_mean = x.mean(), y.mean()
    x_err, y_err = x - x_mean, y - y_mean
    a = (x_err * y_err).sum() / (x_err ** 2).sum()
    b = y_mean - a * x_mean
    error = np.sum((y - (a * x + b)) ** 2) / len(filtered_data)

    return np.array([[x[0], a * x[0] + b], [x[-1], a * x[-1] + b]]), a, b, error


def trend_line_ml(data):
    X = data[:, 0].reshape(-1, 1)
    y = data[:, 1]

    ransac = linear_model.RANSACRegressor(max_trials=30, min_samples=1000, residual_threshold=1.24, random_state=42)
    huber = linear_model.HuberRegressor(max_iter=1000, alpha=0.1, epsilon=4)

    model = huber
    model.fit(X, y)
    # inlier_mask = model.inlier_mask_
    # outlier_mask = np.logical_not(inlier_mask)
    outlier_mask = model.outliers_
    line_y_ransac = model.predict(X)
    coef = model.coef_[0]

    # coef = model.estimator_.coef_[0]
    # intercept = ransac.intercept_

    return line_y_ransac, coef, outlier_mask

# def trend_line_ml(data):
#     X = data[:, 0].reshape(-1, 1)
#     y = data[:, 1]
#
#     kernel_reg = KernelReg(endog=y, exog=X, var_type='c', reg_type='lc', bw='cv_ls')
#
#     line_y_kernel, _ = kernel_reg.fit()
#
#     return line_y_kernel


def visualize_rent(rent_path, output_filename='Rents_rule_real.svg', output_figures_folder="."):
    if not rent_path.endswith('.rent'):
        raise ValueError(f"Expected a .rent file, got {rent_path} instead.")
    with open(rent_path, "rb") as fp:  # Unpickling
        rent_data = pickle.load(fp)

    # Flatten data
    rent_data_flat = np.array([point for level in rent_data for point in level])
    blocks, pins = rent_data_flat[:, 0], rent_data_flat[:, 1]
    rent_data_flat = rent_data_flat[:,0:2]

    # ml for trend line
    # y_pred_log, coef, inlier_mask, outlier_mask = trend_line_ml(np.log2(rent_data_flat))
    y_pred_log, coef, outlier_mask = trend_line_ml(np.log2(rent_data_flat.astype(float)))
    # Bin data
    n_bins = len(rent_data)
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

    # Trend line
    log_bin_means = np.log2(bin_means)
    line, slope, _, _ = trend_line(log_bin_means)
    # y_pred_log, coef = trend_line_ml(log_bin_means)
    print(f"Current net's rent's exponent is {slope}")
    plt.figure(figsize=(8, 6))

    ## Viz linear regression results
    # plt.scatter(blocks[inlier_mask], pins[inlier_mask], color="blue", marker=".", label="Inliers")
    # plt.plot((rent_data_flat[:, 0]), np.exp2(y_pred_log), color='red', label=f'Trend Line ML')
    # plt.scatter(blocks[outlier_mask], pins[outlier_mask], color="gold", marker=".", label="Outliers")
    # plt.plot((rent_data_flat[:, 0]), np.exp2(y_pred_log), color='red', label=f'Trend Line ML (Slope: {coef:.2f})')


    plt.scatter(blocks, pins, alpha=0.1, label='Data Points')
    plt.scatter(bin_means[:, 0], bin_means[:, 1], s=100, color='red', alpha=0.85, edgecolors='w', linewidths=2,
                marker='o', label='Bin Means')
    plt.xscale("log", base=2)
    plt.yscale("log", base=2)
    plt.xlabel('$B$ (Blocks)', size=15)
    plt.ylabel('$T$ (Terminals)', size=15)
    plt.plot(np.exp2(line[:, 0]), np.exp2(line[:, 1]), color='black', linewidth=2, linestyle='--',
             label=f'Slope (r) = {slope:.2f}')
    plt.title('Rent\'s Rule Visualization', fontsize=15)
    plt.legend(fontsize=15)

    # Plotting
    # plt.figure(figsize=(10, 6))
    # plt.scatter(blocks, pins, alpha=0.1)
    # plt.scatter(bin_means[:, 0], bin_means[:, 1], s=100, color='red')
    # plt.xscale("log", base=2)
    # plt.yscale("log", base=2)
    # plt.xlabel('$B$', size=15)
    # plt.ylabel('$T$', size=15)
    # plt.plot(np.exp2(line[:, 0]), np.exp2(line[:, 1]), color='black', linewidth=2)
    # plt.text(np.exp2(line[0, 0]), np.exp2(line[0, 1]), f'Slope (r) = {slope:.2f}', size=15)
    os.makedirs(output_figures_folder, exist_ok=True)
    plt.savefig(os.path.join(output_figures_folder, output_filename), transparent=True)


# if __name__ == '__main__':
#     # folder = "../rent_sweep/sweep"  # Adjust directory
#     #
#     if len(sys.argv) != 2:
#         print("Usage: python3 rent2viz.py <rent_path>")
#         sys.exit(1)
#     rent_path = sys.argv[1]
#     filenames = [f for f in os.listdir(rent_path) if f.endswith('.rent')]
#     for filename in filenames:
#         rent_file_path = os.path.join(rent_path, filename)
#         output_filename = os.path.join(rent_path, f"{filename}_visualized.png")
#         visualize_rent(rent_file_path, output_filename)
#         print(f"Visualization saved to {output_filename}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 rent2viz.py <rent_file_path>  <output_figures_folder>")
        sys.exit(1)

    rent_file_path = sys.argv[1]
    output_figures_folder = sys.argv[2]
    output_filename = os.path.basename(rent_file_path) + "_viz.svg"

    visualize_rent(rent_file_path, output_filename, output_figures_folder)
    print(f"Visualization saved to {output_filename}")
