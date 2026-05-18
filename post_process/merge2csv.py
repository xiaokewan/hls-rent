#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 4/9/24 
# @Author  : Xiaoke Wang
# @Group   : UGent HES
# @File    : merge2csv.py
# @Software: PyCharm, Ghent

import csv
import os


def merge_to_csv(csv_file_path, *args):
    # Determine the number of rows (length of the first array)
    num_rows = len(args[0])

    # Ensure that the directory containing the CSV file exists
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    # Open the CSV file for writing
    with open(csv_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write data from each variable to the CSV file column-wise
        for i in range(num_rows):
            row = [arg[i] for arg in args]
            writer.writerow(row)

# csv_file_path = 'data.csv'
# merge_to_csv(csv_file_path, list1, list2, list3)