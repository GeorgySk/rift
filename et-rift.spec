HEPWL_BMKEXE=et-rift-bmk.sh

HEPWL_BMKOPTS=""

HEPWL_BMKDIR=et-rift
HEPWL_BMKDESCRIPTION="ET RIFT benchmark (2025)"
HEPWL_BMKOS=gitlab-registry.cern.ch/linuxsupport/alma9-base:20230801-1
HEPWL_BMKUSEGPU=1
HEPWL_DOCKERIMAGENAME=et-rift-bmk
HEPWL_DOCKERIMAGETAG=ci-v0.1 # NB: use ci-vX.Y for tests (can be rebuilt) and vX.Y for production (cannot be rebuilt)
HEPWL_CVMFSREPOS=NONE
HEPWL_BUILDARCH="x86_64"
