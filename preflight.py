#!/usr/bin/env python3
#       Sgourakis Lab
#   Author: Wyatt Blackson
#   Modified: Ram Pantula
#   Date: July 1, 2026
#   Email: rpantula@sas.upenn.edu

"""
Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union


REPO_ROOT = Path(os.environ.get("PEPPRED_ROOT", Path(__file__).resolve().parent)).resolve()
DEFAULT_NETMHCPAN_CONTAINER_DIR = "/container/software/netmhcpan"
DEFAULT_NETMHCPAN_VERSION_DIR = "netMHCpan-4.2-linux"
DEFAULT_AFFT_PARAMS = "AFFT-HLA3DB/params/7WKJ_af_mhc_params_2351.pkl"
DEFAULT_INFERENCE_BUNDLE = "Inference/peppred.pkl"
DEFAULT_MODEL_CONFIG = "configs/peppred.yaml"
DEFAULT_PROTPARDELLE_WEIGHT = "weights/cc89pmhc_epoch8800.pth"
DEFAULT_FOLDSEEK = "tools/foldseek/bin/foldseek"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


class Preflight:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

        self.sif = env("PEPPRED_SIF", env("SIF"))
        self.scratch_host = expand(env("SCRATCH", "/scratch"))
        self.assets_host = env("PEPPRED_ASSETS_HOST")
        self.assets_container = env("PEPPRED_ASSETS_CONTAINER")
        self.model_params_host = env("PEPPRED_MODEL_PARAMS_HOST")
        self.model_params_container = env("PEPPRED_MODEL_PARAMS_CONTAINER")
        self.netmhc_host = env("PEPPRED_NETMHCPAN_HOST_DIR")
        self.netmhc_container = env(
            "PEPPRED_NETMHCPAN_CONTAINER_DIR", DEFAULT_NETMHCPAN_CONTAINER_DIR
        )

        if self.assets_host and not self.assets_container:
            self.errors.append(
                "PEPPRED_ASSETS_CONTAINER must be set when PEPPRED_ASSETS_HOST is set"
            )
        if self.assets_container and not self.assets_host:
            self.errors.append(
                "PEPPRED_ASSETS_HOST must be set when PEPPRED_ASSETS_CONTAINER is set"
            )

        if not self.model_params_host:
            if self.assets_host:
                self.model_params_host = str(expand(self.assets_host) / "model_params")
            elif self.sif:
                self.model_params_host = str(self.scratch_host / "peppred/model_params")
            else:
                self.model_params_host = str(REPO_ROOT / "protpardelle/model_params")

        if not self.model_params_container:
            if self.assets_container:
                self.model_params_container = f"{self.assets_container.rstrip('/')}/model_params"
            elif self.sif:
                self.model_params_container = "/scratch/peppred/model_params"
            else:
                self.model_params_container = self.model_params_host

        self.mappings: List[Tuple[Path, str]] = []
        self.add_mapping(REPO_ROOT, str(REPO_ROOT))
        self.add_mapping(self.scratch_host, "/scratch")
        self.add_mapping(expand(self.model_params_host), self.model_params_container)
        if self.assets_host and self.assets_container:
            self.add_mapping(expand(self.assets_host), self.assets_container)
        if self.netmhc_host:
            self.add_mapping(expand(self.netmhc_host), self.netmhc_container)

        self.mappings.sort(key=lambda item: len(item[1]), reverse=True)

    def add_mapping(self, host: Path, container: str) -> None:
        container = container.rstrip("/")
        if not container:
            return
        self.mappings.append((host, container))

    def host_path(self, path: Union[str, Path]) -> Path:
        raw = str(path)
        candidate = expand(raw)
        if not candidate.is_absolute():
            return (REPO_ROOT / candidate).resolve()
        if candidate.exists():
            return candidate

        for host, container in self.mappings:
            if raw == container:
                return host
            prefix = f"{container}/"
            if raw.startswith(prefix):
                return host / raw[len(prefix) :]

        return candidate

    def check_exists(self, label: str, path: Union[str, Path], executable: bool = False) -> None:
        host_path = self.host_path(path)
        if not host_path.exists():
            self.errors.append(f"{label} is missing: {path} (host: {host_path})")
            return
        if executable and not os.access(host_path, os.X_OK):
            self.errors.append(f"{label} is not executable: {path} (host: {host_path})")

    def host_netmhc_bin(self) -> str:
        direct = env("PEPPRED_NETMHCPAN_BIN")
        if direct:
            return direct

        if self.netmhc_host:
            netmhc_version = env("PEPPRED_NETMHCPAN_VERSION_DIR", DEFAULT_NETMHCPAN_VERSION_DIR)
            return str(
                expand(self.netmhc_host)
                / netmhc_version
                / "Linux_x86_64/bin/netMHCpan-4.2"
            )

        try:
            sys.path.insert(0, str(REPO_ROOT))
            from protpardelle.misc import constants as prot_constants
        except Exception:
            return ""

        configured = getattr(prot_constants, "netloc", "")
        container_prefixes = (
            DEFAULT_NETMHCPAN_CONTAINER_DIR,
            "/container/",
            "/opt/peppred/external/netmhcpan",
        )
        if configured.startswith(container_prefixes):
            return ""
        return configured

    def check_dir(self, label: str, path: Union[str, Path]) -> None:
        host_path = self.host_path(path)
        if not host_path.is_dir():
            self.errors.append(f"{label} directory is missing: {path} (host: {host_path})")

    def check(self, input_csv: Optional[str]) -> int:
        if input_csv:
            self.check_exists("input CSV", input_csv)

        self.check_exists("repository root", str(REPO_ROOT))

        if self.sif:
            self.check_exists("SIF", self.sif)
            if not self.netmhc_host:
                self.errors.append("PEPPRED_NETMHCPAN_HOST_DIR is required for SIF runs")
            else:
                netmhc_version = env("PEPPRED_NETMHCPAN_VERSION_DIR", DEFAULT_NETMHCPAN_VERSION_DIR)
                netmhc_bin = (
                    expand(self.netmhc_host)
                    / netmhc_version
                    / "Linux_x86_64/bin/netMHCpan-4.2"
                )
                self.check_exists("NetMHCpan binary", netmhc_bin, executable=True)
        else:
            netmhc_bin = self.host_netmhc_bin()
            if netmhc_bin and "enter path" not in netmhc_bin:
                self.check_exists("Host NetMHCpan binary", netmhc_bin, executable=True)
            else:
                self.warnings.append(
                    "PEPPRED_SIF is unset, so host-conda mode will use the NetMHCpan path written by setup.py; preflight could not validate it"
                )

        if self.assets_host:
            self.check_dir("asset bundle", self.assets_host)

        afft_params = env("PEPPRED_AFFT_PARAMS")
        if not afft_params:
            if self.assets_container:
                afft_params = f"{self.assets_container.rstrip('/')}/{DEFAULT_AFFT_PARAMS}"
            else:
                afft_params = str(REPO_ROOT / DEFAULT_AFFT_PARAMS)
        self.check_exists("AFFT model params", afft_params)

        inference_bundle = env("PEPPRED_INFERENCE_MODEL_BUNDLE")
        if not inference_bundle:
            if self.assets_container:
                inference_bundle = f"{self.assets_container.rstrip('/')}/{DEFAULT_INFERENCE_BUNDLE}"
            else:
                inference_bundle = str(REPO_ROOT / DEFAULT_INFERENCE_BUNDLE)
        self.check_exists("PepPred inference model bundle", inference_bundle)

        self.check_dir("Protpardelle model params", self.model_params_host)
        self.check_exists(
            "Protpardelle peppred config",
            f"{self.model_params_container.rstrip('/')}/{DEFAULT_MODEL_CONFIG}",
        )
        self.check_exists(
            "Protpardelle cc89pmhc weight",
            f"{self.model_params_container.rstrip('/')}/{DEFAULT_PROTPARDELLE_WEIGHT}",
        )

        foldseek = env("FOLDSEEK_BIN", env("PEPPRED_FOLDSEEK_BIN"))
        if not foldseek:
            if self.assets_container:
                foldseek = f"{self.assets_container.rstrip('/')}/{DEFAULT_FOLDSEEK}"
            elif self.sif:
                foldseek = "/scratch/peppred/tools/foldseek/bin/foldseek"
        if foldseek:
            self.check_exists("Foldseek binary", foldseek, executable=True)
        else:
            self.warnings.append(
                "Foldseek was not set explicitly; host-conda mode expects it in the protpardelle environment"
            )

        if env("NUM_MPNN_SEQS", "0") != "0":
            self.warnings.append("NUM_MPNN_SEQS is not 0; this path is not release-validated")

        scheduler = env("PEPPRED_SCHEDULER", "slurm").lower()
        scheduler_aliases = {
            "serial": "local",
            "single-node": "local",
            "single_node": "local",
            "noslurm": "local",
            "no-slurm": "local",
        }
        scheduler = scheduler_aliases.get(scheduler, scheduler)
        if scheduler not in {"slurm", "local"}:
            self.errors.append("PEPPRED_SCHEDULER must be 'slurm' or 'local'")
        elif scheduler == "local":
            self.warnings.append(
                "PEPPRED_SCHEDULER=local runs stages serially; runtime and GPU behavior depend on input size, driver compatibility, and local resources"
            )

        for warning in self.warnings:
            print(f"[preflight:warn] {warning}", file=sys.stderr)

        if self.errors:
            print("[preflight:error] release preflight failed:", file=sys.stderr)
            for error in self.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        print("[preflight] OK")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PepPred runtime inputs")
    parser.add_argument("--input", help="Input CSV that will be submitted", default=None)
    args = parser.parse_args()

    return Preflight().check(args.input)


if __name__ == "__main__":
    raise SystemExit(main())
