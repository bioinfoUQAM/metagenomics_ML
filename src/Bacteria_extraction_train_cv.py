#!/usr/bin python3

from models.extraction import ClassificationMethods

from tensorflow.compat.v1 import logging

import os
import ray
import argparse

from pathlib import Path
from utils import load_Xy_data

__author__ = "Nicolas de Montigny"

__all__ = ['bacteria_extraction_train_cv']

# Suppress Tensorflow warnings
################################################################################
logging.set_verbosity(logging.ERROR)

# Initialisation / validation of parameters from CLI
################################################################################
def bacteria_extraction_train_cv(opt):
    ray.init()
    # Verify existence of files and load data
    if not os.path.isfile(opt['data_bacteria']):
        raise ValueError("Cannot find file {} ! Exiting".format(opt['data_bacteria']))
    else:
        data_bacteria = load_Xy_data(opt['data_bacteria'])
        # Infer k-mers length from the extracted bacteria profile
        k_length = len(data_bacteria['kmers'][0])
        # Verify that kmers profile file exists
        if not os.path.isdir(data_bacteria['profile']):
            raise ValueError("Cannot find data folder {} ! Exiting".format(data_bacteria['profile']))

    # Verify existence of files for host data + concordance and load
    if opt['data_host'] is not None:
        if not os.path.isfile(opt['data_host']):
            raise ValueError("Cannot find file {} ! Exiting".format(opt['data_host']))
        else:
            data_host = load_Xy_data(opt['data_host'])
            # Verify concordance of k length between datasets
            if k_length != len(data_host['kmers'][0]):
                raise ValueError("K length between datasets is inconsistent ! Exiting\n" +
                "K length of bacteria dataset is {} while K length from host is {}").format(k_length, len(data_host['kmers'][0]))
            else:
                # Verify that kmers profile file exists
                if not os.path.isdir(data_host['profile']):
                    raise ValueError("Cannot find data folder {} ! Exiting".format(data_host['profile']))

    # Verify that model type is valid / choose default depending on host presence
    if opt['host_name'] is None:
        opt['model_type'] = 'onesvm'
    elif opt['model_type'] is None and opt['host_name'] is not None:
        opt['model_type'] = 'attention'

    # Validate batch size
    if opt['batch_size'] <= 0:
        raise ValueError("Invalid batch size ! Exiting")

    # Validate number of epochs
    if opt['training_epochs'] <= 0:
        raise ValueError("Invalid number of training iterations for neural networks")

    # Validate path for saving
    outdir_path, outdir_folder = os.path.split(opt['outdir'])
    if not os.path.isdir(opt['outdir']) and os.path.exists(outdir_path):
        print("Created output folder")
        os.makedirs(opt['outdir'])
    elif not os.path.exists(outdir_path):
        raise ValueError("Cannot find where to create output folder ! Exiting")

    # Folders creation for output
    outdirs = {}
    outdirs["main_outdir"] = opt['outdir']
    outdirs["data_dir"] = os.path.join(outdirs["main_outdir"], "data/")
    outdirs["models_dir"] = os.path.join(outdirs["main_outdir"], "models/")
    outdirs["results_dir"] = os.path.join(outdirs["main_outdir"], "results/")
    os.makedirs(outdirs["main_outdir"], mode=0o700, exist_ok=True)
    os.makedirs(outdirs["models_dir"], mode=0o700, exist_ok=True)
    os.makedirs(outdirs["results_dir"], mode=0o700, exist_ok=True)

# Training and cross-validation of models for bacteria extraction / host removal
################################################################################

    if opt['host_name'] is None:
        ClassificationMethods(
            database_k_mers = data_bacteria,
            k = k_length,
            outdirs = outdirs,
            database = opt['database_name'],
            classifier_binary = opt['model_type'],
            taxa = 'domain',
            batch_size = opt['batch_size'],
            training_epochs = opt['training_epochs'],
            verbose = opt['verbose'],
            cv = True
        ).execute_training()
    else:
        ClassificationMethods(
            database_k_mers=data_bacteria,
            k = k_length,
            outdirs = outdirs,
            database = opt['database_name'],
            classifier_binary = opt['model_type'],
            taxa = 'domain',
            batch_size = opt['batch_size'],
            training_epochs = opt['training_epochs'],
            verbose = opt['verbose'],
            cv = True
        )

    print("Caribou finished training and cross-validating the {} model without faults".format(opt['model_type']))


# Argument parsing from CLI
################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script trains and cross-validates a model for the bacteria extraction / host removal step.')
    parser.add_argument('-db','--data_bacteria', required=True, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the bacteria database')
    parser.add_argument('-dh','--data_host', default=None, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the host')
    parser.add_argument('-dt','--database_name', required=True, help='Name of the bacteria database used to name files')
    parser.add_argument('-ds','--host_name', default=None, help='Name of the host database used to name files')
    parser.add_argument('-model','--model_type', default=None, choices=[None,'onesvm','linearsvm','attention','lstm','deeplstm'], help='The type of model to train')
    parser.add_argument('-bs','--batch_size', default=32, type=int, help='Size of the batch size to use, defaults to 32')
    parser.add_argument('-e','--training_epochs', default=100, type=int, help='The number of training iterations for the neural networks models if one ise chosen, defaults to 100')
    parser.add_argument('-v','--verbose', action='store_true', help='Should the program be verbose')
    parser.add_argument('-o','--outdir', required=True, type=Path, help='PATH to a directory on file where outputs will be saved')
    parser.add_argument('-wd','--workdir', default='~/ray_results', type=Path, help='Optional. Path to a working directory where Ray Tune will output and spill tuning data')
    args = parser.parse_args()

    opt = vars(args)

    bacteria_extraction_train_cv(opt)
