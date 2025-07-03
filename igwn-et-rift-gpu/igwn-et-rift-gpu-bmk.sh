#!/bin/bash

# Copyright 2019-2022 CERN. See the COPYRIGHT file at the top-level
# directory of this distribution. For licensing information, see the
# COPYING file at the top-level directory of this distribution.

#set -x # enable debug printouts

#set -e # immediate exit on error

# Function doOne must be defined in each benchmark
# Input argument $1: process index (between 1 and $NCOPIES)
# Return value: please return 0 if this workload copy was successful, 1 otherwise
# The following variables are guaranteed to be defined and exported: NCOPIES, NTHREADS, NEVENTS_THREAD, EXTRA_ARGS, BMKDIR, DEBUG
# The function is started in process-specific working directory <basewdir>/proc_$1:
# please store here the individual log files for each of the NCOPIES processes
function doOne(){
  if [ "$1" == "" ] || [ "$2" != "" ]; then echo "[doOne] ERROR! Invalid arguments '$@' to doOne"; return 1; fi
  echo "[doOne ($1)] $(date) starting in $(pwd)"
  echo "[doOne ($1)] $(date) workDir is $workDir"
  workDir=$(pwd)

  # Choose whether to run benchmarks on CPU only, GPU only or both
  # Based on EXTRA_ARGS passed via '--extra-args'
  echo "[doOne ($1)] $(date) EXTRA_ARGS='$EXTRA_ARGS'"
  status=0
  cpuorgpus=
  for arg in $EXTRA_ARGS; do
    if [ "${arg}" == "--cpu" ] && [ "${cpuorgpus}" == "" ]; then
      cpuorgpus=${arg}
    elif [ "${arg}" == "--gpu" ] && [ "${cpuorgpus}" == "" ]; then
      cpuorgpus=${arg}
    elif [ "${arg}" == "--both" ] && [ "${cpuorgpus}" == "" ]; then
      cpuorgpus=${arg}
    else
      echo "[doOne ($1)] $(date) ERROR! Invalid argument '${arg}'"
      echo "[doOne ($1)] $(date) Usage: --extra-args '[--cpu|--gpu|-both]'"
      status=1; echo "[doOne ($1)] $(date) completed (status=${status})"; return ${status}
    fi
  done
  if [ "${cpuorgpus}" == "" ]; then
    cpuorgpus="--cpu" # default is the CPU benchmark
    echo "[doOne ($1)] $(date) No --cpu or --gpu was specified in EXTRA_ARGS: run default cpuorgpus='--cpu'"
  else
    echo "[doOne ($1)] $(date) From EXTRA_ARGS: cpuorgpus='${cpuorgpus}'"
  fi
  # Setup WL copy
  SECONDS=0
  source /bmk/build/et/rift/.travis/test-run.sh \
    >> ${workDir}/out_$1.log 2> >(tee -a ${workDir}/out_$1.log >&2)
  status=${?}
  duration=$SECONDS
  echo "[doOne ($1)] $(date) current status=$status: completed action '${action}' in ${duration} seconds"
  echo "[doOne ($1)] $(date) current status=$status: completed action '${action}' in ${duration} seconds" | tee -a ${workDir}/out_$1.log
  echo "[doOne ($1)] $(date) completed (status=${status})"
  # Return 0 if this workload copy was successful, 1 otherwise
  return ${status}
}

# Optional function usage_detailed may be defined in each benchmark
# Input arguments: none
# Return value: none
function usage_detailed(){
  echo "Optional EXTRA_ARGS: [--cpu|--gpu]"
  echo "  --cpu   : (CPU or GPU?)     run only the benchmarks on CPU (1 or more copies)"
  echo "  --gpu   : (CPU or GPU?)     run only the CUDA benchmarks on GPU (1 copy)"
  echo "DEFAULT is '--cpu "
  echo ""
  echo "If you start the benchmark by mistake and need to kill all associated processes, run the following command:"
  echo "  kill \$(ps -ef | egrep '(igwn-et-rift-gpu-bmk.sh|job.py|check.exe)' | grep -v grep | awk '{print \$2}')"
}

# Default values for NCOPIES, NTHREADS, NEVENTS_THREAD must be set in each benchmark
#NCOPIES=$(nproc)
NCOPIES=1
NTHREADS=1 # cannot be changed by user input (single-threaded single-process WL)
NEVENTS_THREAD=1 # multiplier for a process-dependent predefined number of events

# Source the common benchmark driver
if [ -f $(dirname $0)/bmk-driver.sh ]; then
  . $(dirname $0)/bmk-driver.sh
else
  . $(dirname $0)/../../../common/bmk-driver.sh
fi
