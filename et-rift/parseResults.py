# Based on https://gitlab.cern.ch/hep-benchmarks/hep-workloads/-/blob/master/igwn/pe/igwn-pe/parseResults.py
import json
import os
import re

import numpy as np

scores = []
ncopies = int(os.environ['NCOPIES'])

# Each copy generates an output file
for i in range(ncopies):
    likelihood_estimations_count = max((int(m.group(1))
                                        for d in os.listdir('/bmk/build/et/rift/.travis/ILE-GPU-Paper/demos/test_workflow_batch_gpu_lowlatency')
                                        if (m := re.match(r'iteration_(\d+)_ile', d))))
    execution_time = next((int(m.group(1))
                           for m in (re.search(r"completed action '.*' in (\d+) seconds", line)
                                     for line in open(f"{os.getcwd()}/proc_1/out_{i + 1}.log"))
                           if m))
    likelihoods_per_sec = likelihood_estimations_count / execution_time
    scores.append(likelihoods_per_sec)

avg_total = np.mean(scores)
output_json = {'wl-scores': {'pe': avg_total * ncopies},
               'wl-stats': {'avg': avg_total,
                            'median': np.median(scores),
                            'min': np.min(scores),
                            'max': np.max(scores),
                            'count': ncopies}}
print(json.dumps(output_json))

# basewdir = os.environ['baseWDir']
#
# with open(f"{basewdir}/parser_output.json", "w") as output_file:
#     json.dump(output_json, output_file)
