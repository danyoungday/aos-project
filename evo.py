"""
A super simple dummy script for the project proposal.
"""
import json
import subprocess

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.termination import get_termination


class THPProblem(ElementwiseProblem):
    """
    Runs our THP evaluation script.
    """
    def __init__(self, eval_path: str, sys_params: list[str]):
        super().__init__(
            n_var=2,
            n_obj=2,
            xl=np.array([1, 10]),
            xu=np.array([4096, 10000])
        )
        self.eval_path = eval_path
        self.sys_params = sys_params

    def _evaluate(self, x, out, *args, **kwargs):
        command = [self.eval_path, str(int(x[1])), str(int(x[0])), "temp.json"]
        subprocess.run(command, check=True)
        with open("temp.json", "r", encoding="utf-8") as f:
            result = json.load(f)
            out["F"] = np.array([-1 * result["result"]["throughput_MBps"], result["thp_count"]])


def main():
    problem = THPProblem(
        eval_path="./eval.sh",
        sys_params=["pages_to_scan", "scan_sleep_millisecs"]
    )

    algorithm = NSGA2(
        pop_size=40,
        n_offsprings=40,
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

    np.save("X.npy", res.X)
    np.save("F.npy", res.F)


if __name__ == "__main__":
    main()
