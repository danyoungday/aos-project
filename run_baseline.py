import json
import numpy as np

from problems.fio import FioProblem


def get_baseline(config):
    defaults = {
        "max_sectors_kb": 1280,
        "nr_requests": 127,
        "read_ahead_kb": 1,
        "nomerges": 0,
        "scheduler": 0,
        "rq_affinity": 1
    }

    problem = FioProblem(config)
    out = {}
    x = np.array(list(defaults.values()))
    print(problem.evaluate(x.reshape(1, -1), out=out))
    print(out)


def main():
    with open("results/rand_write/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        print(json.dumps(config, indent=4))
    get_baseline(config["problem_params"])


if __name__ == "__main__":
    main()