#       Sgourakis Lab
#   Author: Sagar Gupta 
#   Modified: Ram Pantula
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu

#USER VARIABLE **** IMPORTANT FOR USERS ****
mainpath="{{ROOT}}"
dbpath=f"{mainpath}/Compare"
ROSETTA_INSTALL_DIR = "{{ROSETTA}}"
condapath = "{{CONDA}}"



# parameters
MUTATION_THRESH = 5 # number of allowed mutations in the HLA (inclusive)

LONG_PEP_LENGTH = 20 # Upper bound on what we consider a "peptide" chain
PEP_LOWER = 8 # Smallest peptide length to consider
PEP_UPPER = 10 # Longest peptide length to consider

HC_CUTOFF = 90 # Sequence identity score cutoff for HLA heavy chain (out of 180)
B2M_CUTOFF = 90 # Sequence identity score cutoff for HLA B2M chain (out of 100)

RECEPTOR_DIST = 5 # Distance (Å) threshold between peptide and receptor

DISTANCE_PEP_MHC = 15.0 # 65th residue of MHC Ca atom and 2nd residue for peptide Ca atom (from observation)

MHC_TRIM_LENGTH = 181 # Number of residues in MHC chain + 1 (so really it is 180)

FIRST_MHC_STRUC_YEAR = 1988

# reference values
A0201_SEQ = "GSHSMRYFFTSVSRPGRGEPRFIAVGYVDDTQFVRFDSDAASQRMEPRAPWIEQEGPEYWDGETRKVKAHSQTHRVDLGTLRGYYNQSEAGSHTVQRMYGCDVGSDWRFLRGYHQYAYDGKDYIALKEDLRSWTAADMAAQTTKHKWEAAHVAEQLRAYLEGTCVEWLRRYLENGKETLQ"
B2M_SEQ = "MIQRTPKIQVYSRHPAENGKSNFLNCYVSGFHPSDIEVDLLKNGERIEKVEHSDLSFSKDWSFYLLYYTEFTPTEKDEYACRVNHVTLSQPKIVKWDRDM"

DEFAULT_MHC_CHAIN = 'A'
DEFAULT_PEP_CHAIN = 'B'

MHC_SEQ_MOTIF_SHS = 'SHS'
MHC_SEQ_MOTIF_HS = 'HS'

SINGLE_DIST_THRESHOLD = 1.0 # Distance score threshold for every single dihedral angle pair
SUM_DIST_THRESHOLD = 1.5 # Distance score threshold for every single dihedral angle pair

amino_acids = ["A", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"]

supertypes = {
    "A*01": ["HLA-A*01:01", "HLA-A*01:03", "HLA-A*01:12", "HLA-A*26:09",
            "HLA-A*26:18", "HLA-A*30:12", "HLA-A*36:02", "HLA-A*25:01", "HLA-A*36:03", "HLA-A*26:01",
            "HLA-A*01:04", "HLA-A*01:14", "HLA-A*26:10", "HLA-A*26:19", "HLA-A*32:02", "HLA-A*36:04",
            "HLA-A*25:02", "HLA-A*74:10", "HLA-A*26:02", "HLA-A*01:06", "HLA-A*01:15", "HLA-A*26:11",
            "HLA-A*26:21", "HLA-A*32:05", "HLA-A*25:04", "HLA-A*80:01", "HLA-A*26:03", "HLA-A*01:07",
            "HLA-A*26:04", "HLA-A*26:12", "HLA-A*26:23", "HLA-A*32:06", "HLA-A*26:22", "HLA-A*30:02",
            "HLA-A*01:08", "HLA-A*26:05", "HLA-A*26:13", "HLA-A*26:24", "HLA-A*32:07", "HLA-A*31:10",
            "HLA-A*30:03", "HLA-A*01:09", "HLA-A*26:06", "HLA-A*26:14", "HLA-A*26:26", "HLA-A*32:09",
            "HLA-A*32:03", "HLA-A*30:04", "HLA-A*01:10", "HLA-A*26:07", "HLA-A*26:15", "HLA-A*30:06",
            "HLA-A*32:10", "HLA-A*32:04", "HLA-A*32:01", "HLA-A*01:11", "HLA-A*26:08", "HLA-A*26:17",
            "HLA-A*30:09", "HLA-A*36:01", "HLA-A*32:08"],
    "A*03" : ["HLA-A*30:01", "HLA-A*30:08", "HLA-A*30:11", "HLA-A*30:14", "HLA-A*30:15",
            "HLA-A*02:52", "HLA-A*30:13", "HLA-A*68:06", "HLA-A*68:07"],
    "A*01, A*24" : ["HLA-A*29:02", "HLA-A*29:01", "HLA-A*29:05", "HLA-A*29:09", "HLA-A*29:11", "HLA-A*29:13",
            "HLA-A*29:03", "HLA-A*29:06", "HLA-A*29:10", "HLA-A*29:12"],
    "A*02": ["HLA-A*02:01", "HLA-A*02:09", "HLA-A*02:24", "HLA-A*02:40", "HLA-A*02:57", "HLA-A*02:71", "HLA-A*68:27", "HLA-A*02:41",
            "HLA-A*02:02", "HLA-A*02:11", "HLA-A*02:25", "HLA-A*02:43", "HLA-A*02:58", "HLA-A*02:72", "HLA-A*68:28", "HLA-A*02:42",
            "HLA-A*02:03", "HLA-A*02:12", "HLA-A*02:26", "HLA-A*02:44", "HLA-A*02:59", "HLA-A*02:74", "HLA-A*02:50",
            "HLA-A*02:04", "HLA-A*02:13", "HLA-A*02:27", "HLA-A*02:45", "HLA-A*02:61", "HLA-A*02:75", "HLA-A*02:60",
            "HLA-A*02:05", "HLA-A*02:15", "HLA-A*02:28", "HLA-A*02:46", "HLA-A*02:62", "HLA-A*02:77", "HLA-A*02:73",
            "HLA-A*02:06", "HLA-A*02:16", "HLA-A*02:30", "HLA-A*02:47", "HLA-A*02:63", "HLA-A*02:78", "HLA-A*02:84",
            "HLA-A*02:07", "HLA-A*02:18", "HLA-A*02:31", "HLA-A*02:48", "HLA-A*02:66", "HLA-A*02:79", "HLA-A*68:15",
            "HLA-A*02:14", "HLA-A*02:19", "HLA-A*02:36", "HLA-A*02:49", "HLA-A*02:67", "HLA-A*02:82",
            "HLA-A*02:17", "HLA-A*02:20", "HLA-A*02:37", "HLA-A*02:51", "HLA-A*02:68", "HLA-A*02:83",
            "HLA-A*68:02", "HLA-A*02:21", "HLA-A*02:38", "HLA-A*02:54", "HLA-A*02:69", "HLA-A*02:85",
            "HLA-A*69:01", "HLA-A*02:22", "HLA-A*02:39", "HLA-A*02:56", "HLA-A*02:70", "HLA-A*02:86"],
    "A*03": ["HLA-A*03:01", "HLA-A*03:02", "HLA-A*03:16", "HLA-A*11:12", "HLA-A*31:05", "HLA-A*34:04", "HLA-A*68:12", "HLA-A*74:02", "HLA-A*02:65",
            "HLA-A*11:01", "HLA-A*03:04", "HLA-A*03:17", "HLA-A*11:13", "HLA-A*31:06", "HLA-A*34:06", "HLA-A*68:13", "HLA-A*74:03", "HLA-A*02:80",
            "HLA-A*31:01", "HLA-A*03:05", "HLA-A*11:02", "HLA-A*11:14", "HLA-A*31:09", "HLA-A*66:02", "HLA-A*68:14", "HLA-A*74:04", "HLA-A*03:09",
            "HLA-A*33:01", "HLA-A*03:06", "HLA-A*11:03", "HLA-A*11:15", "HLA-A*33:04", "HLA-A*66:03", "HLA-A*68:16", "HLA-A*74:05", "HLA-A*11:06",
            "HLA-A*33:03", "HLA-A*03:07", "HLA-A*11:04", "HLA-A*11:16", "HLA-A*33:05", "HLA-A*66:04", "HLA-A*68:19", "HLA-A*74:07", "HLA-A*11:22",
            "HLA-A*66:01", "HLA-A*03:08", "HLA-A*11:05", "HLA-A*11:20", "HLA-A*33:06", "HLA-A*68:03", "HLA-A*68:21", "HLA-A*74:08", "HLA-A*31:12",
            "HLA-A*68:01", "HLA-A*03:10", "HLA-A*11:07", "HLA-A*11:21", "HLA-A*33:07", "HLA-A*68:04", "HLA-A*68:22", "HLA-A*74:09", "HLA-A*68:05",
            "HLA-A*74:01", "HLA-A*03:12", "HLA-A*11:08", "HLA-A*11:23", "HLA-A*33:07", "HLA-A*68:08", "HLA-A*68:24", "HLA-A*74:11", "HLA-A*68:20",
            "HLA-A*03:13", "HLA-A*11:09", "HLA-A*31:03", "HLA-A*34:02", "HLA-A*68:09", "HLA-A*68:25", "HLA-A*68:23",
            "HLA-A*03:14", "HLA-A*11:10", "HLA-A*31:04", "HLA-A*34:03", "HLA-A*68:10", "HLA-A*68:26", "HLA-A*74:06", "HLA-A*30:01", "HLA-A*30:03"],
    "A*24": ["HLA-A*23:01", "HLA-A*23:02", "HLA-A*23:10", "HLA-A*24:10", "HLA-A*24:22", "HLA-A*24:33", "HLA-A*24:40", "HLA-A*23:05", "HLA-A*24:42",
            "HLA-A*24:02", "HLA-A*23:03", "HLA-A*24:03", "HLA-A*24:11", "HLA-A*24:23", "HLA-A*24:34", "HLA-A*24:43", "HLA-A*23:12", "HLA-A*24:44",
            "HLA-A*23:04", "HLA-A*24:05", "HLA-A*24:13", "HLA-A*24:26", "HLA-A*24:35", "HLA-A*24:46", "HLA-A*24:17", "HLA-A*24:52",
            "HLA-A*23:06", "HLA-A*24:06", "HLA-A*24:18", "HLA-A*24:27", "HLA-A*24:37", "HLA-A*24:47", "HLA-A*24:25",
            "HLA-A*23:07", "HLA-A*24:08", "HLA-A*24:20", "HLA-A*24:28", "HLA-A*24:38", "HLA-A*24:48", "HLA-A*24:30",
            "HLA-A*23:08", "HLA-A*24:09", "HLA-A*24:21", "HLA-A*24:29", "HLA-A*24:39", "HLA-A*24:49", "HLA-A*24:41"],
    'B07': ["HLA-B*07:02", "HLA-B*07:35", "HLA-B*42:02", "HLA-B*55:04", "HLA-B*67:01",
            "HLA-B*07:03", "HLA-B*07:75", "HLA-B*42:18", "HLA-B*55:15", "HLA-B*78:01",
            "HLA-B*07:05", "HLA-B*07:91", "HLA-B*54:01", "HLA-B*56:01", "HLA-B*81:01",
            "HLA-B*07:06", "HLA-B*07:96", "HLA-B*54:18", "HLA-B*56:02", "HLA-B*82:01",
            "HLA-B*07:07", "HLA-B*39:10", "HLA-B*55:01", "HLA-B*56:04", "HLA-B*82:02",
            "HLA-B*07:08", "HLA-B*39:20", "HLA-B*55:02", "HLA-B*56:05", "HLA-B*07:10",
            "HLA-B*42:01", "HLA-B*55:03", "HLA-B*56:43"],
    "B*35": ["HLA-B*15:08", "HLA-B*35:04", "HLA-B*35:13", "HLA-B*35:21", "HLA-B*35:36", "HLA-B*40:08",
            "HLA-B*15:11", "HLA-B*35:05", "HLA-B*35:14", "HLA-B*35:23", "HLA-B*35:43", "HLA-B*53:01", "HLA-B*15:29",
            "HLA-B*35:06", "HLA-B*35:15", "HLA-B*35:24", "HLA-B*35:44", "HLA-B*53:03", "HLA-B*18:07", "HLA-B*35:08",
            "HLA-B*35:16", "HLA-B*35:25", "HLA-B*35:61", "HLA-B*53:05", "HLA-B*35:01", "HLA-B*35:09", "HLA-B*35:17", "HLA-B*35:27", "HLA-B*35:68",
            "HLA-B*35:02", "HLA-B*35:10", "HLA-B*35:18", "HLA-B*35:29", "HLA-B*35:77",
            "HLA-B*35:03", "HLA-B*35:12", "HLA-B*35:19", "HLA-B*35:32", "HLA-B*40:07"],
    "B*51": ["HLA-B*51:01", "HLA-B*51:04", "HLA-B*51:07", "HLA-B*51:12", "HLA-B*51:19", "HLA-B*51:76",
            "HLA-B*51:02", "HLA-B*51:05", "HLA-B*51:08", "HLA-B*51:14", "HLA-B*51:33", "HLA-B*52:01",
            "HLA-B*51:03", "HLA-B*51:06", "HLA-B*51:10", "HLA-B*51:15", "HLA-B*51:61", "HLA-B*59:01"],
    "B*58": ["HLA-B*15:16", "HLA-B*15:17", "HLA-B*15:67", "HLA-B*57:01", "HLA-B*57:02", "HLA-B*57:03", "HLA-B*57:04", "HLA-B*57:05", 
             "HLA-B*57:25", "HLA-B*58:01", "HLA-B*58:02", "HLA-B*58:06"],
    "B*08": ["HLA-B*08:01", "HLA-B*08:04", "HLA-B*08:03", "HLA-B*08:05",],
    "B*18": ["HLA-B*18:01", "HLA-B*18:03", "HLA-B*18:06", "HLA-B*18:02", "HLA-B*18:05", "HLA-B*18:09",],
    "B*39": ["HLA-B*39:01", "HLA-B*39:04", "HLA-B*39:09", "HLA-B*39:24", "HLA-B*73:01",
            "HLA-B*39:03", "HLA-B*39:06", "HLA-B*39:12", "HLA-B*39:54"],
    "B*14": ["HLA-B*14:01", "HLA-B*14:02", "HLA-B*14:03", "HLA-B*14:04", "HLA-B*14:05", "HLA-B*14:06", "HLA-B*14:11",
            "HLA-B*15:09", "HLA-B*15:10", "HLA-B*15:18", "HLA-B*15:21", "HLA-B*15:23", "HLA-B*15:37", "HLA-B*15:93",
            "HLA-B*38:01", "HLA-B*38:02", "HLA-B*38:09", "HLA-B*39:05", "HLA-B*39:07", "HLA-B*39:11", "HLA-B*78:03"],
    "B*15": ["HLA-B*13:01", "HLA-B*13:02", "HLA-B*13:04", "HLA-B*13:38",
            "HLA-B*15:01", "HLA-B*15:02", "HLA-B*15:03", "HLA-B*15:04", "HLA-B*15:05", "HLA-B*15:06", "HLA-B*15:07",
            "HLA-B*15:12", "HLA-B*15:13", "HLA-B*15:15", "HLA-B*15:20", "HLA-B*15:24", "HLA-B*15:25", "HLA-B*15:27",
            "HLA-B*15:31", "HLA-B*15:32", "HLA-B*15:34", "HLA-B*15:35", "HLA-B*15:36", "HLA-B*15:39", "HLA-B*15:46",
            "HLA-B*18:04", "HLA-B*35:20", "HLA-B*35:28","HLA-B*40:02", "HLA-B*40:03", "HLA-B*40:06", "HLA-B*40:09", 
            "HLA-B*40:26", "HLA-B*40:38","HLA-B*47:01", "HLA-B*47:03","HLA-B*48:01", "HLA-B*48:02", "HLA-B*48:04", "HLA-B*48:07"],
    "B*40": ["HLA-B*15:30", "HLA-B*15:58","HLA-B*37:01","HLA-B*39:02", "HLA-B*39:08","HLA-B*40:01", "HLA-B*40:04", "HLA-B*40:05", 
             "HLA-B*40:10", "HLA-B*40:11", "HLA-B*40:12", "HLA-B*40:14", "HLA-B*40:15","HLA-B*40:16", "HLA-B*40:23", "HLA-B*40:36", 
             "HLA-B*40:46", "HLA-B*40:49","HLA-B*41:01", "HLA-B*41:02", "HLA-B*41:03", "HLA-B*41:23","HLA-B*44:05", "HLA-B*44:10", 
             "HLA-B*44:15", "HLA-B*45:01", "HLA-B*48:03", "HLA-B*49:01", "HLA-B*50:01", "HLA-B*50:02", "HLA-B*50:04"],
    "B*27": ["HLA-B*27:01", "HLA-B*27:02", "HLA-B*27:03", "HLA-B*27:04", "HLA-B*27:05", "HLA-B*27:06", "HLA-B*27:07", "HLA-B*27:08", "HLA-B*27:14"],
    "B*44": ["HLA-B*44:02", "HLA-B*44:03", "HLA-B*44:04", "HLA-B*44:06", "HLA-B*44:07",
            "HLA-B*44:08", "HLA-B*44:09", "HLA-B*44:15", "HLA-B*44:27", "HLA-B*44:29"],
    "C*01":[ "HLA-C*01:02", "HLA-C*01:03", "HLA-C*01:06", "HLA-C*01:44", "HLA-C*01:57", "HLA-C*03:03", "HLA-C*03:04", "HLA-C*03:05", 
            "HLA-C*03:06", "HLA-C*03:07", "HLA-C*03:09", "HLA-C*03:13", "HLA-C*03:19","HLA-C*04:01", "HLA-C*04:06", "HLA-C*04:07", 
            "HLA-C*04:10", "HLA-C*04:15", "HLA-C*04:43","HLA-C*05:01", "HLA-C*05:09", "HLA-C*17:01", "HLA-C*17:03", "HLA-C*18:01", "HLA-C*18:02",
            "HLA-C*08:01", "HLA-C*08:02", "HLA-C*08:03", "HLA-C*08:04", "HLA-C*08:06", "HLA-C*08:13", "HLA-C*08:72",
            "HLA-C*15:02", "HLA-C*15:03", "HLA-C*15:05", "HLA-C*15:07", "HLA-C*15:08", "HLA-C*15:10", "HLA-C*15:13",],
    "C*02": ["HLA-B*46:01", "HLA-B*56:03","HLA-C*01:04", "HLA-C*02:02", "HLA-C*02:03", "HLA-C*02:09", "HLA-C*02:10", 
             "HLA-C*03:02", "HLA-C*03:15", "HLA-C*03:16", "HLA-C*06:02", "HLA-C*06:03", "HLA-C*06:04", "HLA-C*06:06", 
             "HLA-C*07:26","HLA-C*12:02", "HLA-C*12:03", "HLA-C*12:04", "HLA-C*12:05", "HLA-C*12:07","HLA-C*14:02", 
             "HLA-C*14:03", "HLA-C*14:04", "HLA-C*14:06", "HLA-C*15:04", "HLA-C*15:09","HLA-C*16:01", "HLA-C*16:02", "HLA-C*16:04"],
    "C*07": ["HLA-C*07:01", "HLA-C*07:02", "HLA-C*07:03", "HLA-C*07:04", "HLA-C*07:05",
            "HLA-C*07:06", "HLA-C*07:07", "HLA-C*07:08", "HLA-C*07:10", "HLA-C*07:14",
            "HLA-C*07:17", "HLA-C*07:18", "HLA-C*07:19", "HLA-C*07:24", "HLA-C*07:27", "HLA-C*07:31"]}
