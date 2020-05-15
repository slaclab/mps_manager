#!/usr/bin/env python
#
# Script for changing thresholds for MPS analog devices
#

from mps_config import MPSConfig, models, runtime
from mps_names import MpsName
from runtime import *
from sqlalchemy import func
import sys
import argparse
import time 
import os
import re
import subprocess
import yaml
import epics
from epics import PV
from argparse import RawTextHelpFormatter
from threshold_manager import ThresholdManager
from mps_manager import DatabaseReader
from mps_manager_protocol import MpsManagerThresholdRequest
from pprint import *
  
#
# build a table/dictionary from the command line parameters
#
def build_threshold_table(t):
  # fist check the parameters
  for l in t:
    [table_name, t_index, integrator, t_type, value] = l

    table_name = table_name.lower()
    t_index = t_index.lower()
    integrator = integrator.lower()
    t_type = t_type.lower()

    if (table_name != 'lc2' and
        table_name != 'alt' and
        table_name != 'lc1' and
        table_name != 'idl'):
      print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
          format(table_name, integrator, t_index)
      print 'ERROR: invalid table "{0}" (parameter={})'.format(l[0], l)
      return False

    if (not (((integrator.startswith('i')) and
              len(integrator)==2 and
              int(integrator[1])>=0 and
              int(integrator[1])<=3) or
             integrator=='x' or
             integrator=='y' or
             integrator=='tmit')):
      print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
          format(table_name, integrator, t_index)
      print 'ERROR: invalid integrator "{}" (parameter={})'.format(integrator, l)
      return False

    if (not (t_index.startswith('t'))):
      print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
          format(table_name, integrator, t_index)
      print 'ERROR: invalid threshold "{}", must start with t (parameter={})'.format(t_index, l)
      return False
    else:
      if (len(t_index) != 2):
        print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
            format(table_name, integrator, t_index)
        print 'ERROR: invalid threshold "{}", must be in t<index> format (parameter={})'.format(t_index, l)
        return False
      else:
        if (table_name == 'lc2' or table_name == 'alt'):
          if (int(t_index[1])<0 or int(t_index[1])>7):
            print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
                format(table_name, integrator, t_index)
            print 'ERROR: invalid threshold index "{}", must be between 0 and 7 (parameter={})'.\
                format(t_index[1], l)
            return False
        else:
          if (int(t_index[1]) != 0):
            print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
                format(table_name, integrator, t_index)
            print 'ERROR: invalid threshold index "{}", must be 0'.\
                format(t_index[1], l)
            return False

    if (not (t_type == 'lolo' or
             t_type == 'hihi')):
      print 'ERROR: invalid thresholds for table {}, integrator {}, threshold {}'.\
          format(table_name, integrator, t_index)
      print 'ERROR: invalid threshold type "{}", must be lolo or hihi (parameter={})'.\
          format(t_type, l)
      return False

  # build a dictionary with the input parameters
  table = {}
  for l in t:
    [table_name, t_index, integrator, t_type, value] = l

    table_name = table_name.lower()
    t_index = t_index.lower()
    integrator = integrator.lower()
    t_type = t_type.lower()

    # rename fields to match database
    if (integrator == 'x'):
      integrator = 'i0'

    if (integrator == 'y'):
      integrator = 'i1'

    if (integrator == 'tmit'):
      integrator = 'i2'

    if (t_type == 'lolo'):
      t_type = 'l'

    if (t_type == 'hihi'):
      t_type = 'h'

    if (not table_name in table.keys()):
      table[table_name]={}

    if (not t_index in table[table_name].keys()):
      table[table_name][t_index]={}

    if (not integrator in table[table_name][t_index].keys()):
      table[table_name][t_index][integrator]={}

    if (not t_type in table[table_name][t_index][integrator].keys()):
      table[table_name][t_index][integrator][t_type]=value

  message = MpsManagerThresholdRequest()
  for thr_table, v in table.items(): # lc1, lc2, idl or aln
    for thr_index, v2 in v.items(): # T0 through T7
      thr_index_index = int(thr_index[1])
      for thr_integrator, v3 in v2.items(): # I0 through I4
        thr_int_index = int(thr_integrator[1])
        for thr_type, thr_value in v3.items(): # LOLO or HIHI
          thr_type_index = 0 if thr_type == 'l' else  1
          if thr_table == 'lc1':
            message.lc1_active[thr_type_index][thr_int_index] = 1
            message.lc1_value[thr_type_index][thr_int_index] = float(thr_value)
          elif thr_table == 'idl':
            message.idl_active[thr_type_index][thr_int_index] = 1
            message.idl_value[thr_type_index][thr_int_index] = float(thr_value)
          elif thr_table == 'lc2':
            message.lc2_active[thr_type_index * 8 + thr_index_index][thr_int_index] = 1
            message.lc2_value[thr_type_index * 8 + thr_index_index][thr_int_index] = float(thr_value)
          elif thr_table == 'alt':
            message.alt_active[thr_type_index * 8 + thr_index_index][thr_int_index] = 1
            message.alt_value[thr_type_index * 8 + thr_index_index][thr_int_index] = float(thr_value)
    
  return message

def is_analog(dbr, dev_id):
  analog_devices = dbr.session.query(models.AnalogDevice).filter(models.AnalogDevice.id==dev_id).all()
  if (len(analog_devices)==1):
    return True
  else:
    digital_devices = dbr.session.query(models.DigitalDevice).filter(models.DigitalDevice.id==dev_id).all()
    if (len(digital_devices)==0):
      print('ERROR: Device not found (invalid device id {0})'.format(dev_id))
    return False

def check_device(dbr, dev_id, dev_name):
  if (dev_id < 0):
    try:
      d = dbr.session.query(models.Device).filter(models.Device.name==dev_name).one()
      dev_id = d.id
    except Exception as e:
        print(str(e))
        print('ERROR: Cannot find device with name "{0}" in config database'.format(dev_name))
        return None, None

  if (is_analog(dbr, dev_id)):
    try:
      rt_d = dbr.rt_session.query(runtime.Device).filter(runtime.Device.id==dev_id).one()
    except Exception as e:
      print(str(e))

      print('ERROR: Cannot find device with id="{0}" in runtime database'.format(dev_id))
      return None, None

    try:
      d = dbr.session.query(models.Device).filter(models.Device.id==dev_id).one()
    except:
      print('ERROR: Cannot find device with id="{0}" in config database'.format(dev_id))
      return None, None

    if (rt_d.mpsdb_name != d.name):
      print('ERROR: Device names do not match in config ({0}) and runtime databases ({1})'.\
          format(d.name, rt_d.mpsdb_name))
      return None, None

    is_bpm = False
    if (d.device_type.name == 'BPMS'):
        is_bpm = True

  else:
    print('ERROR: Cannot set threshold for digital device')
    return None, None

  return rt_d, is_bpm  

#=== MAIN ==================================================================================

parser = argparse.ArgumentParser(description='Change thresholds for analog devices',
                                 formatter_class=RawTextHelpFormatter)
parser.add_argument('database', metavar='db', type=file, nargs=1, 
                    help='database file name (e.g. mps_gun.db, where the runtime database is named mps_gun_runtime.db')
parser.add_argument('--reason', metavar='reason', type=str, nargs=1, help='reason for the threshold change', required=True)
parser.add_argument('-t', nargs=5, action='append', 
                    help='<table threshold_index integrator threshold_type value>\nwhere:\n'+
                         '  table: lc2, alt, lc1 or idl\n'
                         '  threshold_index: T0 through T7 (must be T0 for LCLS-I and IDLE thresholds)\n'+
                         '  integrator_index: I0, I1, I2, I3, X, Y or TMIT\n'+
                         '  threshold_type: LOLO or HIHI\n'+
                         '  value: new threshold value\n\nTables:\n'+
                         '  lc2: LCLS-II thresholds\n'+
                         '  alt: alternative LCLS-II thresholds\n'+
                         '  lc1: LCLS-I thresholds, only T0 available\n'+
                         '  idl: no beam thresholds, only T0 available\n')

parser.add_argument('--disable', action='store_true', default=False, help="Disable specified thresholds")

group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. BPM1B)', type=str, nargs='?', help='device name as found in the MPS database')
parser.add_argument('-f', action='store_true', default=False,
                    dest='force_write', help='Change thresholds even if PVs are not writable (changes only the database)')
parser.add_argument('-i', action='store_true', default=False,
                    dest='ignore_pv', help='Change thresholds even if PVs are not accessible on the network (changes only the database)')

proc = subprocess.Popen('whoami', stdout=subprocess.PIPE)
user = proc.stdout.readline().rstrip()

args = parser.parse_args()

device_id = -1
if (args.device_id):
  device_id = args.device_id

device_name = None
if (args.device_name):
  device_name =args.device_name

reason = args.reason[0]

db_file_name = args.database[0].name
rt_file_name = '{}/{}_runtime.db'.format(os.path.dirname(db_file_name),
                                         os.path.basename(db_file_name).\
                                           split('.')[0])

dbr = DatabaseReader(db_file_name, rt_file_name)

tm = ThresholdManager(dbr.session, dbr.rt_session, dbr.mps_names)
message = build_threshold_table(args.t)

rt_d, is_bpm = check_device(dbr, device_id, device_name)

if (rt_d):
  log, error_pvs, status = tm.change_thresholds(rt_d, user, reason, is_bpm,
                                                message.lc1_active, message.lc1_value,
                                                message.idl_active, message.idl_value,
                                                message.lc2_active, message.lc2_value,
                                                message.alt_active, message.alt_value,
                                                args.disable)
  if (not status):
    exit(1)
