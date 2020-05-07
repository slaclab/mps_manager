#!/bin/bash
echo 'Starting MpsManager...'

log_file=$PHYSICS_DATA/mps_manager/mps_manager-`date +"%m-%d-%Y_%H:%M:%S"`.log
if [ $1 = "dev" ]; then
    export TOP=/afs/slac/u/ld/jmock/Cosylab/workspace/
    current_db=$TOP/mps_database/
    log_file=$PHYSICS_DATA/mps_manager/mps_manager-dev-`date +"%m-%d-%Y_%H:%M:%S"`.log
else
    export TOP=$PHYSICS_TOP
    current_db=$TOP/mps_configuration/cu
    log_file=$PHYSICS_DATA/mps_manager/mps_manager-cu-`date +"%m-%d-%Y_%H:%M:%S"`.log
fi
    echo 'Log File:' $log_file

go_python_file=$TOOLS/script/go_python2.7.13-x86_64.bash

if [ `hostname` == 'lcls-dev1' ]; then
    echo "Host: `hostname`, using virtual python environment"
    if [ `hostname` == 'lcls-dev1' ]; then
	pushd $TOP/mps_database
	. ./setup.sh
	popd
	# Gets python 2.7.9 ...
	. $EPICS_SETUP/go_epics_3.15.5-1.0.bash
    fi
else
    . $EPICS_SETUP/fixed-epics-setup.bash
    . $EPICS_SETUP/epicsenv-7.0.2-1.1.bash
    . $TOOLS/script/go_python2.7.13-x86_64.bash
fi

export PYTHONPATH=$TOP/mps_database/:$PYTHONPATH
export PYTHONPATH=$TOP/mps_database/tools:$PYTHONPATH
export PYTHONPATH=$TOP/mps_manager:$PYTHONPATH

files=`ls -1 $current_db/mps_config*.db | grep -v runtime | wc -l`

if [ $files != '1' ]; then
  echo '============================================================'
  echo ' ERROR: found '$files' database files in '$current_db
  echo '        there must be only one mps_config-<release>.db file'
  echo '        MpsManager cannot run.'
  echo '============================================================'
fi

db_file=`ls -1 $current_db/mps_config*.db | grep -v runtime`

echo "Using this runtime database: " $db_file

$TOP/mps_manager/mps_manager.py --log-file $log_file --hb SIOC:SYS0:ML07:AO002 $db_file
