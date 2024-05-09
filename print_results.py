"""
This script summarizes the results from generate_run.py.
"""

import json
import re
import numpy as np
import sys

def report_results(results_fpath):
    # Count outcomes
    counts = {
        # project-level
        "error": 0,
        "other": 0,
        "preparation": 0,
        "couldnt-parse": 0,
        "run": 0,
        # test-level
        "test_successes": [],
        "test_failures": [],
        "test_errors": [],
    }
    with open(results_fpath) as f:
        for line in f:
            data = json.loads(line)
            if "error" in data:
                counts["error"] += 1
            elif "evosuite-test" in data:
                counts["run"] += 1
                out = data["evosuite-test"]["stdout"]
                seen = set()
                unique_summary_lines = []
                for l in out.splitlines():
                    if "Tests run:" in l:
                        if l not in seen:
                            seen.add(l)
                            unique_summary_lines.append(l)
                try:
                    tests_run = sum(int(re.search(r"Tests run: (\d+)", l).group(1)) for l in unique_summary_lines)
                    tests_failed = sum(int(re.search(r"Failures: (\d+)", l).group(1)) for l in unique_summary_lines)
                    tests_errored = sum(int(re.search(r"Errors: (\d+)", l).group(1)) for l in unique_summary_lines)
                    tests_skipped = sum(int(re.search(r"Skipped: (\d+)", l).group(1)) for l in unique_summary_lines)
                    tests_succeeded = tests_run - tests_failed - tests_errored - tests_skipped
                    counts["test_successes"].append(tests_succeeded)
                    counts["test_failures"].append(tests_failed)
                    counts["test_errors"].append(tests_errored)
                except Exception:
                    counts["couldnt-parse"] += 1
            elif "evosuite-generate" in data or "evosuite-compile" in data:
                counts["preparation"] += 1
            else:
                counts["other"] += 1

    # Print summary
    print("Project outcomes:")
    print("\n".join(f"{k} = {v}" for k, v in counts.items() if not k.startswith("test")))
    if any(v for k, v in counts.items() if k.startswith("test")):
        for k in counts:
            if k.startswith("test"):
                counts[k] = round(np.average(counts[k]), 1)
        
        print("Test outcomes (mean):")
        print("\n".join(f"{k} = {v}" for k, v in counts.items() if k.startswith("test")))

if __name__ == "__main__":
    report_results(sys.argv[1])
