#!/bin/bash
echo 'Starting MpsManager...'

go_python_file=$TOOLS/script/go_python2.7.13.bash
if [ ! -f $go_python_file ]; then
    echo "No $go_python_file found, using system defined python settings"
else
    . $TOOLS/script/go_python2.7.13.bash
fi

export PYTHONPATH=$PHYSICS_TOP/mps_database:$PYTHON_PATH

export PYTHONPATH=$PHYSICS_TOP/mps_manager:$PYTHON_PATH

current_db=$PHYSICS_TOP/mps_configuration/current

log_file=$PHYSICS_DATA/mps_manager/mps_manager-`date +"%m-%d-%Y_%H:%M:%S"`.log

files=`ls -1 $current_db/mps_config*.db | grep -v runtime | wc -l`

if [ $files != '1' ]; then
  echo '============================================================'
  echo ' ERROR: found '$files' database files in '$current_db
  echo '        there must be only one mps_config-<release>.db file'
  echo '        MpsManager cannot run.'
  echo '============================================================'
fi

db_file=`ls -1 $current_db/mps_config*.db | grep -v runtime`

$PHYSICS_TOP/mps_manager/mps_manager.py --log-file $log_file --hb SIOC:SYS0:ML00:AO500 $db_file &
