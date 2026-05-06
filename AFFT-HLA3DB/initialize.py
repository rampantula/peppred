 #!/usr/bin/env python
 
import Bio
from Bio import pairwise2
from Bio.Align import substitution_matrices
blosum62_matrix = substitution_matrices.load("BLOSUM62")
import os, glob
import shutil

TEMPLATE_PDB_FOLDER = "template_pdbs/"
TEMPLATE_SEQ_FOLDER = "template_seq/"
def pep_homolog(seq1, seq2):
    differences = 0
    for index, aa_1 in enumerate(list(seq1)):
        aa_2 = seq2[index]
        if aa_1 != aa_2: differences += 1
    return differences <= 3, differences  

def get_template_pdbs(target_pdbid, target_pep_seq):

    template_info = {}
    for template_seq_file in glob.glob(f"{TEMPLATE_SEQ_FOLDER}/*.txt"):
        template_pdbid = template_seq_file.split("/")[-1].split("_")[0]
        _, pep_seq = get_seq(template_seq_file)
        template_info[template_pdbid] = pep_seq

    template_blosum_scores = {}

    for template_pdbid, template_pep_seq in template_info.items():
        # For training purposes, we removed peptide homologs in the template search
        # if not pep_homolog(target_pep_seq, template_pep_seq)[0]:
        blosum_score = pairwise2.align.globaldx(target_pep_seq, template_pep_seq, blosum62_matrix, score_only=True)  # BLOSUM score b/w pep seqs
        template_blosum_scores[template_pdbid] = blosum_score
    
    template_blosum_scores = dict(sorted(template_blosum_scores.items(), key=lambda item: item[1], reverse=True)) # sort by BLOSUM scores descending
    top4_templates = list(template_blosum_scores.keys())[0:4] # top 4 template PDB IDs by BLOSUM score
    
    # our sequences are prealigned so align string is constant
    ALIGNSTRING="0:0;1:1;2:2;3:3;4:4;5:5;6:6;7:7;8:8;9:9;10:10;11:11;12:12;13:13;14:14;15:15;16:16;17:17;18:18;19:19;20:20;21:21;22:22;23:23;24:24;25:25;26:26;27:27;28:28;29:29;30:30;31:31;32:32;33:33;34:34;35:35;36:36;37:37;38:38;39:39;40:40;41:41;42:42;43:43;44:44;45:45;46:46;47:47;48:48;49:49;50:50;51:51;52:52;53:53;54:54;55:55;56:56;57:57;58:58;59:59;60:60;61:61;62:62;63:63;64:64;65:65;66:66;67:67;68:68;69:69;70:70;71:71;72:72;73:73;74:74;75:75;76:76;77:77;78:78;79:79;80:80;81:81;82:82;83:83;84:84;85:85;86:86;87:87;88:88;89:89;90:90;91:91;92:92;93:93;94:94;95:95;96:96;97:97;98:98;99:99;100:100;101:101;102:102;103:103;104:104;105:105;106:106;107:107;108:108;109:109;110:110;111:111;112:112;113:113;114:114;115:115;116:116;117:117;118:118;119:119;120:120;121:121;122:122;123:123;124:124;125:125;126:126;127:127;128:128;129:129;130:130;131:131;132:132;133:133;134:134;135:135;136:136;137:137;138:138;139:139;140:140;141:141;142:142;143:143;144:144;145:145;146:146;147:147;148:148;149:149;150:150;151:151;152:152;153:153;154:154;155:155;156:156;157:157;158:158;159:159;160:160;161:161;162:162;163:163;164:164;165:165;166:166;167:167;168:168;169:169;170:170;171:171;172:172;173:173;174:174;175:175;176:176;177:177;178:178;179:179;180:180;181:181;182:182;183:183;184:184;185:185;186:186;187:187;188:188\t189\t189\t189"

    # write alignment file for AF-FT
    with open(f"{target_pdbid}/inputs/alignments.tsv", "w") as tsvfile:
        tsvfile.write("template_pdbfile\ttarget_to_template_alignstring\tidentities\ttarget_len\ttemplate_len\n")
        for template_pdbid in top4_templates:
            tsvfile.write(f"{target_pdbid}/inputs/templates/{template_pdbid.lower()}.pdb\t{ALIGNSTRING}\n")
            shutil.copy2(f'{TEMPLATE_PDB_FOLDER}/{template_pdbid.lower()}.pdb', f'{target_pdbid}/inputs/templates/')

def get_seq(filename):

    hla_seq, pep_seq = '', ''
    with open(filename, "r") as file:
        lines = file.readlines()
        hla_seq = lines[0].strip()
        pep_seq = lines[1].strip()
    
    return hla_seq, pep_seq

def main():

    for seq_file in glob.glob("input_seq/*.txt"):
        target_pdbid = seq_file.split("/")[-1].split("_")[0]
        print(f"Made folder for {seq_file}")
        
        os.system(f"mkdir -p {target_pdbid}/inputs/templates")
        hla_seq, pep_seq = get_seq(seq_file)

        allele_name = "A*02:01" # not sure if this matters

        with open(f"{target_pdbid}/inputs/target.tsv", "w") as tsvfile:
            tsvfile.write("mhc\tstart\tpeptide\ttargetid\ttarget_chainseq\ttemplates_alignfile\n")
            tsvfile.write(f"{allele_name}\t0\t{pep_seq}\t{target_pdbid}\t{hla_seq}/{pep_seq}\t{target_pdbid}/inputs/alignments.tsv\n") # the path to alignment file may need to be absolute

        get_template_pdbs(target_pdbid, pep_seq)

if __name__ == "__main__":
    
    main()
    

