"""
A super simple dummy script for the project proposal.
"""
import json
from pathlib import Path
import pickle

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling

from problems.fio import FioProblem


def main():
    """
    Main experiment logic.
    """
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        print(json.dumps(config, indent=4))

    save_dir = Path(config["evolution_params"]["save_dir"])
    print("Saving to:", save_dir)
    if save_dir.exists():
        raise FileExistsError(f"Save directory {save_dir} already exists!")

    save_dir.mkdir(exist_ok=True, parents=True)

    with open(save_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    problem = FioProblem(config["problem_params"])

    # Create initial population with seeding + random
    initial_pop = problem.create_initial_pop()
    # Random sample the rest up to pop size if needed
    pop_size = config["evolution_params"]["population_size"]
    if initial_pop.shape[0] < pop_size:
        sampling = FloatRandomSampling()
        X_rand = sampling(problem, pop_size - initial_pop.shape[0]).get("X")
        initial_pop = np.concatenate((initial_pop, X_rand), axis=0)
    assert initial_pop.shape[0] == pop_size

    algorithm = NSGA2(
        sampling=initial_pop,
        pop_size=config["evolution_params"]["population_size"],
        n_offsprings=config["evolution_params"]["population_size"],
        eliminate_duplicates=True,
        crossover=SBX(eta=5),
        mutation=PM(eta=10)
    )

    algorithm.setup(
        problem,
        termination=("n_gen", config["evolution_params"]["n_generations"]),
        seed=42,
        save_history=True,
        verbose=True
    )

    while algorithm.has_next():
        algorithm.next()
        res = algorithm.result()
        with open(save_dir / "fullresults.pkl", "wb") as f:
            pickle.dump(res, f)


if __name__ == "__main__":
    main()