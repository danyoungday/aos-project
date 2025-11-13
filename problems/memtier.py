"""
Runs the memtier benchmark.
"""
import json
import subprocess
import tempfile

from problems.problem import THPProblem


class MemtierProblem(THPProblem):
    """
    Runs the memtier benchmark.
    """
    def __init__(self, config: dict):
        # Keep track of memtier params for our benchmarking
        self.memtier_params = config["memtier_params"]

        super().__init__(sys_params=config["sys_params"], objectives=config["objectives"])

    def run_benchmark(self) -> dict[str, float]:
        """
        Runs the memtier benchmark and returns the parsed JSON output.
        """
        # Restart redis server to clear all data
        subprocess.run(
            ["sudo", "systemctl", "restart", "redis-server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        # Save results to a JSON tempfile
        metrics = {}
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as tmpfile:
            # Construct the command with our memtier_params. This is a little inefficient but whatever
            command = [
                "memtier_benchmark",
                "--protocol=redis",
                f"--json-out-file={tmpfile.name}"
            ]
            for param, value in self.memtier_params.items():
                command.append(f"--{param}={str(value)}")

            # Run the command
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            # Write the output to metrics dict. Since we want to maximize throughput, multiply it by -1
            with open(tmpfile.name, "r", encoding="utf-8") as t:
                output = json.load(t)
                metrics = {
                    "throughput": -1 * output["ALL STATS"]["Sets"]["Ops/sec"],
                    "latency": output["ALL STATS"]["Sets"]["Percentile Latencies"]["p99.90"]
                }

        # Measure Redis memory usage
        result = subprocess.run(["redis-cli", "info", "memory"], capture_output=True, text=True, check=True)
        # Take output and convert to a dict by splitting on newlines and colons
        info_lines = result.stdout.splitlines()
        info_dict = {}
        for line in info_lines:
            if ":" in line:
                key, value = line.split(":")
                info_dict[key.strip()] = value.strip()
        metrics["fragmentation"] = float(info_dict.get("mem_fragmentation_ratio"))

        return metrics
