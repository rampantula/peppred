#!/bin/bash
touch NMHC/LLRC15/MPLKHYLLL.xls
cat NMHC/LLRC15/alleles.txt | while read line; do /mnt/isilon/sgourakis_lab_storage/main/netMHCpan-4.1/netMHCpan -a $line -p NMHC/LLRC15/MPLKHYLLL.pep -l 9 -BA -xlsfile NMHC/LLRC15/MPLKHYLLL.xls >> NMHC/LLRC15/MPLKHYLLL.xls; done
awk '/MPLKHYLLL/&&/*/&&/:/ {print $2, $15, $16, $18}' NMHC/LLRC15/MPLKHYLLL.xls > NMHC/LLRC15/results_MPLKHYLLL.txt
awk '/MPLKHYLLL/&&/*/&&/:/&&/SB|WB/ {print $2, $15, $16, $18}' NMHC/LLRC15/MPLKHYLLL.xls > NMHC/LLRC15/results_MPLKHYLLL_SB_WB_only.txt
python geninput.py NMHC/LLRC15/results_MPLKHYLLL_SB_WB_only.txt NMDP.fasta MPLKHYLLL LLRC15
