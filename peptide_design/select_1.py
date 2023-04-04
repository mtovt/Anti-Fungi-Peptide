import hashlib
import multiprocessing as mp
import os
import threading
import time
from collections import Counter, defaultdict
from functools import partial
from itertools import combinations_with_replacement

from Bio import SeqIO, SeqRecord
from matplotlib import pyplot as plt

multi_fasta = [record for record in SeqIO.parse("uniprot_neg_db.fasta", "fasta")]
multi_fasta_size = []
for fasta in multi_fasta:
    record, seq = fasta.id, fasta.seq
    fasta.description = ""
    record = "".join(record.split("|")[1])
    fasta.id = record
    if len(seq) in range(3, 19):
        print(record)
        multi_fasta_size.append(fasta)
    else:
        pass

SeqIO.write(multi_fasta_size, "negative_db_size.fasta", "fasta")
