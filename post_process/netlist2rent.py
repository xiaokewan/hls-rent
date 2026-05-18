#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 3/20/24 
# @Author  : Marieke Louage, Xiaoke Wang
# @Group   : UGent HES
# @File    : netlist2rent.py.py
# @Software: PyCharm, Ghent

import xml.etree.ElementTree as ET
import os
import numpy as np
import subprocess
import pickle
import sys
import csv
from ipyfilechooser import FileChooser
import glob


class Hypergraph:
    def __init__(self, hypergraph, external_edges, folder, name='hg', suffix=''):
        # Extract hypergraph nodename = list index + 1 (starts from 1), list of edgenames per node
        self.hypergraph = np.array(hypergraph, dtype=object)

        # Input and output edges are external edges
        self.external_edges = np.array(external_edges)

        # Exclude external edges that are not connected to a node in the hypergraph
        external_edges_mask = np.zeros(len(self.external_edges))
        for edges in hypergraph:
            for edge in edges:
                indices = np.argwhere(self.external_edges == edge)
                if indices.size > 0:
                    index = np.argwhere(self.external_edges == edge)[0]
                    external_edges_mask[index] = 1

        self.external_edges = self.external_edges[external_edges_mask == 1]

        self.n_vertices = len(self.hypergraph)  ## Blocks
        self.n_pins = len(self.external_edges)  ## Pins

        self.folder = folder
        self.name_base = name
        self.suffix = suffix

    def print_hmetis_hypergraph(self):
        # Hmetis expects flipped graph (edge -> nodes) instead of (node -> edges)
        edge_nodes = {}
        for i, edges in enumerate(self.hypergraph):
            node = str(i + 1)
            for edge in edges:
                if edge in edge_nodes:
                    edge_nodes[edge].append(node)
                else:
                    edge_nodes[edge] = [node]
        self.n_hyperedges = len(edge_nodes)
        self.n_vertices = len(self.hypergraph)
        # Print file
        hmetis_lines = []
        hmetis_lines.append(' '.join([str(self.n_hyperedges), str(self.n_vertices)]))
        for nodes in edge_nodes.values():
            hmetis_lines.append(' '.join(nodes))
        file1 = open(self.get_path_graphfile(), 'w')
        lines = file1.writelines([entry + '\n' for entry in hmetis_lines])
        file1.close()

    def run_hmetis(self, hmetis_path):
        output = subprocess.run([hmetis_path, self.get_path_graphfile(), '2', '5', '10', '1', '1', '2', '1', '0'],
                                capture_output=True)

    def split(self, hmetis_path):
        # make input file for hmetis
        self.print_hmetis_hypergraph()
        # run hmetis
        self.run_hmetis(hmetis_path)
        # process output file (name inputfile + '.part.2') --> format read hmetis docs
        path_splitfile = self.get_path_graphfile() + '.part.2'
        file1 = open(path_splitfile, 'r')
        lines = file1.readlines()
        file1.close()

        # split hypergraph nodes
        mask = np.array(list(map(int, lines)))  # partition1: 0, partition2: 1
        hypergraph0 = self.hypergraph[mask == 0]
        hypergraph1 = self.hypergraph[mask == 1]

        # add cut edges to external edges
        cut_edges = np.array(list(set(np.concatenate(hypergraph0)) & set(np.concatenate(hypergraph1))))
        self.external_edges = np.unique(np.append(self.external_edges, cut_edges))

        hg0 = Hypergraph(self.hypergraph[mask == 0], self.external_edges, self.folder, self.name_base, '0')
        hg1 = Hypergraph(self.hypergraph[mask == 1], self.external_edges, self.folder, self.name_base, '1')

        return hg0, hg1

    def get_path_graphfile(self):
        return os.path.join(self.folder, self.name_base + self.suffix)


class subckt:
    def __init__(self, name, inputs, outputs):
        self.inputs = inputs
        self.outputs = outputs
        self.name = name


def get_hypergraph_from_blif(path_blif, path_graphfiles_folder):
    # Read blif file
    f = open(path_blif, 'r')
    lines = f.readlines()
    f.close()

    # Seperate models: blif describes main model and optionally subcircuit models
    models = []
    index1 = 0
    for index2, line in enumerate(lines):
        if '.model' in line:
            models.append(lines[index1:index2])
            index1 = index2
    models.append(lines[index1:])
    main_model = models[1]
    subckt_models = models[2:]  # Templates for subckts in main model -> doesn't influence Rents exponent -> ignore

    # Reformat: collect .subckts, .inputs, .outputs, .names, .latch by eliminating concatenate characters
    new_main_model = []
    new_line_split = []
    for line in main_model:
        line_split = line.split()
        if line_split != [] and (line_split[-1] == '\\'):  # Concatenate character: \
            new_line_split.extend(line_split[:-1])
        else:
            new_line_split.extend(line_split)
            new_main_model.append(new_line_split)
            new_line_split = []

    # collect .inputs, .outputs, .names, .latch, .subckt
    inputs = None
    outputs = None
    names = []  # truth table not included and not relevant. Truth table is on a different line
    latches = []
    subckts = []

    for split_line in new_main_model:
        if split_line == []:
            pass
        elif split_line[0] == '.inputs':
            inputs = split_line
        elif split_line[0] == '.outputs':
            outputs = split_line
        elif split_line[0] == '.names':
            names.append(split_line)
        elif split_line[0] == '.latch':
            latches.append(split_line)
        elif split_line[0] == '.subckt':
            subckts.append(split_line)

    hypergraph_internal = []

    # subckt; first: '.subckt', second: 'name', then 'IO_name=netname'
    for subckt in subckts:
        edges = []
        for io_net in subckt[2:]:
            net = io_net.split('=')[1]
            edges.append(net)
        hypergraph_internal.append(edges)

    # name; first: '.name', then netnames
    for name in names:
        hypergraph_internal.append(name[1:])

    # latch; first: '.latch', then net names        e.g. ".latch n809 n810 re pclk 2"
    for latch in latches:
        hypergraph_internal.append(latch[1:3])

    # Input and output edges are external edges
    external_edges = []
    external_edges.extend(inputs)
    external_edges.extend(outputs)
    hypergraph = Hypergraph(hypergraph_internal, external_edges, path_graphfiles_folder)
    return hypergraph


def bipartition(hg, rent_data, hmetis_path, partition_level=0):
    blocks = hg.n_vertices
    pins = hg.n_pins
    if len(rent_data) >= partition_level + 1:
        rent_data[partition_level].append([blocks, pins])
    else:
        rent_data.append([[blocks, pins]])
    if blocks > 2:
        hg0, hg1 = hg.split(hmetis_path)
        del hg
        bipartition(hg0, rent_data, hmetis_path, partition_level + 1)
        bipartition(hg1, rent_data, hmetis_path, partition_level + 1)


def process_blif_file(blif_file, output_folder, hmetis_path, graphfiles_folder='graphfiles'):
    if not os.path.isdir(graphfiles_folder):
        os.makedirs(graphfiles_folder, exist_ok=True) 

    hypergraph = get_hypergraph_from_blif(blif_file, graphfiles_folder)
    rent_data = []
    bipartition(hypergraph, rent_data, hmetis_path)
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, os.path.basename(blif_file) + '.rent')
    output_path_csv = os.path.join(output_folder, os.path.basename(blif_file) + '.csv')
    print("Output Path:", {output_path})
    with open(output_path, "wb") as fp:
        pickle.dump(rent_data, fp)

    with open(output_path_csv, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        for sublist in rent_data:
            writer.writerow(sublist)

# if __name__ == '__main__':
#     arguments = sys.argv[1:]
#     if len(arguments) > 3 or len(arguments) < 2:
#         print("Usage: python3 netlist2rent.py <blif_file_path> <output_folder> <hmetis_path> \n"
#               "or python3 netlist2rent.py <blif_file_path> <hmetis_path> with default output folder")
#         sys.exit(1)
#
#     blif_folder_path = arguments[0]
#     output_folder = os.path.dirname(blif_folder_path) if len(arguments) == 2 else arguments[1]
#     hmetis_path = arguments[1] if len(arguments) == 2 else arguments[2]
#
#     # blif_file_folder = "../rent_sweep/sweep"
#     # hmetis_path = “../hmetis-1.5-linux”
#     filenames = [f for f in os.listdir(blif_folder_path) if f.endswith('.blif')]
#     for filename in filenames:
#         blif_file_path = os.path.join(blif_folder_path, filename)
#         process_blif_file(blif_file_path, output_folder=output_folder, hmetis_path=hmetis_path)
#

if __name__ == '__main__':
    arguments = sys.argv[1:]
    if len(arguments) < 2 or len(arguments) > 3:
        print("Usage: python3 netlist2rent.py <blif_file_path> [<output_folder>] <hmetis_path>")
        sys.exit(1)

    blif_file_path = arguments[0]
    hmetis_path = arguments[-1]  # Always the last argument
    
    # If only two arguments are provided, use the directory of the BLIF file as the output directory
    output_folder = arguments[1] if len(arguments) == 3 else os.path.dirname(blif_file_path)
    # print(f"Output path: {output_folder},\n Blif path: {blif_file_path},\n hmetis path: {hmetis_path}")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    process_blif_file(blif_file_path, output_folder, hmetis_path)
