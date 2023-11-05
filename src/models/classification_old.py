import os
import ray
import cloudpickle

import numpy as np
import pandas as pd

from glob import glob
from shutil import rmtree
from utils import load_Xy_data
from models.sklearn.models import SklearnModel
from models.kerasTF.models import KerasTFModel

# Simulation class
from models.reads_simulation import readsSimulation

__author__ = 'Nicolas de Montigny'

__all__ = ['ClassificationMethods']

class ClassificationMethods():
    """
    Utilities class for classifying sequences from metagenomes using ray

    ----------
    Attributes
    ----------
    
    classified_data : dictionary
        Dictionary containing the classified data for each classified taxonomic level

    models : dictionary
        Dictionary containing the trained models for each taxonomic level

    ----------
    Methods
    ----------

    execute_training : launch the training of the models for the chosen taxonomic levels
        no parameters to pass

    execute_classification : 
        data2classify : a dictionnary containing the data to classify produced by the function Caribou.src.data.build_data.build_X_data

    """
    def __init__(
        self,
        database_k_mers,
        k,
        outdirs,
        database,
        classifier_binary = 'deeplstm',
        classifier_multiclass = 'widecnn',
        taxa = None,
        threshold = 0.8,
        batch_size = 32,
        training_epochs = 100,
        verbose = True,
        cv = False
    ):
        # Parameters
        self._k = k
        self._cv = cv
        self._taxas = taxa
        self._outdirs = outdirs
        self._database = database
        self._verbose = verbose
        self._threshold = threshold
        self._classifier_binary = classifier_binary
        self._classifier_multiclass = classifier_multiclass
        self._batch_size = batch_size
        self._training_epochs = training_epochs
        # Initialize with values
        self.classified_data = {
            'sequence': [],
            'classification' : None,
            'classified_ids' : [],
            'unknown_ids' : []
        }
        # Empty initializations
        self.models = {}
        self._host = False
        self._taxas_order = []
        self._host_data = None
        self._database_data = None
        self._training_datasets = None
        self._merged_training_datasets = None
        self._merged_database_host = None
        self.previous_taxa_unclassified = None
        # Extract database data 
        if isinstance(database_k_mers, tuple):
            self._host = True
            self._database_data = database_k_mers[0]
            self._host_data = database_k_mers[1]
        else:
            self._database_data = database_k_mers
        # Remove 'id' from kmers if present
        if 'id' in self._database_data['kmers']:
            self._database_data['kmers'].remove('id')
        if self._host and 'id' in self._host_data['kmers']:
            self._host_data['kmers'].remove('id')
        # Assign taxas order for top-down strategy
        self._taxas_order = self._database_data['taxas'].copy()
        self._taxas_order.reverse()
        # Automatic executions
        self._verify_assign_taxas(taxa)
        
    # Main functions
    #########################################################################################################

    # Wrapper function for training and predicting over each known taxa
    def execute_training_prediction(self, data2classify):
        print('execute_training_prediction')
        files_lst = glob(os.path.join(data2classify['profile'],'*.parquet'))
        df2classify = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
        # df2classify = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
        ids2classify = data2classify['ids']
        for i, taxa in enumerate(self._taxas_order):
            if taxa in self._taxas:
                # Training
                if taxa in ['domain','bacteria','host']:
                    clf = self._classifier_binary
                else:
                    clf = self._classifier_multiclass
                self._data_file = os.path.join(self._outdirs['data_dir'], f'Xy_{taxa}_database_K{self._k}_{clf}_{self._database}_data.npz')
                self._model_file = os.path.join(self._outdirs['models_dir'], f'{clf}_{taxa}.pkl')
                train = self._verify_load_data_model(self._data_file, self._model_file, taxa)
                if train:
                    self._train_model(taxa)
                # Predicting
                try:
                    if i == 0:
                        df2classify = self._classify_first(df2classify, taxa, ids2classify, data2classify['profile'])
                    else:
                        df2classify = self._classify_subsequent(df2classify, taxa, ids2classify, data2classify['profile'])
                except ValueError:
                    print('Stopping classification prematurelly because there are no more sequences to classify')
                    return taxa
        return None
    
    # Utils functions
    #########################################################################################################
    
    # Verify taxas and assign to class variable
    def _verify_assign_taxas(self, taxa):
        print('_verify_assign_taxas')
        if taxa is None:
            self._taxas = self._database_data['taxas'].copy()            
        elif isinstance(taxa, list):
            self._taxas = taxa
        elif isinstance(taxa, str):
            self._taxas = [taxa]
        else:
            raise ValueError("Invalid taxa option, it must either be absent/None, be a list of taxas to extract or a string identifiying a taxa to extract")
        self._verify_taxas()

    # Verify if selected taxas are in database
    def _verify_taxas(self):
        print('_verify_taxas')
        for taxa in self._taxas:
            if taxa not in self._database_data['taxas']:
                raise ValueError("Taxa {} not found in database".format(taxa))

    # Caller function for verifying if the data and model already exist
    def _verify_load_data_model(self, data_file, model_file, taxa):
        print('_verify_load_data_model')
        self._verify_files(data_file, taxa)
        return self._verify_load_model(model_file, taxa)
        
    # Load extracted data if already exists
    def _verify_files(self, file, taxa):
        print('_verify_files')
        self.classified_data['sequence'].append(taxa)
        if os.path.isfile(file):
            self.classified_data[taxa] = load_Xy_data(file)
        else:
            self.classified_data[taxa] = {}

    # Load model if already exists
    def _verify_load_model(self, model_file, taxa):
        print('_verify_load_model')
        if os.path.exists(model_file):
            with open(model_file, 'rb') as f:
                self.models[taxa] = cloudpickle.load(f)
            return False
        else:
            return True

    def _save_model(self, model_file, taxa):
        print('_save_model')
        with open(model_file, 'wb') as f:
            cloudpickle.dump(self.models[taxa], f)

    def _verify_classifier_binary(self):
        print('_verify_classifier_binary')
        if self._classifier_binary == 'onesvm':
            if self._cv == True and self._host == True:
                pass
            elif self._cv == True and self._host == False:
                raise ValueError('Classifier One-Class SVM cannot be cross-validated with bacteria data only!\nEither add host data from parameters or choose to predict directly using this method')
            elif self._cv == False and self._host == True:
                raise ValueError('Classifier One-Class SVM cannot classify with host data!\nEither remove host data from parameters or choose another bacteria extraction method')
            elif self._cv == False and self._host == False:
                pass
        elif self._classifier_binary == 'onesvm' and self._host == False:
            pass
        elif self._classifier_binary in ['linearsvm','attention','lstm','deeplstm'] and self._host == True:
            pass
        elif self._classifier_binary in ['linearsvm','attention','lstm','deeplstm'] and self._host == False:
            raise ValueError('Classifier {} cannot classify without host data!\nEither add host data to config file or choose the One-Class SVM classifier'.format(self._classifier_binary))
        else:
            raise ValueError('Invalid classifier option for bacteria extraction!\n\tModels implemented at this moment are :\n\tBacteria isolator :  One Class SVM (onesvm)\n\tClassic algorithm : Linear SVM (linearsvm)\n\tNeural networks : Attention (attention), Shallow LSTM (lstm) and Deep LSTM (deeplstm)')

    def _verify_classifier_multiclass(self):
        print('_verify_classifier_multiclass')
        if self._classifier_multiclass in ['sgd','mnb','lstm_attention','cnn','widecnn']:
            pass
        else:
            raise ValueError('Invalid classifier option for bacteria classification!\n\tModels implemented at this moment are :\n\tClassic algorithm : Stochastic Gradient Descent (sgd) and Multinomial Naïve Bayes (mnb)\n\tNeural networks : Deep hybrid between LSTM and Attention (lstm_attention), CNN (cnn) and Wide CNN (widecnn)')

    # Merge database and host reference data for bacteria extraction training
    def _merge_database_host(self, database_data, host_data):
        print('_merge_database_host')
        self._merged_database_host = {}
        self._merged_database_host['profile'] = f"{database_data['profile']}_host_merged" # Kmers profile

        if os.path.exists(self._merged_database_host['profile']):
            files_lst = glob(os.path.join(self._merged_database_host['profile'],'*.parquet'))
            df_merged = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
            # df_merged = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
        else:
            files_lst = glob(os.path.join(database_data['profile'],'*.parquet'))
            df_db = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
            # df_db = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
            files_lst = glob(os.path.join(host_data['profile'],'*.parquet'))
            df_host = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
            # df_host = ray.data.read_parquet_bulk(files_lst, parallelism = -1)

            cols2drop = []
            for col in df_db.schema().names:
                if col not in ['id','domain','__value__']:
                    cols2drop.append(col)
            df_db = df_db.drop_columns(cols2drop)
            cols2drop = []
            for col in df_host.schema().names:
                if col not in ['id','domain','__value__']:
                    cols2drop.append(col)
            df_host = df_host.drop_columns(cols2drop)

            df_merged = df_db.union(df_host)
            df_merged.write_parquet(self._merged_database_host['profile'])

        self._merged_database_host['ids'] = np.concatenate((database_data["ids"], host_data["ids"]))  # IDs
        self._merged_database_host['kmers'] = database_data["kmers"]  # Features
        self._merged_database_host['taxas'] = ['domain']  # Known taxas for classification
        self._merged_database_host['fasta'] = (database_data['fasta'], host_data['fasta'])  # Fasta file needed for reads simulation

        return df_merged

    # Load, merge db + host & simulate validation / test datasets
    def _load_training_data_merged(self, taxa):
        print('_load_training_data_merged')
        if self._classifier_binary == 'onesvm' and taxa == 'domain':
            files_lst = glob(os.path.join(self._database_data['profile'],'*.parquet'))
            df_train = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
            # df_train = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
            df_train = df_train.map_batches(convert_archaea_bacteria, batch_format = 'pandas')
            df_val_test = self._merge_database_host(self._database_data, self._host_data)
            df_val_test = df_val_test.map_batches(convert_archaea_bacteria, batch_format = 'pandas')
            df_val = self.split_sim_cv_ds(df_val_test,self._merged_database_host, 'merged_validation')
            self._merged_training_datasets = {'train': df_train, 'validation': df_val}
            if self._cv:
                df_test = self.split_sim_cv_ds(df_val_test,self._merged_database_host, 'merged_test')
                self._merged_training_datasets['test'] = df_test
        else:
            df_train = self._merge_database_host(self._database_data, self._host_data)
            df_train = df_train.map_batches(convert_archaea_bacteria, batch_format = 'pandas')
            df_val = self.split_sim_cv_ds(df_train,self._merged_database_host, 'merged_validation')
            self._merged_training_datasets = {'train': df_train, 'validation': df_val}
            if self._cv:
                df_test = self.split_sim_cv_ds(df_train,self._merged_database_host, 'merged_test')
                self._merged_training_datasets['test'] = df_test

    # Load db & simulate validation / test datasets
    def _load_training_data(self):
        print('_load_training_data')
        files_lst = glob(os.path.join(self._database_data['profile'],'*.parquet'))
        df_train = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
        # df_train = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
        df_train = df_train.map_batches(convert_archaea_bacteria, batch_format = 'pandas')
        df_val = self.split_sim_cv_ds(df_train,self._database_data, 'validation')
        self._training_datasets = {'train': df_train, 'validation': df_val}
        if self._cv:
            df_test = self.split_sim_cv_ds(df_train,self._database_data, 'test')
            self._training_datasets['test'] = df_test

    def _sim_4_cv(self, df, kmers_ds, name):
        print('_sim_4_cv')
        cols = ['id']
        cols.extend(kmers_ds['taxas'])
        cls = pd.DataFrame(columns = cols)
        for batch in df.iter_batches(batch_format = 'pandas'):
            cls = pd.concat([cls, batch[cols]], axis = 0, ignore_index = True)
        
        sim_outdir = os.path.dirname(kmers_ds['profile'])
        cv_sim = readsSimulation(kmers_ds['fasta'], cls, list(cls['id']), 'miseq', sim_outdir, name)
        sim_data = cv_sim.simulation(self._k, kmers_ds['kmers'])
        files_lst = glob(os.path.join(sim_data['profile'],'*.parquet'))
        df = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
        # df = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
        return df
    
    def split_sim_cv_ds(self, ds, data, name):
        ds_path = os.path.join(
            os.path.dirname(data['profile']),
            f'Xy_genome_simulation_{name}_data_K{len(data["kmers"][0])}'
            )
        if os.path.exists(ds_path):
            files_lst = glob(os.path.join(ds_path,'*.parquet'))
            cv_ds = ray.data.read_parquet_bulk(files_lst, parallelism = len(files_lst))
            # cv_ds = ray.data.read_parquet_bulk(files_lst, parallelism = -1)
        else:
            cv_ds = ds.random_sample(0.1)
            if cv_ds.count() == 0:
                nb_smpl = round(ds.count() * 0.1)
                cv_ds = ds.random_shuffle().limit(nb_smpl)
            cv_ds = self._sim_4_cv(cv_ds, data, name)
        return cv_ds

# Helper functions outside of class
###############################################################################

def convert_archaea_bacteria(df):
    df.loc[df['domain'].str.lower() == 'archaea', 'domain'] = 'Bacteria'
    return df