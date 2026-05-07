#       Sgourakis Lab
#   Author: Sagar Gupta 
#   Modified: Ram Pantula
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu
# import required libraries
import subprocess
import math
import csv
from collections import defaultdict

# import custom libraries
from misc.constants import *

'''

Common methods used throughout the application

'''

def run_command(command, ignore=False):

    '''
    Helps run command line operations
    '''

    cmd = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output = cmd.communicate()

    if cmd.returncode != 0:
        if ignore:
            return False
        print("--- FAIL ---\n")
        print(command)
        if output[0] != None:
            print(str(output[0], 'utf-8'))
        if output[1] != None:
            print(str(output[1], 'utf-8'))
        print("\n--- FAIL ---")
        return False
    else:
        if output[0] != None:
            output = output[0].decode('utf-8')
        return output
        # return True

def check_for_duplicates(query, file):

    filereader = open(file, "r")
    if query in filereader.read():
        return True
    else:
        return False

def distance(angle1, angle2):

    '''
    Determines the dihedral difference between two angles
    '''

    distance = 2.0 * (1.0 - math.cos(math.radians(angle1) - math.radians(angle2)))
    return distance

def distance_score_threshold(pdb1, pdb2, pdb_dihedrals):

    '''
    Determines if two structures are similar via distance score
    '''

    similar = True
    dscore = 0
    dscore_list = []
    for index, angle in enumerate(pdb_dihedrals[pdb1]):
        angle1 = angle
        angle2 = pdb_dihedrals[pdb2][index]

        angle_dist = distance(angle1, angle2)

        dscore_list.append(angle_dist)

        dscore += angle_dist
        if angle_dist > SINGLE_DIST_THRESHOLD:
            similar = False

    if dscore > SUM_DIST_THRESHOLD:
        similar = False

    return (similar, dscore, dscore_list)

def read_dihedrals47(dihedralsfile, pdb_dict, pep_len):

    '''
    Returns phi, psi angles of P4-P7 from the inputted dihedrals file
    '''

    pdb_dihedrals = defaultdict(list)

    with open(dihedralsfile, "r") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for line in reader:
            pdbid = line[0]
            if pdbid not in pdb_dict.keys(): continue
            angles = line[7:pep_len*2-3]
            angles = [float(angle) for angle in angles]
            pdb_dihedrals[pdbid] = angles

    return pdb_dihedrals

def read_all_dihedrals(dihedralsfile, pdb_dict, pep_len):

    '''
    Returns phi, psi angles from the inputted dihedrals file
    '''

    pdb_dihedrals = defaultdict(list)

    with open(dihedralsfile, "r") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for line in reader:
            pdbid = line[0]
            if pdbid not in pdb_dict.keys(): continue
            angles = line[1:]
            angles = [float(angle) for angle in angles]
            pdb_dihedrals[pdbid] = angles

    return pdb_dihedrals


def get_hamming_distance(sequence1, sequence2):
    diff_list = []
    for index, amino_acid1 in enumerate(sequence1):
        if amino_acid1 != sequence2[index]:
            diff_list.append(index+1)

    return len(diff_list), diff_list

def get_distance_score(pdb1, pdb2, pdb1_pepchain, pdb2_pepchain):

    '''
        Computes distance score between two input .PDB files 
        Only works on ∆7 9mer structures
        Assumptions:
            Both structures are 9mers
    '''

    import pyrosetta
    from pyrosetta import pose_from_pdb
    pyrosetta.init()

    pose_pdb1 = pose_from_pdb(pdb1)
    pdb1_dihedrals = get_pep_dihedrals(pose_pdb1, pdb1_pepchain, 9)
    pdb1_dihedrals_47 = pdb1_dihedrals[6:14]

    pose_pdb2 = pose_from_pdb(pdb2)
    pdb2_dihedrals = get_pep_dihedrals(pose_pdb2, pdb2_pepchain, 9)
    pdb2_dihedrals_47 = pdb2_dihedrals[6:14]


    similar, dscore, dscore_list = distance_score_threshold2(pdb1_dihedrals_47, pdb2_dihedrals_47)

    return similar, dscore, dscore_list


def get_pep_dihedrals(pose_pdb, pdb1_pepchain, pep_length):
    '''
        Determines peptide dihedral angles of a given .PDB file
    '''

    dihedrals = []

    pdb1_p1 = pose_pdb.pdb_info().pdb2pose(pdb1_pepchain, 1)
    pdb1_pO = pose_pdb.pdb_info().pdb2pose(pdb1_pepchain, pep_length)

    for resi_num in range(pdb1_p1, pdb1_pO+1):
        phi = pose_pdb.phi(resi_num)
        psi = pose_pdb.psi(resi_num)

        dihedrals.append(phi)
        dihedrals.append(psi)

    return dihedrals

def distance_score_threshold2(pdbid1, pdbid2, pdb1_dihedrals, pdb2_dihedrals):

    '''
        Determines if two structures are similar via distance score
        Returns (bool, float): (whether two structures are similar, their distance score)
    '''
    print(f"{pdbid1}/{pdbid2}:{len(pdb1_dihedrals)} and {len(pdb2_dihedrals)}")
    similar = True
    dscore = 0
    dscore_list = []
    for index, angle in enumerate(pdb1_dihedrals):
        angle1 = angle
        angle2 = pdb2_dihedrals[index]

        angle_dist = distance(angle1, angle2)

        dscore_list.append(angle_dist)

        dscore += angle_dist
        if angle_dist > SINGLE_DIST_THRESHOLD:
            similar = False

    if dscore > SUM_DIST_THRESHOLD:
        similar = False

    return (similar, dscore, dscore_list)

def distance_score_threshold3(pdb1_dihedrals, pdb2_dihedrals):

    '''
        Determines if two structures are similar via distance score
        Returns (bool, float): (whether two structures are similar, their distance score)
    '''

    similar = True
    dscore = 0
    dscore_list = []
    for index, angle in enumerate(pdb1_dihedrals):
        angle1 = angle
        angle2 = pdb2_dihedrals[index]

        angle_dist = distance(angle1, angle2)

        dscore_list.append(angle_dist)

        dscore += angle_dist
        if angle_dist > SINGLE_DIST_THRESHOLD:
            similar = False

    if dscore > SUM_DIST_THRESHOLD:
        similar = False

    return (similar, dscore, dscore_list)
    
def is_pep_homolog(seq1, seq2):

    differences = 0
    for index, aa_1 in enumerate(list(seq1)):
        aa_2 = seq2[index]
        if aa_1 != aa_2:
            differences += 1

    return differences <= 3, differences

def get_rmsd_47(pdb1, pdb2):

    import pyrosetta
    from pyrosetta import pose_from_pdb
    native_pose = pose_from_pdb(pdb1)
    my_pose = pose_from_pdb(pdb2)

    start_native = native_pose.conformation().chain_begin(1)
    end_native = native_pose.conformation().chain_end(1)
    start_my = my_pose.conformation().chain_begin(1)
    end_my = my_pose.conformation().chain_end(1)

    # remove MHC chain
    pyrosetta.rosetta.protocols.grafting.delete_region(native_pose, start_native, end_native)
    pyrosetta.rosetta.protocols.grafting.delete_region(my_pose, start_my, end_my)

    # remove resi 1-3 and resi 8-9
    # 123456789 -> 456789 (123456) -> 1234
    pyrosetta.rosetta.protocols.grafting.delete_region(native_pose, 1, 3)
    pyrosetta.rosetta.protocols.grafting.delete_region(native_pose, 5, 6)

    pyrosetta.rosetta.protocols.grafting.delete_region(my_pose, 1, 3)
    pyrosetta.rosetta.protocols.grafting.delete_region(my_pose, 5, 6)

    rmsd = pyrosetta.rosetta.core.scoring.bb_rmsd_including_O(my_pose, native_pose)

    return rmsd

def read_anchor_file(anchor_file, anchor_class, pdb_dict=None):
    
    '''
        Returns PDBs of a specific anchor class (anchor_class) as stored in an anchor class file (anchor_file)
    '''

    return_pdbs = defaultdict(list)
    with open(anchor_file, "r") as csvfile:
        reader = csv.reader(csvfile)
        next(reader) # skip header
        for line in reader:
            if int(line[1]) == anchor_class:
                if pdb_dict != None and line[0] in pdb_dict.keys():
                    return_pdbs[line[0]] = [int(line[3]), int(line[4])]
                elif pdb_dict == None:
                    return_pdbs[line[0]] = [int(line[3]), int(line[4])]
    
    return return_pdbs

def read_central_dihedral(pep_dihed_stem, start_pdb_list):

    '''
        Get "central" dihedral angles of a given PDB list irrespective of 

        ∆7 anchor class:
            [1] 2 3456 7 [8]
            1 [2] 3 4567 8 [9]
            [1] 2 3456 7 [8] 9
            [1] 2 3456 7 [8] 9 10
            1 [2] 3 4567 8 [9] 10
            1 2 [3] 4 5678 9 [10]

    '''

    pdb_dihedrals = defaultdict(list)
    for length in [8, 9, 10]:
        dihedralsfile = f"{pep_dihed_stem}{length}.csv"

        with open(dihedralsfile, "r") as csvfile:
            reader = csv.reader(csvfile)
            next(reader)
            for line in reader:
                pdbid = line[0]
                if pdbid in start_pdb_list.keys():
                    anchor1 = start_pdb_list[pdbid][0] - 180 # 2 
                    anchor2 = start_pdb_list[pdbid][1] - 180 # 9

                    center_start_pos = anchor1 + 2  # 2 + + 2 = 4
                    center_start_index = center_start_pos*2 - 1  # 4*2-1 = 7
                    center_end_pos = anchor2 - 2  # 9 - 2 = 7
                    center_end_index = center_end_pos*2  # 7*2 = 14 + 1

                    angles = line[center_start_index:center_end_index+1]
                    angles = [float(angle) for angle in angles]
                    pdb_dihedrals[pdbid] = angles
    
    return pdb_dihedrals

def read_all_dihedral(pep_dihed_stem, start_pdb_list):

    pdb_dihedrals = defaultdict(list)
    for length in [8, 9, 10]:
        dihedralsfile = f"{pep_dihed_stem}{length}.csv"

        with open(dihedralsfile, "r") as csvfile:
            reader = csv.reader(csvfile)
            next(reader)
            for line in reader:
                pdbid = line[0]
                if pdbid in start_pdb_list.keys():
                    anchor1 = start_pdb_list[pdbid][0] - 180  # 2
                    anchor2 = start_pdb_list[pdbid][1] - 180  # 9

                    anchor_start_index = anchor1*2 - 1  # 2*2-1 = 3
                    anchor_end_index = anchor2*2  # 9*2 = 18 + 1

                    angles = line[anchor_start_index:anchor_end_index+1]
                    angles = [float(angle) for angle in angles]
                    pdb_dihedrals[pdbid] = angles
    
    return pdb_dihedrals

def distance_score_threshold4(pdb1, pdb2, pdb_dihedrals, anchor_class_sum_threshold):

    '''
    Determines if two structures are similar via distance score
    '''

    similar = True
    dscore = 0
    dscore_list = []
    for index, angle in enumerate(pdb_dihedrals[pdb1]):
        angle1 = angle
        angle2 = pdb_dihedrals[pdb2][index]

        angle_dist = distance(angle1, angle2)

        dscore_list.append(angle_dist)

        dscore += angle_dist
        if angle_dist > SINGLE_DIST_THRESHOLD:
            similar = False

    if dscore > anchor_class_sum_threshold:
        similar = False

    return (similar, dscore, dscore_list)

def get_coordinates_on_reference_map(phi_psi_angle, reference_map):

    phi = phi_psi_angle[0]
    psi = phi_psi_angle[1]

    height = reference_map.shape[0]
    width = reference_map.shape[1]

    i = int((180 - psi) / 360 * height)
    j = int((phi + 180) / 360 * width)

    # If i or j == resolution, adjust it.
    if i == height:
        i = height - 1
    if j == width:
        j = width - 1

    return (i, j)
