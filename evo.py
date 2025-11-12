"""
A super simple dummy script for the project proposal.
"""
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pickle
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

        # Make sure transparent huge pages are enabled
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
        """
        for param, value in params.items():
            with open(param, "w", encoding="utf-8") as f:
                f.write(str(value))


    def _evaluate(self, x, out, *args, **kwargs):

        # Reset caches, memory, etc. before evaluation
        self.reset_system()

        params = dict(zip(self.params, map(int, x)))
        self.set_kernel_params(params)

        result = subprocess.run([
            "/usr/bin/time",
            "-f", "{\"time\": %e, \"res\": %M, \"maj\": %F, \"min\": %R}",
            "-a", "taskset", "-c", "0",
            "sysbench", "--verbosity=0", "memory",
            "--memory_block_size=64M", "--memory_total_size=4096GB", "--memory_access_mode=rnd",
            "run"
        ], check=True, capture_output=True, text=True)

        metrics = json.loads(result.stderr)

        out["F"] = np.array([metrics["time"], metrics["res"]])


def main():
    """
    Main experiment logic.
    """
    daemon = "/sys/kernel/mm/transparent_hugepage/khugepaged/"
    sys_params={
        daemon + "scan_sleep_millisecs": [100, 20000],
        daemon + "pages_to_scan": [1, 8192],
        daemon + "max_ptes_none": [0, 1024],
        daemon + "max_ptes_swap": [0, 1024],
        daemon + "max_ptes_shared": [0, 1024]
    }
    problem = THPProblem(
        sys_params=sys_params
    )

    algorithm = NSGA2(
        pop_size=20,
        n_offsprings=20,
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

    save_dir = Path("results/moreparams")

    with open(save_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump(sys_params, f, indent=4)

    np.save(save_dir / "X.npy", res.X)
    np.save(save_dir / "F.npy", res.F)

    with open(save_dir / "fullresults.pkl", "wb") as f:
        pickle.dump(res, f)


if __name__ == "__main__":
    main()
