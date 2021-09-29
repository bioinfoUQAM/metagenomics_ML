from os.path import splitext
import re
import copy
import random
from collections import UserList, defaultdict

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

__all__ = ['SeqCollection']

# From mlr_kgenomvir
__author__ = "Amine Remita"

class SeqCollection(UserList):

    """
    Attributes
    ----------

    data : list of Bio.SeqRecord
        Collection of sequence records

    labels : list
        Collection of labels of the sequences
        The order of label needs to be the same as
        the sequences in data

    label_map : dict
        mapping of sequences and their labels (classes)

    taget_ind : defaultdict(list)
        Collection of labels and the indices of belonging
        sequences

    """

    def __init__(self, arg):

        self.data = []
        self.labels = []
        self.label_map = {}
        self.label_ind = defaultdict(list)
        self.ids = []
        self.id_map = {}
        self.id_ind = defaultdict(list)

        # If arguments are two files
        # Fasta file and annotation file
        if isinstance(arg, tuple):
            self.data = self.read_bio_file(arg[0])
            self.label_map = self.read_class_file(arg[1])
            self.__set_labels(arg)
            self.__set_ids()

        elif isinstance(arg, tuple):
            self.data = self.read_bio_file(arg[0])
# Argument pour pas de classe idem en bas
            self.__set_labels(arg)
            self.__set_ids()


        # If argument is a list of labeled seq records
        elif isinstance(arg, list):
            #self.data = arg
            self.data = copy.deepcopy(arg)
            self.__get_labels()
            self.__set_ids()

        # If argument is SeqCollection object
        elif isinstance(arg, self.__class__):
            #self.data = arg.data[:]
            self.data = copy.deepcopy(arg.data)
            self.__get_labels()
            self.__set_ids()

        # why?
        else:
            self.data = list(copy.deepcopy(arg))
            self.__get_labels()
            self.__set_ids()

    def __set_labels(self, arg):
        for ind, seqRecord in enumerate(self.data):
            if seqRecord.id in self.label_map:
                seqRecord.label = self.label_map[seqRecord.id]
                self.labels.append(self.label_map[seqRecord.id])
                self.label_ind[seqRecord.label].append(ind)

            else:
                print("No label for {}\n".format(seqRecord.id))
                self.labels.append("UNKNOWN")
                self.label_ind["UNKNOWN"].append(ind)

    def __get_labels(self):

        self.label_map = dict((seqRec.id, seqRec.label)
                        for seqRec in self.data)

        self.labels = list(seqRec.label for seqRec in self.data)

        for ind, seqRecord in enumerate(self.data):
            self.label_ind[seqRecord.label].append(ind)

    def __set_ids(self):
        for seqRecord in self.data:
            self.ids.append(seqRecord.id)

    def __getitem__(self, ind):
        # TODO
        # Give more details about this exception
        if not isinstance(ind, (int, list, slice)):
            raise TypeError("The argument must be int, list or slice")

        # shallow copy
        #if the argument is an integer
        if isinstance(ind, int):
            return self.data[ind]

        # With instantiation, data will be deep copied
        # If the argument is a list of indices
        elif isinstance(ind, list):

            tmp = [self.data[i] for i in ind if i>= 0 and i<len(self.data)]
            return self.__class__(tmp)

        return self.__class__(self.data[ind])

    @classmethod
    def read_bio_file(cls, my_file):
        path, ext = splitext(my_file)
        ext = ext.lstrip(".")

        if ext == "fa" : ext = "fasta"

        return list(seqRec for seqRec in SeqIO.parse(my_file, ext))

    @classmethod
    def read_class_file(cls, my_file):

        with open(my_file, "r") as fh:
            return dict(map(lambda x: (x[0], x[1]), (re.split(r'[\t\s,;:]', line.rstrip("\n"))
                        for line in fh if not line.startswith("#"))))

    @classmethod
    def write_fasta(cls, data, out_fasta):
        SeqIO.write(data, out_fasta, "fasta")

    @classmethod
    def write_classes(cls, classes, file_class):
        with open(file_class, "w") as fh:
            for entry in classes:
                fh.write(entry+","+classes[entry]+"\n")

    def extract_fragments(self, size, stride=1):

        if stride < 1:
            print("extract_fragments() stride parameter should be sup to 1")
            stride = 1

        new_data = []

        for ind, seqRec in enumerate(self.data):
            sequence = seqRec.seq

            i = 0
            j = 0
            while i < (len(sequence) - size + 1):
                fragment = sequence[i:i + size]

                frgRec = SeqRecord(fragment, id=seqRec.id + "_" + str(j))
                frgRec.rankParent = ind
                frgRec.idParent = seqRec.id
                frgRec.label = seqRec.label
                frgRec.description = seqRec.description
                frgRec.name = "{}.fragment_at_{}".format(seqRec.name, str(i))
                frgRec.position = i

                new_data.append(frgRec)
                i += stride
                j += 1

        return self.__class__(new_data)

    def get_parents_rank_list(self):
        parents = defaultdict(list)

        for ind, seqRec in enumerate(self.data):
            if hasattr(seqRec, "rankParent"):
                parents[seqRec.rankParent].append(ind)

        return parents

    def sample(self, size, seed=None):
        random.seed(seed)

        if size > len(self.data):
            return self

        else:
            return self.__class__(random.sample(self, size))

    def stratified_sample(self, sup_limit=25, inf_limit=5, seed=None):
        random.seed(seed)

        new_data_ind = []

        for label in self.label_ind:
            nb_seqs = len(self.label_ind[label])
            the_limit = sup_limit

            if nb_seqs <= the_limit:
                the_limit = nb_seqs

            if nb_seqs >= inf_limit:
                new_data_ind.extend(random.sample(self.label_ind[label], the_limit))

        return self[new_data_ind]

    def get_count_labels(self):
        count = {label:len(self.label_ind[label])
                for label in self.label_ind}

        return count

    def write(self, fasta_file, class_file):
       self.write_fasta(self.data, fasta_file)
       self.write_classes(self.label_map, class_file)
