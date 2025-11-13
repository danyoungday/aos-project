"""
Abstract class used for THP problems
"""
import subprocess
import time

import numpy as np

from pymoo.core.problem import ElementwiseProblem

class THPProblem(ElementwiseProblem):
    """
    Runs our THP evaluation script.
    """
    def __init__(self, sys_params: dict[str, tuple[int, int]], objectives: list[str]):
        
        self.objectives = objectives

        # Set up bounds and use super constructor
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

    def run_benchmark(self) -> dict[str, float]:
        """
        To be implemented: runs the benchmark and returns a dict of metrics. Make sure the keys match those in
        self.objectives!!
        """
        raise NotImplementedError("Subclasses must implement run_benchmark method.")

    def _evaluate(self, x, out, *args, **kwargs):

        # Reset caches, memory, etc. before evaluation
        self.reset_system()

        # Convert x to param dict
        params = dict(zip(self.params, x))
        self.set_kernel_params(params)

        # Run the memtier benchmark
        metrics = self.run_benchmark()
        
        if kwargs["verbose"] == 1:
            print(params)
            print(metrics)

        out["F"] = np.array([metrics[obj] for obj in self.objectives])