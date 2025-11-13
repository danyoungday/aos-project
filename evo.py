"""
A super simple dummy script for the project proposal.
"""
import json
from pathlib import Path
import pickle

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.termination import get_termination

from problems.memtier import MemtierProblem


def main():
    """
    Main experiment logic.
    """
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        print(json.dumps(config, indent=4))

    save_dir = Path("results/bigtest")
    print("Saving to:", save_dir)
    if save_dir.exists():
        raise FileExistsError(f"Save directory {save_dir} already exists!")

    save_dir.mkdir(exist_ok=True, parents=True)

    with open(save_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    problem = MemtierProblem(**config)

    algorithm = NSGA2(
        pop_size=5,
        n_offsprings=5,
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

    with open(save_dir / "fullresults.pkl", "wb") as f:
        pickle.dump(res, f)


if __name__ == "__main__":
    main()