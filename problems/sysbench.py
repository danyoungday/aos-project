"""
The sysbench problem as a pymoo problem.
"""
import subprocess

import json

from problems.problem import THPProblem

class SysbenchProblem(THPProblem):
    """
    Runs our sysbench evaluation
    """
    def run_benchmark(self) -> dict[str, float]:
        """
        Runs the sysbench memory benchmark and returns the parsed JSON output.
        """
        result = subprocess.run([
            "/usr/bin/time",
            "-f", "{\"time\": %e, \"res\": %M, \"maj\": %F, \"min\": %R}",
            "-a", "taskset", "-c", "0",
            "sysbench", "--verbosity=0", "memory",
            "--memory_block_size=64M", "--memory_total_size=4096G", "--memory_access_mode=rnd",
            "run"
        ], check=True, capture_output=True, text=True)
        metrics = json.loads(result.stderr)
        return metrics