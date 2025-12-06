import json
import matplotlib.pyplot as plt
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


def compare_paretos():
    df = pd.read_csv("results/eval_all.csv")
    exp_names = ["seq_read", "rand_read", "seq_write", "rand_write"]
    labels = {
        "seq_read": "Sequential Read",
        "rand_read": "Random Read",
        "seq_write": "Sequential Write",
        "rand_write": "Random Write"
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()

    for eval_col, ax in zip(exp_names, axes):
        subset = df[df["eval"] == eval_col]
        for params_col in exp_names: 
            if params_col != eval_col:
                pareto_subset = subset[subset["params"] == params_col]
                ax.scatter(pareto_subset["throughput"] / 1000, pareto_subset["latency"] / 1e6, label=labels[params_col] + " Solutions")
            else:
                results_df = pd.read_csv(f"results/{eval_col}/results.csv")
                final_pareto_df = results_df[(results_df["is_pareto"] == 1.0) & (results_df["gen"] == results_df["gen"].max())]
                ax.scatter(final_pareto_df["throughput"], final_pareto_df["latency"], label=labels[params_col] + " Solutions", marker="x", s=100)
        # ax.legend()
        ax.set_title(f"Evaluation on {labels[eval_col]}")
    
    axes[0].set_xlim(0, 1100)
    axes[1].set_xlim(0, 1100)
    axes[0].set_ylim(0, 5)
    axes[1].set_ylim(0, 5)

    axes[2].set_xlim(0, 700)
    axes[3].set_xlim(0, 700)
    axes[2].set_ylim(0, 90)
    axes[3].set_ylim(0, 90)

    # Create legend outside the plots with common labels from "labels"
    # Make sure the legend is all points not x's
    labels = [label + " Solutions" for label in labels.values()]
    points = [plt.Line2D([0], [0], color="w", marker="o", markerfacecolor=f"C{i}") for i in range(len(labels))]
    fig.legend(points, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.05))
    
    fig.supxlabel("Throughput (MB/s)")
    fig.supylabel("Latency (ms)")
    fig.suptitle("Evaluation of Pareto Fronts Across Workloads")
    # plt.savefig("results/pareto_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()

def create_table():
    results_dirs = [
        "results/seq_read",
        "results/rand_read",
        "results/seq_write",
        "results/rand_write"
    ]
    eval_all_df = pd.read_csv("results/eval_all.csv")

    for param_path in results_dirs:
        results_df = pd.read_csv(param_path + "/results.csv")
        print("Param: " + param_path.split("/")[-1])
        row = []
        for eval_path in results_dirs:
            if eval_path == param_path:
                row.append(f"{results_df['latency'].min():.2f}")
            else:
                params = param_path.split("/")[-1]
                evals = eval_path.split("/")[-1]
                subset = eval_all_df[(eval_all_df["params"] == params) & (eval_all_df["eval"] == evals)]
                row.append(f"{(subset['latency'].min() / 1e6) :.2f}")
        print(" & ".join(row))

if __name__ == "__main__":
    # eval_on_all()
    # compare_paretos()
    create_table()

