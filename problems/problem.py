"""
Abstract class used for THP problems
"""
import numpy as np

from pymoo.core.problem import ElementwiseProblem

class SysfsProblem(ElementwiseProblem):
    """
    Runs our sysfs evaluation script.
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
            n_obj=len(objectives),
            xl=np.array(xl),
            xu=np.array(xu)
        )

    def set_sysfs_params(self, params: dict[str, int]):
        """
        Sets the kernel params by writing to them.
        We manually parse the parameters here. The enabled parameter is binary but represented as a string.
        The others are floats that need to be converted to ints then strings.
        """
        for param, value in params.items():
            if param.endswith("read_ahead_kb"):
                val = int(value)
                if val == 0:
                    value_str = "0"
                else:
                    value_str = str(2 ** (val + 6))
            else:
                value_str = str(int(value))
            with open(param, "w", encoding="utf-8") as f:
                f.write(value_str)

    def reset_system(self):
        """
        Resets the system before running a benchmark.
        """
        raise NotImplementedError("Subclasses must implement reset_system method.")

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
        self.set_sysfs_params(params)

        # Run the benchmark
        metrics = self.run_benchmark()

        if "verbose" in kwargs and kwargs["verbose"] == 1:
            print(params)
            print(metrics)

        out["F"] = np.array([metrics[obj] for obj in self.objectives])