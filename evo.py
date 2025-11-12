"""
A super simple dummy script for the project proposal.
"""
import json
from pathlib import Path
import pickle
import re
import subprocess
import tempfile
import time

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.termination import get_termination


class THPProblem(ElementwiseProblem):
    """
    Runs our THP evaluation script.
    """
    def __init__(self, sys_params: dict[str, tuple[int, int]]):

        xl = []
        xu = []
        self.params = []
        for param, bounds in sys_params.items():
            xl.append(bounds[0])
            xu.append(bounds[1])
            self.params.append(param)

        super().__init__(
            n_var=len(sys_params),
            n_obj=2,
            xl=np.array(xl),
            xu=np.array(xu)
        )

        # Enable THPs
        with open("/sys/kernel/mm/transparent_hugepage/enabled", "w", encoding="utf-8") as f:
            f.write("always")

    def reset_system(self):
        """
        Runs sudo sync to flush file system buffers, then drops caches and compacts memory.
        """
        subprocess.run(["sudo", "sync"], check=True)
        with open("/proc/sys/vm/drop_caches", "w", encoding="utf-8") as f:
            f.write("3")
        with open("/proc/sys/vm/compact_memory", "w", encoding="utf-8") as f:
            f.write("1")
        time.sleep(1)

    def set_kernel_params(self, params: dict[str, int]):
        """
        Sets the kernel params by writing to them.
        We manually parse the parameters here. The enabled parameter is binary but represented as a string.
        The others are floats that need to be converted to ints then strings.
        """
        for param, value in params.items():
            if param.endswith("defrag"):
                value_str = "always" if value > 0.5 else "defer"
            else:
                value_str = str(int(value))
            with open(param, "w", encoding="utf-8") as f:
                f.write(value_str)

    def run_sysbench_eval(self) -> dict[str, float]:
        """
        Runs the sysbench memory benchmark and returns the parsed JSON output.
        """
        result = subprocess.run([
            "/usr/bin/time",
            "-f", "{\"time\": %e, \"res\": %M, \"maj\": %F, \"min\": %R}",
            "-a", "taskset", "-c", "0",
            "sysbench", "--verbosity=0", "memory",
            "--memory_block_size=64M", "--memory_total_size=4096G", "--memory_access_mode=rnd",
            "run"
        ], check=True, capture_output=True, text=True)
        metrics = json.loads(result.stderr)
        return metrics

    def run_memtier_eval(self) -> dict[str, float]:
        """
        Runs the memtier benchmark and returns the parsed JSON output.
        """

        # Resets Redis
        subprocess.run(["redis-cli", "flushall"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Save results to a JSON tempfile
        metrics = {}
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as tmpfile:
            subprocess.run([
                "memtier_benchmark",
                "--protocol=redis",
                "--threads=1",
                "--clients=8",
                "--test-time=60",
                f"--json-out-file={tmpfile.name}"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            with open(tmpfile.name, "r", encoding="utf-8") as t:
                output = json.load(t)
                metrics = {
                    "throughput": output["ALL STATS"]["Sets"]["Ops/sec"],
                    "latency": output["ALL STATS"]["Sets"]["Max Latency"]
                }

        # Measure Redis memory usage
        result = subprocess.run(["redis-cli", "info", "memory"], capture_output=True, text=True, check=True)

        # Take output and convert to a dict by splitting on newlines and colons
        info_lines = result.stdout.splitlines()
        info_dict = {}
        for line in info_lines:
            if ":" in line:
                key, value = line.split(":")
                info_dict[key.strip()] = value.strip()
        metrics["fragmentation"] = float(info_dict.get("mem_fragmentation_ratio"))

        return metrics

    def _evaluate(self, x, out, *args, **kwargs):

        # Reset caches, memory, etc. before evaluation
        self.reset_system()

        # Convert x to param dict
        params = dict(zip(self.params, x))
        self.set_kernel_params(params)

        # Run the memtier benchmark
        metrics = self.run_memtier_eval()

        out["F"] = np.array([-1 * metrics["throughput"], metrics["fragmentation"]])


def main():
    """
    Main experiment logic.
    """
    daemon = "/sys/kernel/mm/transparent_hugepage/khugepaged/"
    sys_params={
        "/sys/kernel/mm/transparent_hugepage/defrag": [0, 1],
        daemon + "scan_sleep_millisecs": [100, 20000],
        daemon + "pages_to_scan": [1, 8192],
        daemon + "max_ptes_none": [0, 512],
        daemon + "max_ptes_swap": [0, 512],
        daemon + "max_ptes_shared": [0, 512],
    }
    problem = THPProblem(
        sys_params=sys_params
    )

    algorithm = NSGA2(
        pop_size=10,
        n_offsprings=10,
        eliminate_duplicates=True
    )

    termination = get_termination("n_gen", 10)

    res = minimize(
        problem,
        algorithm,
        termination,
        seed=42,
        save_history=True,
        verbose=True
    )

    save_dir = Path("results/redis")
    save_dir.mkdir(exist_ok=True, parents=True)

    with open(save_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump(sys_params, f, indent=4)

    np.save(save_dir / "X.npy", res.X)
    np.save(save_dir / "F.npy", res.F)

    with open(save_dir / "fullresults.pkl", "wb") as f:
        pickle.dump(res, f)


if __name__ == "__main__":
    main()
