#!/usr/bin python3

import ray
import os.path
import argparse

from utils import *
from pathlib import Path
from models.classification import ClassificationMethods

__author__ = "Nicolas de Montigny"

__all__ = ['bacteria_classification_train_cv']

# Initialisation / validation of parameters from CLI
################################################################################
def bacteria_classification(opt):
    # Verify existence of files and load data
    data_bacteria = verify_load_data(opt['data_bacteria'])
    data_metagenome = verify_load_data(opt['data_metagenome'])
    k_length = len(data_bacteria['kmers'][0])

    # Verify that model type is valid / choose default depending on host presence
    if opt['model_type'] is None:
        opt['model_type'] = 'cnn'

    # Validate training parameters
    verify_positive_int(opt['batch_size'], 'batch_size')
    verify_positive_int(opt['training_epochs'], 'number of iterations in neural networks training')
    
    outdirs = define_create_outdirs(opt['outdir'])

    # Validate and extract list of taxas
    list_taxas = verify_taxas(opt['taxa'], data_bacteria['taxas'])

    # Initialize cluster
    ray.init()

# Definition of model for bacteria taxonomic classification + training
################################################################################
    clf = ClassificationMethods(
        database_k_mers = data_bacteria,
        k = k_length,
        outdirs = outdirs,
        database = opt['database_name'],
        classifier_multiclass = opt['model_type'],
        taxa = list_taxas,
        batch_size = opt['batch_size'],
        training_epochs = opt['training_epochs'],
        verbose = opt['verbose'],
        cv = False
    )
    clf.execute_training()

# Execution of bacteria taxonomic classification on metagenome + save results
################################################################################
    def populate_save_data(clf, end_taxa):
        clf_data = {'sequence' : clf.classified_data['sequence'].copy()}
        if end_taxa is not None:
            clf_data['sequence'] = clf_data['sequence'][:clf_data['sequence'].index(end_taxa)]
        
        if 'domain' in clf_data['sequence'] and len(data_metagenome['classified_ids']) > 0:
            clf_data['domain'] = {
                'profile' : data_metagenome['profile'],
                'kmers' : data_metagenome['kmers'],
                'ids' : data_metagenome['ids'],
                'classification' : data_metagenome['classification'],
                'classified_ids' : data_metagenome['classified_ids'],
                'unknown_profile' : data_metagenome['unknown_profile'],
                'unknown_ids' : data_metagenome['unknown_ids']
            }
        if 'host' in clf_data.keys():
            clf_data['domain']['host_classification'] = data_metagenome['host_classification']
            clf_data['domain']['host_ids'] = data_metagenome['host_ids']

        for taxa in clf_data['sequence']:
            clf_data[taxa] = {
                'profile' : clf.classified_data[taxa]['unknown'],
                'kmers' : data_metagenome['kmers'],
                'ids' : clf.classified_data[taxa]['unknown_ids'],
                'classification' : clf.classified_data[taxa]['classification'],
                'classified_ids' : clf.classified_data[taxa]['classified_ids'],
            }

        clf_file = os.path.join(outdirs['results_dir'], opt['metagenome_name'] + '_classified.npz')
        save_Xy_data(clf_data, clf_file)

    end_taxa = clf.execute_classification(data_metagenome)
    populate_save_data(clf, end_taxa)
    if end_taxa is None:
        print("Caribou finished training the {} model and classifying bacterial sequences at {} taxonomic level with it".format(opt['model_type'], opt['taxa']))
    else:
        print("Caribou finished training the {} model and classifying bacterial sequences at {} taxonomic level until {} because there were no more sequences to classify".format(opt['model_type'], opt['taxa'], end_taxa))

# Argument parsing from CLI
################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script trains a model and classifies bacteria sequences iteratively over known taxonomic levels.')
    parser.add_argument('-db','--data_bacteria', required=True, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the bacteria database')
    parser.add_argument('-mg','--data_metagenome', required=True, type=Path, help='PATH to a npz file containing the data corresponding to the k-mers profile for the metagenome to classify')
    parser.add_argument('-dt','--database_name', required=True, help='Name of the bacteria database used to name files')
    parser.add_argument('-mn','--metagenome_name', required=True, help='Name of the metagenome to classify used to name files')
    parser.add_argument('-model','--model_type', default='lstm_attention', choices=['sgd','mnb','lstm_attention','cnn','widecnn'], help='The type of model to train')
    parser.add_argument('-t','--taxa', default='species', help='The taxonomic level to use for the classification, defaults to species. Can be one level or a list of levels separated by commas.')
    parser.add_argument('-bs','--batch_size', default=32, type=int, help='Size of the batch size to use, defaults to 32')
    parser.add_argument('-e','--training_epochs', default=100, type=int, help='The number of training iterations for the neural networks models if one ise chosen, defaults to 100')
    parser.add_argument('-v','--verbose', action='store_true', help='Should the program be verbose')
    parser.add_argument('-o','--outdir', required=True, type=Path, help='PATH to a directory on file where outputs will be saved')
    parser.add_argument('-wd','--workdir', default=None, type=Path, help='Optional. Path to a working directory where Ray Tune will output and spill tuning data')
    args = parser.parse_args()

    opt = vars(args)

    bacteria_classification(opt)
