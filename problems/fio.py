"""
Runs the fio benchmark.
"""
import json
import subprocess
import tempfile

from problems.problem import SysfsProblem


class FioProblem(SysfsProblem):
    """
    Runs the fio benchmark.
    """
    def __init__(self, config: dict):
        # Keep track of memtier params for our benchmarking
        self.fio_params = config["fio_params"]

        super().__init__(sys_params=config["sys_params"], objectives=config["objectives"])

    def reset_system(self):
        pass

    def run_benchmark(self) -> dict[str, float]:
        """
        Runs the fio benchmark and returns the parsed JSON output.
        """

        # Save results to a JSON tempfile
        metrics = {}
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as tmpfile:
            # Construct the command with our memtier_params. This is a little inefficient but whatever
            command = [
                "fio",
                "--name=evo",
                "--filename=/dev/nvme0n1",
                "--output-format=json",
                f"--output={tmpfile.name}"
            ]
            for param in self.fio_params:
                command.append(f"--{param}")

            # Run the command
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            # Write the output to metrics dict. Since we want to maximize throughput, multiply it by -1
            with open(tmpfile.name, "r", encoding="utf-8") as t:
                output = json.load(t)
                results = output["jobs"][0]
                metrics = {
                    "read_throughput": -1 * results["read"]["bw"],
                    # "write_throughput": -1 * results["write"]["bw"],
                    "read_latency": results["read"]["clat_ns"]["percentile"]["99.990000"],
                    # "write_latency": results["write"]["clat_ns"]["percentile"]["99.990000"]
                }

        return metrics
