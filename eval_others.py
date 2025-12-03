import json
import numpy as np
import pandas as pd
from tqdm import tqdm

from problems.fio import FioProblem


def eval_params(x: np.ndarray, config: dict) -> np.ndarray:
    """
    Evaluates a set of parameters on a given config
    """
    problem = FioProblem(config)
    return problem.evaluate(x.reshape(1, -1))


def eval_on_all():
    """
    Evaluates every set of pareto parameters on every problem and saves to CSV.
    """
    results_dirs = [
        "results/rand_write",
        "results/rand_read",
        "results/seq_write",
        "results/seq_read"
    ]
    rows = []
    for param_path in tqdm(results_dirs):

        results_df = pd.read_csv(param_path + "/results.csv")
        final_pareto_df = results_df[(results_df["is_pareto"] == 1.0) & (results_df["gen"] == results_df["gen"].max())]

        for eval_path in tqdm(results_dirs, leave=False, desc=f"Eval {param_path}"):

            with open(eval_path + "/config.json", "r", encoding="utf-8") as f:
                config = json.load(f)["problem_params"]
            problem = FioProblem(config)

            for _, row in tqdm(final_pareto_df.iterrows(), total=len(final_pareto_df), leave=False, desc="Params"):
                # Construct x from row
                x = []
                for col in config["sys_params"]:
                    colname = col.split("/")[-1]
                    x.append(row[colname])
                x = np.array(x)

                # Evaluate on eval problem
                result = problem.evaluate(x.reshape(1, -1))[0]
                rows.append({
                    "params": param_path.split("/")[-1],
                    "eval": eval_path.split("/")[-1],
                    "throughput": -1 * result[0], 
                    "latency": result[1]
                })

    df = pd.DataFrame(rows)
    df.to_csv("results/eval_all.csv", index=False)


def create_all_eval_table():
    """
    Create a table with the min, mean, and max latency and throughput for each combination of params and eval.
    """
    df = pd.read_csv("results/eval_all.csv")

    grouped = df.groupby(["params", "eval"])
    mins = grouped.min()
    maxes = grouped.max()

    rows = []
    for params in df["params"].unique():
        row = f"{params} & "
        results = []
        for evals in df["eval"].unique():
            results.append(f"{maxes.loc[(params, evals), 'throughput']:.0f} / {mins.loc[(params, evals), 'latency']:.0f}")
        row += " & ".join(results)
        rows.append(row)

    string = "\n".join(rows)
    print(string)

if __name__ == "__main__":
    # eval_on_all()
    create_all_eval_table()

