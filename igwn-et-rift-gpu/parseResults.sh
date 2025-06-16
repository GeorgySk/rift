# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level
# directory of this distribution. For licensing information, see the
# COPYING file at the top-level directory of this distribution.

parseResultsDir=$(cd $(dirname ${BASH_SOURCE}); pwd) # needed to locate parseResults.py

# Function parseResults must be defined in each benchmark (or in a separate file parseResults.sh)
# The following variables are guaranteed to be defined and exported: NCOPIES, NTHREADS, NEVENTS_THREAD, BMKDIR, DEBUG, APP
# Logfiles have been stored in process-specific working directories <basewdir>/proc_<1...NCOPIES>
# The function is started in the base working directory <basewdir>:
# please store here the overall json summary file for all NCOPIES processes combined
function parseResults(){
  echo "[parseResults] current directory: $(pwd)"
  # #-----------------------
  # Parse results (bash)
  #-----------------------
  echo "[parseResults] python parser starting"
  # Call the Python script
  python3 ${parseResultsDir}/parseResults.py "$baseWDir"
  shstatus=$?
  [ "$shstatus" != "0" ] && return $shstatus

  #-----------------------
  # Return status
  #-----------------------
  return $shstatus
}
