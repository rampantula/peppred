#!/bin/bash
touch NMHC/{pepID}/{sequence}.xls
cat NMHC/{pepID}/alleles.txt | while read line; do {netmhc_path} -a $line -p NMHC/{pepID}/{sequence}.pep -l 9 -BA -xlsfile NMHC/{pepID}/{sequence}.xls >> NMHC/{pepID}/{sequence}.xls; done
awk '/{sequence}/&&/*/&&/:/ {print $2, $15, $16, $18}' NMHC/{pepID}/{sequence}.xls > NMHC/{pepID}/results_{sequence}.txt
awk '/{sequence}/&&/*/&&/:/&&/SB|WB/ {print $2, $15, $16, $18}' NMHC/VVGAVGVGK.xls > NMHC/{pepID}/results_{sequence}_SB_WB_only.txt
python geninput.py NMHC/{pepID}/results_{sequence}_SB_WB_only.txt NMDP.fasta {sequence} {pepID}

