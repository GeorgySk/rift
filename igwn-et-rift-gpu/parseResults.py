import json
import glob
import os
import re
from collections import defaultdict
from math import log10, floor

import numpy as np


def round_to_significant_digits(value, digits):
    if not isinstance(value, (int, float)):
        return value
    if value == 0:
        return 0
    else:
        return round(value, digits - int(floor(log10(abs(value)))) - 1)

def process_value(value, significant_digits):
    print(value)
    if isinstance(value, dict):
        return {k: process_value(v, significant_digits) for k, v in value.items()}
    elif isinstance(value, (int, float)):
        return round_to_significant_digits(value, significant_digits)
    else:
        return value

def merge_dicts(dicts, significant_digits=5):
    """Merge multiple dictionaries with identical structure, creating lists at the leaf nodes."""
    def merge_values(val_list, significant_digits=5):
        if all(isinstance(v, dict) for v in val_list):
            # If all values are dictionaries, merge them recursively
            merged = {}
            keys = set(k for d in val_list for k in d)
            for key in keys:
                merged[key] = merge_values([d[key] for d in val_list if key in d])
            return merged
        else:
            # If the values are not dictionaries, return them as a list
            return [round_to_significant_digits(v, significant_digits) for v in val_list]

    return merge_values(dicts, significant_digits)

def parse_results(baseWDir, significant_digits=5):
    scores = []
    ncopies = int(os.environ['NCOPIES'])

    # Each copy generates an output file
    for i in range(ncopies):
        likelihood_estimations_count = max((int(m.group(1))
                                            for d in os.listdir(
            '/bmk/build/et/rift/.travis/ILE-GPU-Paper/demos/test_workflow_batch_gpu_lowlatency')
                                            if (m := re.match(r'iteration_(\d+)_ile', d))))
        execution_time = next((int(m.group(1))
                               for m in (re.search(r"completed action '.*' in (\d+) seconds", line)
                                         for line in open(f"{os.getcwd()}/proc_{i + 1}/out_{i + 1}.log"))
                               if m))
        likelihoods_per_sec = likelihood_estimations_count / execution_time
        scores.append(likelihoods_per_sec)

    avg_total = np.mean(scores)
    wl_stats = {'avg': avg_total,
                'median': np.median(scores),
                'min': np.min(scores),
                'max': np.max(scores),
                'count': ncopies}
    resJSON = {'wl-scores': {'pe': round_to_significant_digits(avg_total * ncopies, significant_digits)},
               'wl-stats': process_value(wl_stats, significant_digits)}
    output_file = os.path.join(baseWDir, 'parser_output.json')
    with open(output_file, 'w') as f:
        json.dump(resJSON, f, indent=4)

# Example usage:
# parse_results('/path/to/baseWDir', significant_digits=5)

if __name__ == "__main__":
    import sys
    parse_results(sys.argv[1], significant_digits=5)
