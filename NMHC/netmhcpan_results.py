#       Sgourakis Lab
#   Author: Sagar Gupta
#   Date: June 2, 2022
#   Email: sagarg@sas.upenn.edu

# import required libraries
import csv
import os
from collections import defaultdict

def read_netmhcpan_results(peptide, filename):

    os.system(f"cat {filename} | "+"awk '{print $1}' > "+f"{peptide}.temp")
    with open(f"{peptide}.temp", "r") as file:
        lines = file.readlines()
        lines = [l.strip() for l in lines]
    alleles = lines

    os.system(f"cat {filename} | "+"awk '{print $2}' > "+f"{peptide}.temp")
    with open(f"{peptide}.temp", "r") as file:
        lines = file.readlines()
        lines = [l.strip() for l in lines]
    percent_rank_ba = lines

    os.system(f"cat {filename} | "+"awk '{print $3}' > "+f"{peptide}.temp")
    with open(f"{peptide}.temp", "r") as file:
        lines = file.readlines()
        lines = [l.strip() for l in lines]
    binding_aff_estimate = lines

    os.system(f"cat {filename} | "+"awk '{print $4}' > "+f"{peptide}.temp")
    with open(f"{peptide}.temp", "r") as file:
        lines = file.readlines()
        lines = [l.strip() for l in lines]
    sb_wb = lines

    os.system(f"rm {peptide}.temp")

    results = defaultdict(list)
    for index, value in enumerate(alleles):
        results[value] = [percent_rank_ba[index], binding_aff_estimate[index], sb_wb[index]]

    return results

def main():

    # Get peptide
    with open("QYNPIRTTF.pep", 'r') as txtfile:
        peptides = txtfile.readlines()
        peptides = [p.strip() for p in peptides]

    # Convert results txtfile to csvfile
    for peptide in peptides:
        with open(f"{peptide}_results.csv", "w") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['peptide', 'allele', 'percent_rank_ba', 'binding_aff_estimate', 'sb_wb'])
            for peptide in peptides:
                filename = f"results_{peptide}.txt"
                results = read_netmhcpan_results(peptide, filename)
                for key, element in results.items():
                    row = [peptide]
                    row.append(key)
                    for e in element:
                        if e == '':
                            row.append('NB')
                        else:
                            row.append(e)
                    writer.writerow(row)

    # Get HLA Frequencies (via Andrew McShan)
    hla_freq = {}
    with open("all_hla_freq_global.csv", "r", encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        for line in reader:
            allele = line[0][0:5]+"*"+line[0][5:]
            hla_freq[allele] = float(line[1])

    global_frequency_cutoff = 0.1 # percentage (default)

    # writes a txtfile with alleles matching the above criteria
    for peptide in peptides:
        allele_count = 0
        print(peptide)
        with open(f"{peptide}_sb_wb_common_alleles.csv", "w") as sb_wb_txt:
            with open(f"{peptide}_results.csv", "r") as csvfile:
                reader = csv.reader(csvfile)
                next(reader)
                for line in reader:
                    print(line)
                    if line[4] == 'SB' or line[4] =='WB':
                        if hla_freq[line[1]] >= global_frequency_cutoff:
                            sb_wb_txt.write(line[1]+","+line[2]+","+line[3]+","+line[4]+"\n")
                            allele_count += 1

        print(f"{allele_count} alleles are SB to {peptide} and ≥{global_frequency_cutoff}% in global population")

if __name__ == "__main__":

    main()
