#!/usr/bin python3

import ray
import pathlib
import os.path
import argparse

from utils import *
from data.build_data import build_load_save_data

__author__ = "Nicolas de Montigny"

__all__ = ['kmers_dataset']

"""
This script extracts K-mers of the given dataset using the available ressources on the computer before saving it to drive.
"""

# Initialisation / validation of parameters from CLI
################################################################################
def kmers_dataset(opt):
    kmers_list = None

    # Verify there are files to analyse
    verify_seqfiles(opt['seq_file'], opt['seq_file_host'])

    # Verification of existence of files
    for file in [opt['seq_file'],opt['cls_file'],opt['seq_file_host'],opt['cls_file_host'],opt['kmers_list']]:
        verify_file(file)

    # Verification of k length
    opt['k_length'], kmers_list = verify_kmers_list_length(opt['k_length'], opt['kmers_list'])

    # Verify path for saving
    outdirs = define_create_outdirs(opt['outdir'])
    
    # Initialize cluster
    ray.init()

# K-mers profile extraction
################################################################################

    if kmers_list is None:
        # Reference Database Only
        if opt['seq_file'] is not None and opt['cls_file'] is not None and opt['seq_file_host'] is None and opt['cls_file_host'] is None:
            k_profile_database = build_load_save_data((opt['seq_file'],opt['cls_file']),
                None,
                outdirs["data_dir"],
                opt['dataset_name'],
                opt['host_name'],
                k = opt['k_length'],
                kmers_list = None
            )

            # Save kmers list to file for further extractions
            kmers_list = k_profile_database['kmers']
            with open(os.path.join(outdirs["data_dir"],'kmers_list.txt'),'w') as handle:
                handle.writelines("%s\n" % item for item in kmers_list)

            print("Caribou finished extracting k-mers of {}".format(opt['dataset_name']))

        # Reference database and host
        elif opt['seq_file'] is not None and opt['cls_file'] is not None and opt['seq_file_host'] is not None and opt['cls_file_host'] is not None:

            k_profile_database, k_profile_host  = build_load_save_data((opt['seq_file'],opt['cls_file']),
                (opt['seq_file_host'],opt['cls_file_host']),
                outdirs["data_dir"],
                opt['dataset_name'],
                opt['host_name'],
                k = opt['k_length'],
                kmers_list = None
            )

            # Save kmers list to file for further extractions
            kmers_list = k_profile_database['kmers']
            with open(os.path.join(outdirs["data_dir"],'kmers_list.txt'),'w') as handle:
                handle.writelines("%s\n" % item for item in kmers_list)

            print("Caribou finished extracting k-mers of {} and {}".format(opt['dataset_name'],opt['host_name']))
    else:
        # Reference Host only
        if opt['seq_file'] is not None and opt['cls_file'] is not None:

            k_profile_host = build_load_save_data(None,
            (opt['seq_file'],opt['cls_file']),
            outdirs["data_dir"],
            None,
            opt['host_name'],
            k = opt['k_length'],
            kmers_list = kmers_list
            )
            print("Caribou finished extracting k-mers of {}".format(opt['host_name']))

        # Dataset to analyse only
        elif opt['seq_file'] is not None and opt['cls_file'] is None:

            k_profile_metagenome = build_load_save_data(opt['seq_file'],
            None,
            outdirs["data_dir"],
            opt['dataset_name'],
            None,
            k = opt['k_length'],
            kmers_list = kmers_list
            )
            print("Caribou finished extracting k-mers of {}".format(opt['dataset_name']))

        else:
            raise ValueError(
                "Caribou cannot extract k-mers because there are missing parameters !\n" +
                "Please refer to the wiki for further details : https://github.com/bioinfoUQAM/Caribou/wiki")

# Argument parsing from CLI
################################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script extracts K-mers of the given dataset using the available ressources on the computer before saving it to drive.')
    parser.add_argument('-s','--seq_file', default=None, type=pathlib.Path, help='PATH to a fasta file containing bacterial genomes to build k-mers from')
    parser.add_argument('-c','--cls_file', default=None, type=pathlib.Path, help='PATH to a csv file containing classes of the corresponding fasta')
    parser.add_argument('-dt','--dataset_name', default='dataset', help='Name of the dataset used to name files')

    parser.add_argument('-sh','--seq_file_host', default=None, type=pathlib.Path, help='PATH to a fasta file containing host genomes to build k-mers from')
    parser.add_argument('-ch','--cls_file_host', default=None, type=pathlib.Path, help='PATH to a csv file containing classes of the corresponding host fasta')
    parser.add_argument('-dh','--host_name', default='host', help='Name of the host used to name files')

    parser.add_argument('-k','--k_length', required=True, type=int, help='Length of k-mers to extract')
    parser.add_argument('-l','--kmers_list', default=None, type=pathlib.Path, help='PATH to a file containing a list of k-mers to be extracted if the dataset is not a training database')
    parser.add_argument('-o','--outdir', required=True, type=pathlib.Path, help='PATH to a directory on file where outputs will be saved')
    args = parser.parse_args()

    opt = vars(args)

    kmers_dataset(opt)
