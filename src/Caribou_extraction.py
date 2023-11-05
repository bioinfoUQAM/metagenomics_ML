#!/usr/bin python3

import argparse

from utils import *
from time import time
from pathlib import Path
from models.classification_old import ClassificationMethods

__author__ = "Nicolas de Montigny"

__all__ = ['bacteria_extraction_train_cv']

# Initialisation / validation of parameters from CLI
################################################################################
def bacteria_extraction(opt):

    # Verify that model type is valid / choose default depending on host presence
    if opt['host_name'] is None:
        opt['model_type'] = 'onesvm'
    elif opt['model_type'] is None and opt['host_name'] is not None:
        opt['model_type'] = 'attention'

    # Validate training parameters
    verify_positive_int(opt['batch_size'], 'batch_size')
    verify_positive_int(opt['training_epochs'], 'number of iterations in neural networks training')
    
    outdirs = define_create_outdirs(opt['outdir'])
    
    # Initialize cluster
    init_ray_cluster(opt['workdir'])
    
# Data loading
################################################################################

    if opt['data_host'] is not None:
        db_data, db_ds = verify_load_host_merge(opt['data_bacteria'], opt['data_host'])
    else:
        db_data, db_ds = verify_load_db(opt['data_bacteria'])
    data_metagenome = verify_load_data(opt['data_metagenome'])

    k_length = len(db_data['kmers'][0])

    val_ds = split_sim_dataset(db_ds, db_data, 'validation')

# Definition of model for bacteria extraction / host removal + execution
################################################################################
    if opt['host_name'] is None:
        clf = ClassificationMethods(
            database_k_mers = (db_data, db_ds),
            k = k_length,
            outdirs = outdirs,
            database = opt['database_name'],
            classifier_binary = opt['model_type'],
            taxa = 'domain',
            batch_size = opt['batch_size'],
            training_epochs = opt['training_epochs'],
            verbose = opt['verbose'],
            cv = False
        )
    else:
        clf = ClassificationMethods(
            database_k_mers = (db_data, db_ds),
            k = k_length,
            outdirs = outdirs,
            database = opt['database_name'],
            classifier_binary = opt['model_type'],
            taxa = 'domain',
            batch_size = opt['batch_size'],
            training_epochs = opt['training_epochs'],
            verbose = opt['verbose'],
            cv = False
        )
# Execution of bacteria extraction / host removal on metagenome + save results
################################################################################
    
    t_start = time()
    end_taxa = clf.execute_training_prediction(data_metagenome)
    t_end = time()
    t_classify = t_end - t_start

    if end_taxa is None:
        clf_data = merge_save_data(
            clf.classified_data,
            data_bacteria,
            end_taxa,
            outdirs['results_dir'],
            opt['metagenome_name'],
        )
        print(f"Caribou finished training the {opt['model_type']} model and extracting bacteria with it. \
            \nThe training and classification steps took {t_classify} seconds.")
    else:
        print(f"Caribou finished training the {opt['model_type']} model but there was no data to classify. \
            \nThe training and classification steps took {t_classify} seconds.")

# Argument parsing from CLI
################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script trains a model and extracts bacteria / host sequences.')
    parser.add_argument('-db','--data_bacteria', required=True, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the bacteria database')
    parser.add_argument('-dh','--data_host', default=None, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the host')
    parser.add_argument('-mg','--data_metagenome', required=True, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the metagenome to classify')
    parser.add_argument('-dt','--database_name', required=True, help='Name of the bacteria database used to name files')
    parser.add_argument('-ds','--host_name', default=None, help='Name of the host database used to name files')
    parser.add_argument('-mn','--metagenome_name', required=True, help='Name of the metagenome to classify used to name files')
    parser.add_argument('-model','--model_type', default=None, choices=[None,'onesvm','linearsvm','attention','lstm','deeplstm'], help='The type of model to train')
    parser.add_argument('-bs','--batch_size', default=32, type=int, help='Size of the batch size to use, defaults to 32')
    parser.add_argument('-e','--training_epochs', default=100, type=int, help='The number of training iterations for the neural networks models if one ise chosen, defaults to 100')
    parser.add_argument('-v','--verbose', action='store_true', help='Should the program be verbose')
    parser.add_argument('-o','--outdir', required=True, type=Path, help='PATH to a directory on file where outputs will be saved')
    parser.add_argument('-wd','--workdir', default='/tmp/spill', type=Path, help='Optional. Path to a working directory where Ray Tune will output and spill tuning data')
    args = parser.parse_args()

    opt = vars(args)

    bacteria_extraction(opt)