#! /usr/bin/env bash
ls  /home/georgy/ET/rift/.travis/ILE-GPU-Paper/demos/test_workflow_batch_gpu_lowlatency/*.composite  1>&2 
/usr/local/bin/util_CleanILE.py /home/georgy/ET/rift/.travis/ILE-GPU-Paper/demos/test_workflow_batch_gpu_lowlatency/*.composite 
ret_value=$?
if [ $ret_value -eq 0 ]; then
  exit 0
else
  cat  /home/georgy/ET/rift/.travis/ILE-GPU-Paper/demos/test_workflow_batch_gpu_lowlatency/*.composite
fi
