#!/usr/bin/env python3
# Change note (2026-06-14, wyattb/codex):
# Public-SIF/local-mode prep: keep the validated Slurm DAG as the default,
# configure runtime paths through PEPPRED_* env vars, and add an explicit serial
# local mode.
import os
import sys
import csv
import subprocess
from supertypes import supertypes
import re
import shutil
from datetime import datetime

REPO_ROOT = os.getenv("PEPPRED_ROOT", os.path.dirname(os.path.abspath(__file__)))
DEFAULT_NETMHCPAN_CONTAINER_DIR = "/container/software/netmhcpan"
DEFAULT_NETMHCPAN_VERSION_DIR = "netMHCpan-4.2-linux"
NETMHCPAN_HOST_DIR = os.getenv("PEPPRED_NETMHCPAN_HOST_DIR", "")
NETMHCPAN_CONTAINER_DIR = os.getenv("PEPPRED_NETMHCPAN_CONTAINER_DIR", DEFAULT_NETMHCPAN_CONTAINER_DIR)
NETMHCPAN_VERSION_DIR = os.getenv("PEPPRED_NETMHCPAN_VERSION_DIR", DEFAULT_NETMHCPAN_VERSION_DIR)

def configured_scheduler():
    scheduler = os.getenv("PEPPRED_SCHEDULER", "slurm").strip().lower()
    aliases = {
        "serial": "local",
        "single-node": "local",
        "single_node": "local",
        "noslurm": "local",
        "no-slurm": "local",
    }
    scheduler = aliases.get(scheduler, scheduler)
    if scheduler not in {"slurm", "local"}:
        print("[ERROR] PEPPRED_SCHEDULER must be 'slurm' or 'local'.")
        sys.exit(1)
    return scheduler

def configured_sif():
    return os.getenv("PEPPRED_SIF", os.getenv("SIF", "")).strip()

def run_preflight(input_csv):
    if os.getenv("PEPPRED_SKIP_PREFLIGHT") == "1":
        print("[preflight] skipped because PEPPRED_SKIP_PREFLIGHT=1")
        return

    preflight = os.path.join(REPO_ROOT, "preflight.py")
    subprocess.run([sys.executable, preflight, "--input", input_csv], check=True)

def slurm_export_arg(values):
    pairs = [f"{key}={value}" for key, value in values.items() if value is not None and value != ""]
    if not pairs:
        return "--export=ALL"
    return "--export=ALL," + ",".join(pairs)

def shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"

def singularity_exec_prefix(sif, repo_root, netmhc_host_dir, netmhc_container_dir, nv=False, include_assets=True):
    scratch = os.getenv("SCRATCH", "/scratch")
    parts = ["singularity", "exec", "--cleanenv", "--env", "PYTHONPATH="]
    if nv:
        parts.append("--nv")
    parts.extend([
        "--bind", f"{repo_root}:{repo_root}",
        "--bind", f"{netmhc_host_dir}:{netmhc_container_dir}",
        "--bind", f"{scratch}:/scratch",
    ])
    assets_host = os.getenv("PEPPRED_ASSETS_HOST", "")
    assets_container = os.getenv("PEPPRED_ASSETS_CONTAINER", "")
    if include_assets and assets_host and assets_container:
        parts.extend(["--bind", f"{assets_host}:{assets_container}"])
    pyrosetta_host = os.getenv("PEPPRED_PYROSETTA_HOST_PATH", "").strip()
    pyrosetta_container = os.getenv("PEPPRED_PYROSETTA_CONTAINER_PATH", pyrosetta_host).strip()
    if pyrosetta_host and pyrosetta_container:
        parts.extend(["--bind", f"{pyrosetta_host}:{pyrosetta_container}"])
    pyrosetta_path = os.getenv("PEPPRED_PYROSETTA_PATH", pyrosetta_container).strip()
    for key, value in {
        "PEPPRED_ENABLE_PYROSETTA": (os.getenv("PEPPRED_ENABLE_PYROSETTA") or "1").strip(),
        "PEPPRED_PYROSETTA_PATH": pyrosetta_path,
    }.items():
        if value:
            parts.extend(["--env", f"{key}={value}"])
    parts.append(sif)
    return " ".join(shell_quote(p) for p in parts)

def singularity_exec_cmd(sif, repo_root, netmhc_host_dir, netmhc_container_dir,
                         command, extra_env=None, include_assets=True, nv=False):
    scratch = os.getenv("SCRATCH", "/scratch")
    cmd = ["singularity", "exec", "--cleanenv", "--env", "PYTHONPATH="]
    if nv:
        cmd.append("--nv")

    cmd.extend([
        "--bind", f"{repo_root}:{repo_root}",
        "--bind", f"{netmhc_host_dir}:{netmhc_container_dir}",
        "--bind", f"{scratch}:/scratch",
    ])

    assets_host = os.getenv("PEPPRED_ASSETS_HOST", "")
    assets_container = os.getenv("PEPPRED_ASSETS_CONTAINER", "")
    if include_assets and assets_host and assets_container:
        cmd.extend(["--bind", f"{assets_host}:{assets_container}"])

    pyrosetta_host = os.getenv("PEPPRED_PYROSETTA_HOST_PATH", "").strip()
    pyrosetta_container = os.getenv("PEPPRED_PYROSETTA_CONTAINER_PATH", pyrosetta_host).strip()
    if pyrosetta_host and pyrosetta_container:
        cmd.extend(["--bind", f"{pyrosetta_host}:{pyrosetta_container}"])
    pyrosetta_path = os.getenv("PEPPRED_PYROSETTA_PATH", pyrosetta_container).strip()
    pyrosetta_enable = (os.getenv("PEPPRED_ENABLE_PYROSETTA") or "1").strip()
    if pyrosetta_enable:
        cmd.extend(["--env", f"PEPPRED_ENABLE_PYROSETTA={pyrosetta_enable}"])
    if pyrosetta_path:
        cmd.extend(["--env", f"PEPPRED_PYROSETTA_PATH={pyrosetta_path}"])

    for key, value in (extra_env or {}).items():
        if value:
            cmd.extend(["--env", f"{key}={value}"])

    cmd.append(sif)
    cmd.extend(command)
    return cmd

def run_compare_local(script, repo_root, sif, netmhc_host_dir, netmhc_container_dir):
    if not sif:
        subprocess.run([sys.executable, script], cwd=repo_root, check=True)
        return

    cmd = singularity_exec_cmd(
        sif,
        repo_root,
        netmhc_host_dir,
        netmhc_container_dir,
        ["/opt/conda/bin/conda", "run", "-n", "compare", "python", script],
    )
    subprocess.run(cmd, cwd=repo_root, check=True)

def run_fold_local(repo_root, env):
    subprocess.run(
        ["bash", os.path.join(repo_root, "AFFT-HLA3DB", "fold.sh")],
        cwd=repo_root,
        env=env,
        check=True,
    )

def resetAFFTInputs():
    input_seq_dir = os.path.join("AFFT-HLA3DB", "input_seq")
    if os.path.exists(input_seq_dir):
        shutil.rmtree(input_seq_dir)
    os.makedirs(input_seq_dir, exist_ok=True)
    print(f"Reset folder: {input_seq_dir}")

def moveAFFT():
    src = "AFFT-HLA3DB"
    dst_root = "AFFT-HLA3DB/incomplete"
    untouchable = {
        "alphafold",
        "__pycache__",
        "completed",
        "figures",
        "input_seq",
        "misc",
        "params",
        "runlogs",
        "template_pdbs",
        "template_seq",
        "incomplete",
        ".DS_Store"
    }


    movable = []
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isdir(path) and name not in untouchable:
            movable.append(name)
    if not movable:
        print("No folders to move. Skipping creation of new directory.")
        return
    os.makedirs(dst_root, exist_ok=True)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")
    dst = os.path.join(dst_root, f"input_{timestamp}")
    os.makedirs(dst, exist_ok=True)

    print(f"Moving {len(movable)} folders into: {dst}")
    for name in movable:
        src_path = os.path.join(src, name)
        shutil.move(src_path, dst)
        print(f"Moved: {name} -> {dst}")

    print("Done.")

def moveNMHC():
    src = "NMHC"
    dst_root = "NMHC/incomplete"
    untouchable = {
        "incomplete",
        ".DS_Store"
    }
    movable = []
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isdir(path) and name not in untouchable:
            movable.append(name)
    if not movable:
        print("No folders to move. Skipping creation of new directory.")
        return


    os.makedirs(dst_root, exist_ok=True)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")
    dst = os.path.join(dst_root, f"input_{timestamp}")
    os.makedirs(dst, exist_ok=True)

    print(f"Moving {len(movable)} folders into: {dst}")
    for name in movable:
        src_path = os.path.join(src, name)
        shutil.move(src_path, dst)
        print(f"Moved: {name} -> {dst}")

    print("Done.")

def extract_alleles(result_file):
    alleles = []
    pattern = re.compile(r"(A\*\d{2}:\d{2}|B\*\d{2}:\d{2}|C\*\d{2}:\d{2})")

    with open(result_file, "r") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                alleles.append(m.group(1))

    return list(dict.fromkeys(alleles))


def process_csv(input_csv):
    peptides = []  

    with open(input_csv, "r") as f:
        reader = csv.reader(f)

        for row_num, row in enumerate(reader, start=1):
            if not row or all(not c.strip() for c in row):
                print(f"[Warning] Skipping blank row {row_num}")
                continue
            first_field = re.sub(r"[\s_-]+", "_", row[0].strip().lower())
            second_field = re.sub(r"[\s_-]+", "_", row[1].strip().lower()) if len(row) > 1 else ""
            if row[0].lower().startswith("pep") or (
                first_field in {"trial_name", "trial"} and second_field == "peptide"
            ):
                print(f"[Info] Detected header row at {row_num}, skipping.")
                continue
            if len(row) < 2:
                print(f"[Error] Row {row_num} has fewer than 2 columns: {row}")
                continue

            raw_id = row[0].strip()
            clean_id = re.sub(r"[^A-Za-z0-9\-]", "_", raw_id)

            original_id = clean_id
            counter = 1
            while any(p[0] == clean_id for p in peptides):
                clean_id = f"{original_id}{counter}"  
                counter += 1

            pepID = clean_id

            sequence = row[1].strip()
            allele_list = []
            for a in row[2:]:
                a = a.strip()
                if not a:
                    continue
                if re.match(r"^[ABC]\d{2}:\d{2}", a):
                    a = a[0] + "*" + a[1:]

                allele_list.append(a)

            peptides.append((pepID, sequence, allele_list))

    if not peptides:
        print("[ERROR] No valid peptide rows found in input CSV.")
        sys.exit(1)

    return peptides

def write_alleles_file(pepID, allele_list):
    nmhc_dir = os.path.join("NMHC", pepID)
    os.makedirs(nmhc_dir, exist_ok=True)

    outfile = os.path.join(nmhc_dir, "alleles.txt")
    written = set()

    with open(outfile, "w") as out:
        for allele in allele_list:
            found = False
            query = f"HLA-{allele}"

            for stype, members in supertypes.items():
                if query in members:
                    found = True
                    for m in members:
                        formatted = m.replace("*", "")

                        if formatted not in written:
                            out.write(formatted + "\n")
                            written.add(formatted)

                    break

            if not found:
                print(f"[Warning] Allele {allele} not found in any supertype.")

def generate_netmhc_script(pepID, sequence):
    from protpardelle.misc import constants as prot_constants
    cpu_partition = os.getenv("PEPPRED_CPU_PARTITION", "normal")
    repo_root = os.getenv("PEPPRED_ROOT", REPO_ROOT)
    sif = configured_sif()
    netmhc_host_dir = os.getenv("PEPPRED_NETMHCPAN_HOST_DIR", "")
    netmhc_container_dir = os.getenv("PEPPRED_NETMHCPAN_CONTAINER_DIR", DEFAULT_NETMHCPAN_CONTAINER_DIR)
    netmhc_version_dir = os.getenv("PEPPRED_NETMHCPAN_VERSION_DIR", DEFAULT_NETMHCPAN_VERSION_DIR)
    if sif and not netmhc_host_dir:
        raise RuntimeError("Set PEPPRED_NETMHCPAN_HOST_DIR when PEPPRED_SIF/SIF is set.")
    netmhc_path = os.getenv("PEPPRED_NETMHCPAN_BIN", "")
    if not netmhc_path and not sif and netmhc_host_dir:
        netmhc_path = os.path.join(
            netmhc_host_dir,
            netmhc_version_dir,
            "Linux_x86_64",
            "bin",
            "netMHCpan-4.2",
        )
    if not netmhc_path:
        netmhc_path = prot_constants.netloc

    nmhc_dir = os.path.join("NMHC", pepID)
    script_path = os.path.join(nmhc_dir, f"run_{pepID}.sh")

    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"#SBATCH --job-name=nmhc_{pepID}\n")
        f.write(f"#SBATCH -p {cpu_partition}\n")
        f.write("#SBATCH --mem=4G\n")
        f.write(f"#SBATCH -o NMHC/{pepID}/run_{pepID}.out\n")
        f.write(f"#SBATCH -e NMHC/{pepID}/run_{pepID}.err\n")
        f.write("set -euo pipefail\n")
        f.write(f"cd {shell_quote(repo_root)}\n")
        f.write(f"touch NMHC/{pepID}/{sequence}.xls\n")
        if sif:
            prefix = singularity_exec_prefix(sif, repo_root, netmhc_host_dir, netmhc_container_dir)
            f.write(f"NETMHCPAN_CONTAINER_DIR={shell_quote(netmhc_container_dir)}\n")
            f.write(f"NETMHCPAN_VERSION_DIR={shell_quote(netmhc_version_dir)}\n")
            f.write('NMHC_HOME="${NETMHCPAN_CONTAINER_DIR}/${NETMHCPAN_VERSION_DIR}"\n')
            f.write('NMHC_PLATFORM="${NMHC_HOME}/Linux_x86_64"\n')
            f.write('NMHC_BINARY="${NMHC_PLATFORM}/bin/netMHCpan-4.2"\n')
            f.write('NMHC_TMP="${NMHC_HOME}/tmp"\n')
            f.write(
                f"cat NMHC/{pepID}/alleles.txt | while read line; do "
                f"[ -z \"$line\" ] && continue; "
                f"if ! {prefix} bash -c 'NMHOME=\"$2\" NETMHCpan=\"$3\" TMPDIR=\"$4\" "
                f"\"$5\" -a \"$1\" -p NMHC/{pepID}/{sequence}.pep -l 9 -BA' "
                f"_ \"$line\" \"$NMHC_HOME\" \"$NMHC_PLATFORM\" \"$NMHC_TMP\" \"$NMHC_BINARY\" "
                f">> NMHC/{pepID}/{sequence}.xls 2>&1; then "
                f"echo \"[WARN] NetMHCpan failed for $line; continuing.\" >> NMHC/{pepID}/{sequence}.xls; "
                f"fi; "
                f"done\n"
            )
        else:
            f.write(
                f"cat NMHC/{pepID}/alleles.txt | while read line; do "
                f"if ! {netmhc_path} -a $line -p NMHC/{pepID}/{sequence}.pep -l 9 -BA "
                f"-xlsfile NMHC/{pepID}/{sequence}.xls "
                f">> NMHC/{pepID}/{sequence}.xls 2>&1; then "
                f"echo \"[WARN] NetMHCpan failed for $line; continuing.\" >> NMHC/{pepID}/{sequence}.xls; "
                f"fi; "
                f"done\n"
            )

        f.write(
            f"awk '/{sequence}/&&/*/&&/:/ "
            f"{{bind=($NF==\"SB\"||$NF==\"WB\")?$NF:\"\"; print $2, $15, $16, bind}}' "
            f"NMHC/{pepID}/{sequence}.xls > NMHC/{pepID}/results_{sequence}.txt\n"
        )

        f.write(
            f"awk '/{sequence}/&&/*/&&/:/&&/SB|WB/ "
            f"{{bind=($NF==\"SB\"||$NF==\"WB\")?$NF:\"\"; print $2, $15, $16, bind}}' "
            f"NMHC/{pepID}/{sequence}.xls > NMHC/{pepID}/results_{sequence}_SB_WB_only.txt\n"
        )

        if sif:
            prefix = singularity_exec_prefix(sif, repo_root, netmhc_host_dir, netmhc_container_dir)
            f.write(
                f"{prefix} /opt/conda/bin/conda run -n compare python geninput.py "
                f"NMHC/{pepID}/results_{sequence}_SB_WB_only.txt NMDP.fasta {sequence} {pepID}\n"
            )
        else:
            f.write(
                f"python geninput.py NMHC/{pepID}/results_{sequence}_SB_WB_only.txt "
                f"NMDP.fasta {sequence} {pepID}\n"
            )

    os.chmod(script_path, 0o755)
    return script_path


def main():
    if len(sys.argv) != 2:
        print("Usage: python start.py input.csv")
        sys.exit(1)

    input_csv = sys.argv[1]
    scheduler = configured_scheduler()
    run_preflight(input_csv)

    run_id = os.getenv("PEPPRED_RUN_ID") or datetime.now().strftime("%Y%m%d_%H%M%S")
    os.environ["PEPPRED_RUN_ID"] = run_id
    project_name = os.getenv("PROJECT_NAME") or f"peppred_{run_id}"
    os.environ["PROJECT_NAME"] = project_name
    
    print("Resetting Inputs")
    moveAFFT()
    resetAFFTInputs()
    moveNMHC()
    os.makedirs("results", exist_ok=True)
    os.makedirs("slurm_logs", exist_ok=True)
    
    peptides = process_csv(input_csv)
    subprocess.run(["bash", "NMHC/archive.sh"], check=True)
    cpu_partition = os.getenv("PEPPRED_CPU_PARTITION", "normal")
    repo_root = os.getenv("PEPPRED_ROOT", REPO_ROOT)
    netmhc_host_dir = os.getenv("PEPPRED_NETMHCPAN_HOST_DIR", NETMHCPAN_HOST_DIR)
    netmhc_container_dir = os.getenv("PEPPRED_NETMHCPAN_CONTAINER_DIR", NETMHCPAN_CONTAINER_DIR)
    SIF = configured_sif()
    if SIF and not netmhc_host_dir:
        print("[ERROR] Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory.")
        sys.exit(1)
    
    job_ids = []
    for pepID, sequence, allele_list in peptides:
        nmhc_dir = os.path.join("NMHC", pepID)
        os.makedirs(nmhc_dir, exist_ok=True)

        with open(os.path.join(nmhc_dir, f"{sequence}.pep"), "w") as f:
            f.write(sequence + "\n")
            
        write_alleles_file(pepID, allele_list)
        script = generate_netmhc_script(pepID, sequence)

        if scheduler == "local":
            print(f"[+] Running NetMHC locally for {pepID}")
            subprocess.run(["bash", script], cwd=repo_root, check=True)
            continue

        out = subprocess.check_output([
            "sbatch",
            "-p",
            cpu_partition,
            f"--output=slurm_logs/run_{pepID}.out",
            f"--error=slurm_logs/run_{pepID}.err",
            script
        ]).decode().strip()

        job_id = out.split()[-1]
        job_ids.append(job_id)
    if scheduler == "local":
        print("[+] All local NetMHC steps completed.")
        print("[+] Running coverage locally.")
        run_compare_local("cover.py", repo_root, SIF, netmhc_host_dir, netmhc_container_dir)

        local_env = os.environ.copy()
        local_env.update({
            "SIF": SIF,
            "PEPPRED_SIF": SIF,
            "PEPPRED_ROOT": repo_root,
            "PEPPRED_NETMHCPAN_HOST_DIR": netmhc_host_dir,
            "PEPPRED_NETMHCPAN_CONTAINER_DIR": netmhc_container_dir,
            "PEPPRED_NETMHCPAN_VERSION_DIR": NETMHCPAN_VERSION_DIR,
            "PEPPRED_SCHEDULER": "local",
            "PEPPRED_RUN_ID": run_id,
            "PROJECT_NAME": os.environ["PROJECT_NAME"],
            "PEPPRED_ENABLE_PYROSETTA": os.getenv("PEPPRED_ENABLE_PYROSETTA") or "1",
            "PEPPRED_PYROSETTA_HOST_PATH": os.getenv("PEPPRED_PYROSETTA_HOST_PATH", ""),
            "PEPPRED_PYROSETTA_CONTAINER_PATH": os.getenv("PEPPRED_PYROSETTA_CONTAINER_PATH", ""),
            "PEPPRED_PYROSETTA_PATH": os.getenv("PEPPRED_PYROSETTA_PATH", ""),
        })
        print("[+] Running AFFT/Protpardelle/inference locally.")
        run_fold_local(repo_root, local_env)
        print("[+] Local PepPred pipeline completed.")
        return

    print(f"[+] Submitted {len(job_ids)} NetMHC jobs.")


    netmhc_dependency = ":".join(job_ids)
    alphafold_env_container = os.getenv("ALPHAFOLD_ENV_CONTAINER", "/opt/conda/envs/alphafold")
    alphafold_python_container = os.getenv("ALPHAFOLD_PYTHON_CONTAINER", "/opt/conda/envs/alphafold/bin/python")
    project_name = os.getenv("PROJECT_NAME", f"peppred_{run_id}")
    driver_partition = os.getenv("PEPPRED_DRIVER_PARTITION", cpu_partition)
    gpu_partition = os.getenv("PEPPRED_GPU_PARTITION", "gpu")
    gpu_gres = os.getenv("PEPPRED_GPU_GRES", "gpu:1")
    gpu_constraint = os.getenv("PEPPRED_GPU_CONSTRAINT", "")
    assets_host = os.getenv("PEPPRED_ASSETS_HOST", "")
    assets_container = os.getenv("PEPPRED_ASSETS_CONTAINER", "")
    model_params_host = os.getenv("PEPPRED_MODEL_PARAMS_HOST", "")
    model_params_container = os.getenv("PEPPRED_MODEL_PARAMS_CONTAINER", "")
    afft_params = os.getenv("PEPPRED_AFFT_PARAMS", "")
    inference_model_bundle = os.getenv("PEPPRED_INFERENCE_MODEL_BUNDLE", "")
    foldseek_bin = os.getenv("FOLDSEEK_BIN", os.getenv("PEPPRED_FOLDSEEK_BIN", ""))

    if SIF:
        prefix = singularity_exec_prefix(SIF, repo_root, netmhc_host_dir, netmhc_container_dir)
        cover_wrap = f"{prefix} /opt/conda/bin/conda run -n compare python cover.py"
    else:
        cover_wrap = "python3 cover.py"

    cover_job_info = subprocess.check_output([
        "sbatch",
        f"--dependency=afterok:{netmhc_dependency}",
        "-p",
        cpu_partition,
        "--output=slurm_logs/cover.out",
        "--error=slurm_logs/cover.err",
        f"--wrap={cover_wrap}"
    ]).decode().strip()

    cover_job = cover_job_info.split()[-1]
    print(f"[+] Submitted coverage job with ID {cover_job}")

    fold_job_info = subprocess.check_output([
        "sbatch",
        f"--dependency=afterok:{cover_job}",
        "-p",
        driver_partition,
        "--output=slurm_logs/fold.out",
        "--error=slurm_logs/fold.err",
        slurm_export_arg({
            "SIF": SIF,
            "PEPPRED_SIF": SIF,
            "PEPPRED_ROOT": repo_root,
            "PEPPRED_NETMHCPAN_HOST_DIR": netmhc_host_dir,
            "PEPPRED_NETMHCPAN_CONTAINER_DIR": netmhc_container_dir,
            "PEPPRED_NETMHCPAN_VERSION_DIR": NETMHCPAN_VERSION_DIR,
            "PEPPRED_ASSETS_HOST": assets_host,
            "PEPPRED_ASSETS_CONTAINER": assets_container,
            "PEPPRED_MODEL_PARAMS_HOST": model_params_host,
            "PEPPRED_MODEL_PARAMS_CONTAINER": model_params_container,
            "PEPPRED_ENABLE_PYROSETTA": os.getenv("PEPPRED_ENABLE_PYROSETTA") or "1",
            "PEPPRED_PYROSETTA_HOST_PATH": os.getenv("PEPPRED_PYROSETTA_HOST_PATH", ""),
            "PEPPRED_PYROSETTA_CONTAINER_PATH": os.getenv("PEPPRED_PYROSETTA_CONTAINER_PATH", ""),
            "PEPPRED_PYROSETTA_PATH": os.getenv("PEPPRED_PYROSETTA_PATH", ""),
            "PEPPRED_AFFT_PARAMS": afft_params,
            "PEPPRED_INFERENCE_MODEL_BUNDLE": inference_model_bundle,
            "FOLDSEEK_BIN": foldseek_bin,
            "ALPHAFOLD_ENV_CONTAINER": alphafold_env_container,
            "ALPHAFOLD_PYTHON_CONTAINER": alphafold_python_container,
            "PROJECT_NAME": project_name,
            "PEPPRED_CPU_PARTITION": cpu_partition,
            "PEPPRED_DRIVER_PARTITION": driver_partition,
            "PEPPRED_GPU_PARTITION": gpu_partition,
            "PEPPRED_GPU_GRES": gpu_gres,
            "PEPPRED_GPU_CONSTRAINT": gpu_constraint,
            "PEPPRED_RUN_ID": run_id,
            "PEPPRED_SCHEDULER": scheduler,
        }),
        os.path.join(repo_root, "AFFT-HLA3DB", "fold.sh")
    ]).decode().strip()

    fold_job = fold_job_info.split()[-1]
    print(f"[+] Submitted fold job with ID {fold_job}")

if __name__ == "__main__":
    main()
