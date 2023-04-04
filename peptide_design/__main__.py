import hashlib
import math
import multiprocessing as mp
import shutil
import sys
from functools import partial
from pathlib import Path

from Bio import SeqIO

# reduce AA sequence complexity using different set of in-vitro/silico properties
# Reduction Encoding :
# RED1 : Hydrophobicity A= hydrophobic ; B = hydrophilic ;
# RED2 : Physico-chemical   A= hydrophobic ; B = hydrophilic ; C = Aromatic ; D = Polar ; E = Acidic ; F = Basic ; G = Ionizable ;
# RED3 : Solvent accessibility ; A = Low ; B = Medium ; C = High
# RED4 : Hydrophobicity and charge; A = hydrophobic ; B = Hydrophilic : C = Charged
# RED5 : Hydrophobicity and structure;  A = Hydrophilic ; B = Hydrophobic : C = Structural
# RED6 : Hydrophobicity size and charge; A = Large and hydrophobic; B = small hydrophobic ; P = positive hydrophilic ; U = uncharged hydrophilic ; N = negative hydrophilic

RESOURCES_DIR: Path = Path(__file__).parent.parent / "resources"

REDUCTION_DICT = {
    "A": ["A", "A", "B", "B", "B", "B"],  # Alanine
    "C": ["B", "G", "A", "A", "A", "B"],  # Cysteine
    "D": ["B", "E", "C", "C", "A", "N"],  # Aspartic acid
    "E": ["B", "E", "C", "C", "A", "N"],  # Glutamic acid
    "F": ["B", "C", "A", "A", "A", "B"],  # Phenylalanine
    "G": ["A", "A", "B", "B", "C", "B"],  # Glycine
    "H": ["B", "B", "B", "A", "A", "P"],  # Histidine
    "I": ["A", "A", "A", "B", "B", "A"],  # Isoleucine
    "K": ["B", "F", "C", "C", "A", "P"],  # Lysine
    "L": ["A", "A", "A", "B", "B", "A"],  # Leucine
    "M": ["A", "A", "A", "B", "B", "A"],  # Methionine
    "N": ["B", "D", "C", "A", "A", "U"],  # Asparagine
    "P": ["B", "B", "C", "A", "C", "B"],  # Proline
    "Q": ["B", "D", "C", "A", "A", "U"],  # Glutamine
    "R": ["B", "F", "C", "C", "A", "P"],  # Arginine
    "S": ["B", "D", "B", "A", "A", "U"],  # Serine
    "T": ["B", "D", "B", "A", "A", "U"],  # Threonine
    "V": ["A", "A", "A", "B", "B", "A"],  # Valine
    "W": ["B", "-", "A", "A", "A", "A"],  # Tryptophan
    "Y": ["B", "G", "A", "A", "A", "U"],  # Tyrosine
    "r": ["B", "F", "C", "C", "A", "P"],  # Arginine
    "J": ["B", "F", "C", "C", "A", "P"],  # un-usual amino-acid
}
# Reduction dictionary in use
REDUCE_TARGET_INDEX = 6

# Database to be cleaned
dirty_neg_file_name: Path = RESOURCES_DIR / "uniprot_neg_db.fasta"
dirty_pos_file_name: Path = RESOURCES_DIR / "positive_db_nr.fasta"

# Clean database containing peptides between 3 and 18 AA
neg_fastas_file_name: Path = RESOURCES_DIR / "negative_db_size.fasta"
pos_fastas_file_name: Path = RESOURCES_DIR / "positive_db_size.fasta"

# Temporary directories for kmers
neg_temp_path: Path = RESOURCES_DIR / "kmr_neg_temp"
pos_temp_path: Path = RESOURCES_DIR / "kmr_pos_temp"


def reduce_seq(sequence: str, reduction_index: int, reduction_dict: dict=REDUCTION_DICT) -> str:
    """transforms sequence using AA characteristics in proteins:
    __ Args __
    sequence (Seq): AA sequence in single letter codification
    r_dict (dict) : transformation dictionary in single letter codification

    __ Returns __
    reduced AA sequence using transformation dictionary
    """
    reduced_seq = ""
    for aa in sequence:
        if aa in reduction_dict.keys():
            reduced_seq += reduction_dict[aa][reduction_index - 1]

    return reduced_seq


def hash_kmer(kmer):
    """
    Hash a k-mer using the SHA-256 algorithm
    Args:
        kmer (str): The k-mer to hash
    Returns:
        str: The hashed k-mer
    """
    hashed_kmer = hashlib.sha256(kmer.encode()).hexdigest()
    return hashed_kmer


def gap_kmer(kmers: list[str]) -> set[str]:
    """
    Introduce gaps into the sequentially processed sequence
    """
    k_gap = set()
    for kmer in kmers:
        for i, aa in enumerate(kmer):
            if aa != "_":
                k_gap.add("".join(kmer[:i] + "_" + kmer[i + 1 :]))
    return k_gap


def find_kmer(sequence: str, kmer_size: int, ngap: int, reduction_index: int | None) -> list[str]:
    """
    Find descriptors in the reduced peptide sequence
    """
    kmers: list[str] = []

    if isinstance(reduction_index, int):
        sequence = reduce_seq(sequence, reduction_index=reduction_index)
    for i in range(len(sequence)):
        if i + kmer_size <= len(sequence):
            kmers.append(sequence[i: i + kmer_size])

    current_kmers: list[str] = kmers
    for j in range(ngap):
        current_kmers: set[str] = gap_kmer(current_kmers)
        kmers += current_kmers

    # return [hash_kmer(kmer) for kmer in kmers]
    return kmers


def get_kmers(seq_record, reduction_index: int, path: Path) -> None:  # todo: What is `seq_record`?
    seq = seq_record.seq
    with open(path / "result.kmr", "a") as file:
        size = min(len(seq), 5)
        if size <= 2:
            gap = 0
        else:
            gap = size - 2
        kmers = find_kmer(sequence=seq, kmer_size=size, ngap=gap, reduction_index=reduction_index)
        for kmer in kmers:
            file.write("".join(str(kmer + "\n")))


def cleanup_directory(dir_name: Path) -> None:
    if dir_name.exists():
        answer = input(f"Found {dir_name}\nAre you sure that you want to delete it? [y, n]\n")
        if answer == "y":
            shutil.rmtree(dir_name)
            print(f"{dir_name} deleted.")
        else:
            print("Operation canceled")
            sys.exit(1)

    dir_name.mkdir()
    print(f"Created {dir_name}")


def parse_fasta_file(file_name: Path) -> list:
    multi_fasta = [record for record in SeqIO.parse(file_name, "fasta")]
    print(f"Ended parsing of {file_name}")
    return multi_fasta


def create_descriptors(fastas: str, folder_path: Path, name: str) -> None:
    print(f"[{name}] Performing Gapped k-mer count on {len(fastas)} sequences; reduction = {REDUCE_TARGET_INDEX})")
    pool = mp.Pool(processes=4)

    # map the analyze_sequence function to the sequences
    main = partial(get_kmers, reduction_index=REDUCE_TARGET_INDEX, path=folder_path)
    results = pool.map(main, fastas)

    # close the pool and wait for the worker processes to finish
    pool.close()
    pool.join()

    print(f"[{name}] Finished running")


def clean_database(db_file_name: str, clean_db_file_name: str) -> None:
    print(f"Cleaning {db_file_name} to keep peptides between 3 and 18")
    multi_fasta: list = parse_fasta_file(db_file_name)
    multi_fasta_size = []
    for fasta in multi_fasta:
        seq = fasta.seq
        fasta.description = ""
        if fasta.id.find("|") != -1:
            fasta.id = "".join(fasta.id.split("|")[1])
        if len(seq) in range(3, 19):
            multi_fasta_size.append(fasta)

    SeqIO.write(multi_fasta_size, clean_db_file_name, "fasta")
    print(f"Output clean database in {clean_db_file_name}")


def produce_scoring(neg_result_file_name, pos_result_file_name):
    print("Producing scoring")
    with open(pos_temp_path / pos_result_file_name, "r") as pos:
        positive = pos.readlines()
    with open(neg_temp_path / neg_result_file_name, "r") as neg:
        negative = neg.readlines()

    print("Starting to count the occurrences")
    # count of descriptors in positive then in negative list
    kmers_counter = {}
    for kmer in positive:
        if kmer in kmers_counter.keys():
            kmers_counter[kmer][0] += 1
        else:
            kmers_counter[kmer] = [1, 0, 0]
    for kmer in negative:
        if kmer in kmers_counter.keys():
            kmers_counter[kmer][1] += 1
        else:
            kmers_counter[kmer] = [0, 1, 0]

    print("Finished counting the occurrences\nStart computing scores")
    # score attribution to each descriptor
    for kmer in kmers_counter.keys():
        kmers_counter[kmer][2] = math.log((kmers_counter[kmer][0] + 1) / (kmers_counter[kmer][1] + 1))

    print("Finished computing scores\nCreate tsv file")
    # save data to tsv file
    with open("../resources/unique_set.tsv", "w") as save:
        unique_set_str = ""
        for kmer in kmers_counter.keys():
            unique_set_str += str(kmer).strip() + "\t" + str(kmers_counter[kmer]) + "\n"
        save.write(unique_set_str)


if __name__ == "__main__":
    print("Start selecting the peptides")

    if dirty_neg_file_name.exists() and dirty_pos_file_name.exists():
        # Select peptides between 3 and 18 aa
        clean_database(dirty_neg_file_name, neg_fastas_file_name)
        clean_database(dirty_pos_file_name, pos_fastas_file_name)

    # Create directories for stocking descriptors
    cleanup_directory(neg_temp_path)
    cleanup_directory(pos_temp_path)

    neg_fastas: list = parse_fasta_file(neg_fastas_file_name)
    pos_fastas: list = parse_fasta_file(pos_fastas_file_name)

    create_descriptors(neg_fastas, neg_temp_path, "Negative peptides")
    create_descriptors(pos_fastas, pos_temp_path, "Positive peptides")

    # Compute score of descriptors
    produce_scoring("result.kmr", "result.kmr")
