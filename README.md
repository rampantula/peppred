## PepPred ##
PepPred is a structural similarity prediction program that utilizes sequence information of 9mer peptide antigens and predicted binder HLA alleles to generate
structural comparisons of the peptide backbone conformations between two alleles presenting a shared antigen. 

## Program Dependencies ##
This program assumes users to have a few pre insalled dependencies 
- Anaconda: https://www.anaconda.com/download
- Rosetta: https://docs.rosettacommons.org/demos/latest/tutorials/install_build/install_build 
- TensorFlow (Reccomend using conda create a Tensor specific conda libarary): https://www.tensorflow.org/install/pip
- NetMHCpan4.1: https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ 


## SETUP ##
1. Set up Protpardelle using README.md inside Protpardelle subfolder. You will need to create the Protpardelle conda environment and download the protpardelle specific 
model parameters using the instructions within the README.md inside Protpardelle subfolder.

2. Download custom parameters from: and utilize README.md inside parameters director to install each file in its given location

3. Create necessary conda environments for PepPred pipeline
	conda env create -f alphafold.yml
	conda env create -f conda.yml
	conda env create -f train.yml
	
	If you are running into issues with your conda environment for alphafold try using this command:
     conda activate alphafold
     pip install --upgrade "jax==0.4.1" "jaxlib==0.4.1+cuda11.cudnn86" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

4.  Activate compare environment
	conda activate compare

5. Access setup.py and replace path directories with paths to each dependency, then run setup.py
	python setup.py
     
## USAGE ##
1. Fill input.csv as the following:
	Trial_Name, peptide sequence, X*XX:XX, Y*YY:Y, ...

	Be cautious to only run 9mer peptides
	Do not utilize special characters (with the exception of "_") or spaces in "Trial_Name"
	
	A test case is provided to you as default
	
2. Activate conda environment
	source {yourpath}/anaconda3/bin/activate
	or conda activate
	then,
	conda activate compare

3. Run start.py by using the command
	python start.py <input.csv>

	Replace <input.csv> with a path to any csv formatted with the information necessary to run PepPred

4. Use "squeue -u <username>" to monitor progress of jobs. 

