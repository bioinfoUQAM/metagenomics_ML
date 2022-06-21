import os
import ray
import glob
import warnings

from shutil import rmtree
from subprocess import run
from joblib import Parallel, delayed, parallel_backend

import numpy as np
import modin.pandas as pd

__author__ = ['Amine Remita', 'Nicolas de Montigny']

__all__ = ['kmers_collection','construct_data',
            'compute_seen_kmers_of_sequence','compute_given_kmers_of_sequence','compute_kmers',
            'parallel_extraction','build_kmers_Xy_data','build_kmers_X_data']

"""
Module adapted from module kmer_collections.py of
mlr_kgenomvir package [Remita et al. 2022]

Save kmers directly to drive instead of memory and adapted / added functions to do so.
Converted to be only functions instead of object for parallelization.
"""

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings("ignore")

# #####
# Data build functions
# ####################

def build_kmers_Xy_data(seq_data, k, Xy_file, dataset, length = 0, kmers_list = None):

    if isinstance(kmers_list, list):
        method = 'given'
    else:
        method = 'seen'

    kmers_collection(seq_data, Xy_file, length, k, dataset, method = method, kmers_list = kmers_list)

    classes = np.array(seq_data.labels)

    return classes

def build_kmers_X_data(seq_data, X_file, kmers_list, k, dataset, length = 0):

    kmers_collection(seq_data, X_file, length, k, dataset, method = 'given', kmers_list = kmers_list)

# #####
# Kmers computing
# ##################

def kmers_collection(seq_data, Xy_file, length, k, dataset, method = 'seen', kmers_list = None):

    dir_path = os.path.join(os.path.split(Xy_file)[0],"tmp","")
    kmc_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),"KMC","bin")
    faSplit = os.path.join(os.path.dirname(os.path.realpath(__file__)),"faSplit")

    compute_kmers(seq_data, method, kmers_list, k, dir_path, faSplit, kmc_path, Xy_file, dataset)

    rmtree(dir_path)

def na_2_zero(df):
    df = df.fillna(0)
    return df

def construct_data(Xy_file, dir_path):
    files_list = glob.glob(os.path.join(dir_path,'*.csv'))
    # Read/concatenate files with Ray
    df = ray.data.read_csv(files_list, meta_provider = FastFileMetadataProvider())
    # Fill NAs with 0
    df = df.map_batches(na_2_zero, batch_format = 'pandas')
    # Save dataset
    df.write_parquet(Xy_file)

def compute_seen_kmers_of_sequence(kmc_path, k, dir_path, ind, file):
    # Make tmp folder per sequence
    tmp_folder = os.path.join(dir_path,"tmp_{}".format(ind))
    id = os.path.splitext(os.path.basename(file))[0]
    os.mkdir(tmp_folder)
    # Count k-mers with KMC
    cmd_count = os.path.join(kmc_path,"kmc -k{} -fm -ci5 -cs1000000000 -m10 -hp {} {} {}".format(k, file, os.path.join(tmp_folder, str(ind)), tmp_folder))
    run(cmd_count, shell = True, capture_output=True)
    # Transform k-mers db with KMC
    cmd_transform = os.path.join(kmc_path,"kmc_tools transform {} dump {}".format(os.path.join(tmp_folder, str(ind)), os.path.join(dir_path, "{}.txt".format(ind))))
    run(cmd_transform, shell = True, capture_output=True)

    # Transpose kmers profile
    tmp_df = pd.read_table(os.path.join(dir_path,"{}.txt".format(ind)), sep = '\t', header = None, names = ['id', str(id)])
    tmp_df.T.to_csv(os.path.join(dir_path,"{}.csv".format(ind)), header = False)

    # Delete temp dir and file
    rmtree(tmp_folder)
    os.remove(os.path.join(dir_path,"{}.txt".format(ind)))

def compute_given_kmers_of_sequence(kmers_list, kmc_path, k, dir_path, ind, file):
    # Make tmp folder per sequence
    tmp_folder = os.path.join(dir_path,"tmp_{}".format(ind))
    id = os.path.splitext(os.path.basename(file))[0]
    os.mkdir(tmp_folder)
    # Count k-mers with KMC
    cmd_count = os.path.join(kmc_path,"kmc -k{} -fm -ci4 -cs1000000000 -m10 -hp {} {} {}".format(k, file, os.path.join(tmp_folder, str(ind)), tmp_folder))
    run(cmd_count, shell = True, capture_output=True)
    # Transform k-mers db with KMC
    cmd_transform = os.path.join(kmc_path,"kmc_tools transform {} dump {}".format(os.path.join(tmp_folder, str(ind)), os.path.join(dir_path, "{}.txt".format(ind))))
    run(cmd_transform, shell = True, capture_output=True)

    profile = pd.read_table(os.path.join(dir_path,"{}.txt".format(ind)), sep = '\t', header = None, names = ['id', str(id)]).T
    # Temp df to write given kmers to file
    tmp_df = pd.DataFrame(np.zeros((1,len(kmers_list))), columns = kmers_list, index = [id])
    for kmer in kmers_list:
        if kmer in profile.columns:
            tmp_df.at[id,kmer] = profile.loc[id,kmer]
        else:
            tmp_df.at[id,kmer] = 0

    tmp_df.to_csv(os.path.join(dir_path,"{}.csv".format(ind)), header = False, index_label = 'id')

    # Delete temp dir and file
    rmtree(tmp_folder)
    os.remove(os.path.join(dir_path,"{}.txt".format(ind)))

def compute_kmers(seq_data, method, kmers_list, k, dir_path, faSplit, kmc_path, Xy_file, dataset):
    file_list = []

    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    cmd_split = '{} byname {} {}'.format(faSplit, seq_data.data, dir_path)

    os.system(cmd_split)

    file_list = glob.glob(os.path.join(dir_path,'*.fa'))

    # Extract kmers in parallel using KMC3
    parallel_extraction(file_list, method, kmers_list, kmc_path, k, dir_path)
    # build kmers matrix
    construct_data(Xy_file, dir_path)


def parallel_extraction(file_list, method, kmers_list, kmc_path, k, dir_path):
    if method == 'seen':
        with parallel_backend('threading'):
            Parallel(n_jobs = -1, prefer = 'threads', verbose = 100)(
            delayed(compute_seen_kmers_of_sequence)
            (kmc_path, k, dir_path, i, file) for i, file in enumerate(file_list))
    elif method == 'given':
        with parallel_backend('threading'):
            Parallel(n_jobs = -1, prefer = 'threads', verbose = 100)(
            delayed(compute_given_kmers_of_sequence)
            (kmers_list, kmc_path, k, dir_path, i, file) for i, file in enumerate(file_list))
