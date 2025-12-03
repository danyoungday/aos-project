"""
Script to get baseline performance for fio.
"""
import random

import json
import numpy as np
import pandas as pd
from pymoo.operators.sampling.rnd import FloatRandomSampling

from problems.fio import FioProblem


def run_default(config) -> np.ndarray:
    """
    Get default param performance on given config
    """
    defaults = {
        "max_sectors_kb": 1280,
        "nr_requests": 127,
        "read_ahead_kb": 1,
        "nomerges": 0,
        "scheduler": 0,
        "rq_affinity": 1
    }
    problem = FioProblem(config)
    x = np.array(list(defaults.values()))
    return problem.evaluate(x.reshape(1, -1))


def get_default_baselines():
    """
    Runs default parameters on all configs and saves to CSV.
    """
    config_paths = [
        "results/rand_write/config.json",
        "results/big_fio/config.json",
        "results/seq_write2/config.json",
        "results/seq_read/config.json"
    ]
    rows = []
    for path in config_paths:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            print(f"Config path: {path}")
            results = run_default(config["problem_params"])[0]
            rows.append({"exp": path.split("/")[1], "throughput": -1 * results[0], "latency": results[1]})

    df = pd.DataFrame(rows)
    df.to_csv("results/default_baselines.csv", index=False)


def random_search(config, n_iter=500) -> np.ndarray:
    """
    Performs a random search on the given config for n_iter iterations.
    """
    sampler = FloatRandomSampling()
    problem = FioProblem(config)
    X = sampler(problem, n_iter).get("X")
    results = problem.evaluate(X)
    return results


def get_random_baselines():
    """
    Runs random search on all configs and saves to CSV.
    """
    random.seed(42)
    np.random.seed(42)

    config_paths = [
        # "results/rand_write/config.json",
        "results/rand_read/config.json",
        "results/seq_write/config.json",
        "results/seq_read/config.json"
    ]
    for path in config_paths:
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            print(f"Config path: {path}")
            results = random_search(config["problem_params"], n_iter=500)
            for r in results:
                rows.append({"exp": path.split("/")[1], "throughput": -1 * r[0], "latency": r[1]})

        # Save here for checkpointing purposes
        df = pd.DataFrame(rows)
        df.to_csv(f"results/{path.split('/')[1]}_baselines.csv", index=False)


if __name__ == "__main__":
    get_random_baselines()