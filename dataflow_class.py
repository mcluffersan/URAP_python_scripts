import os
import json
import subprocess
from pathlib import Path

class DataFlow:
    def __init__(self, json_path: str):

        self.json_path = Path(json_path)
        if not self.json_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.json_path}")

        with open(self.json_path, "r") as f:
            self.config = json.load(f)

        self.cosima_file = self.config["cosima_file"]
        self.geometry_file = self.config["geometry_file"]
        self.revan_cfg = self.config["revan_output"]
        self.mimrec_cfg = self.config["mimrec_output"]
        self.energy_cut = self.config.get("energy_cut", [10, 2000])
        self.max_events = self.config.get("max_events", 100000)

        self.dir = self.json_path.parent
        self.output_dir = self.dir / "results"
        os.makedirs(self.output_dir, exist_ok=True)

        # Keep local copies in /home/linusb/algo
        algo_dir = Path("/home/linusb/algo")
        for fpath in [self.cosima_file, self.geometry_file, self.revan_cfg, self.mimrec_cfg]:
            fpath = Path(fpath)
            dest = algo_dir / fpath.name
            if fpath.exists() and not dest.exists():
                os.system(f"cp {fpath} {dest}")

    def run_command(self, cmd):
        print(f">>> {' '.join(cmd)}\n")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {process.returncode}")

    def run_simulation(self):
        print("==== Step 1: Simulation ====")
        # DO NOT pass -n <max_events> → causes crash
        self.run_command(["cosima", self.cosima_file])

    def run_reconstruction(self):
        print("==== Step 2: Reconstruction ====")
        base = os.path.splitext(self.cosima_file)[0]
        sim_file = base + ".inc1.id1.sim.gz"

        if not os.path.exists(sim_file):
            print(f"Warning: Simulation file '{sim_file}' not found!")

        self.run_command([
            "revan",
            "-c", self.revan_cfg,
            "-g", self.geometry_file,
            "-f", sim_file,
            "-a", "-n"
        ])

    def run_spectrum(self):
        print("==== Step 3: Spectrum Creation ====")
        base = os.path.splitext(self.cosima_file)[0]
        tra_file = base + ".inc1.id1.tra.gz"
        output_spectrum = self.output_dir / "spectrum.C"

        if not os.path.exists(tra_file):
            print(f"Warning: Tracking file '{tra_file}' not found!")

        self.run_command([
            "mimrec", "-c", self.mimrec_cfg,
            "-g", self.geometry_file,
            "-f", tra_file,
            "-s", "-o", str(output_spectrum)
        ])

        # 🆕 Automatically call ROOT to generate the plot
        print("==== Generating ROOT spectrum plot ====")
        root_cmd = [
            "root",
            "-l",
            "-b",
            "-q",
            f"spectrum_plot.C(\"{output_spectrum}\")"   # You need spectrum_plot.C macro in working dir
        ]
        try:
            self.run_command(root_cmd)
        except Exception as e:
            print(f"⚠ ROOT plotting failed: {e}")

    def organize_results(self):
        base_prefix = os.path.splitext(os.path.basename(self.cosima_file))[0]
        safe_ext = (".sim.gz", ".tra.gz", ".root", ".C", ".txt", ".dat")

        for file in os.listdir('.'):
            if file.startswith(base_prefix) and file.endswith(safe_ext):
                os.rename(file, self.output_dir / file)

    def run_full_pipeline(self):
        os.chdir(self.dir)
        self.run_simulation()
        self.run_reconstruction()
        self.run_spectrum()
        self.organize_results()
