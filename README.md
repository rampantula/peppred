##AFFT-HLA3DB + Similarity Predictor ##

## SETUP ##
1. extract protpardelle.zip and set up Protpardelle using instructions inside folder (set up protpardelle environment)
2. Download parameters from: and follow instructions
3. Create necessary conda environments from .ymls (compare & train)
4. Open setup.py and fill in required variables & run python setup.py

     
## USAGE ##
1. Fill input.csv as the following:
	NAME, peptide sequence, X*XX:XX, Y*YY:Y, ...

2. Activate conda
	source /mnt/isilon/sgourakis_lab_storage/anaconda3/bin/activate

3. Run start.py by using the command
	python start.py <input.csv>

4. Use "squeue -u <username>" to monitor progress of your Alphafold jobs

##DEBUG##
If you are running into issues with your conda environment for alphafold try using this command:

     conda activate alphafold
     pip install --upgrade "jax==0.4.1" "jaxlib==0.4.1+cuda11.cudnn86" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

