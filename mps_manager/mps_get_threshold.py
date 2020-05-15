#!/usr/bin/env python
#
# Script for reading current thresholds for MPS analog devices
#

import sys
import argparse
import time 
import os
import re
import subprocess
from tabulate import tabulate

from argparse import RawTextHelpFormatter
from mps_manager_protocol import *
from threshold_manager_client import ThresholdManagerClient
import socket
from ctypes import *
from struct import *

def print_thresholds(title, values, active, only_active):
  print('== {}'.format(title))
  t_count = len(values) / 2

  no_active_thresholds = True
  for t_index in range(0, t_count):
    if only_active:
      skip = True
      for i in range(0,4):
        if active[t_index][i] == 1:
          skip = False
        if active[t_index+t_count][i] == 1:
          skip = False
      if skip:
        continue

    no_active_thresholds = False
    header = ['T{}'.format(t_index), 'I0', 'I1', 'I2', 'I3']
    table = []
    table.append(header)

    row = ['Lo']
    for i in range(0, 4):
      if only_active and active[t_index][i] == 0:
        val = '*'
      else:
        val = values[t_index][i]
        if active[t_index][i] == 0:
          val = '[{}]'.format(val)

      row.append(val)
    table.append(row)

    row = ['Hi']
    for i in range(0, 4):
      if only_active and active[t_index+t_count][i] == 0:
        val = '*'
      else:
        val = values[t_index+t_count][i]
        if active[t_index+t_count][i] == 0:
          val = '[{}]'.format(val)
      row.append(val)
    table.append(row)

    print(tabulate(table, tablefmt='simple'))

  if no_active_thresholds:
    print("* No active thresholds")

def show_thresholds(t, only_active, lc1, idl, lc2, alt):
  title = '=== Device Thresholds'
  if not only_active:
    title += ' (All)'
  else:
    title += ' (Active only)'
  print(title)

  if lc1:
    print_thresholds('LCLS-I Thresholds', t.lc1_value, t.lc1_active, only_active)
  if idl:
    print_thresholds('Idle Thresholds', t.idl_value, t.idl_active, only_active)
  if lc2:
    print_thresholds('LCLS-II Thresholds', t.lc2_value, t.lc2_active, only_active)
  if alt:
    print_thresholds('Alt Thresholds', t.alt_value, t.alt_active, only_active)



#=== main ==================================================================================

parser = argparse.ArgumentParser(description='change thresholds for analog devices',
                                 formatter_class=RawTextHelpFormatter)
group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. bpm1b)', type=str, nargs='?', help='device name as found in the mps database')
parser.add_argument('--all', action='store_true', default=False, dest='all_values', help='Print all thresholds, even if not active (default prints only the active thresholds). If a value is surrounded by []s, then that threshold is not active (i.e. the threshold is not restored when the application IOC reboots)')
parser.add_argument('-lc1', action='store_true', default=False, dest='lc1', help='Print only LCLS-I thresholds')
parser.add_argument('-idl', action='store_true', default=False, dest='idl', help='Print only Idle thresholds')
parser.add_argument('-lc2', action='store_true', default=False, dest='lc2', help='Print only LCLS-II thresholds')
parser.add_argument('-alt', action='store_true', default=False, dest='alt', help='Print only ALT thresholds')

parser.add_argument('--port', metavar='port', type=int, default=1975, nargs='?', help='server port (default=1975)')
parser.add_argument('--host', metavar='host', type=str, default='lcls-daemon2', nargs='?', help='server port (default=lcls-daemon2)')

proc = subprocess.Popen('whoami', stdout=subprocess.PIPE)
user = proc.stdout.readline().rstrip()

args = parser.parse_args()

device_id = -1
if (args.device_id):
  device_id = args.device_id

device_name = "None"
if (args.device_name):
  device_name =args.device_name

tm = ThresholdManagerClient(host=args.host, port=args.port)

if (tm.check_device(device_id, device_name, int(MpsManagerRequestType.GET_THRESHOLD.value)) == False):
  exit(2)

only_active = True
if (args.all_values):
  only_active = False

lc1 = args.lc1
idl = args.idl
lc2 = args.lc2
alt = args.alt

if (not lc1) and (not idl) and (not lc2) and (not alt):
  lc1 = idl = lc2 = alt = True


threshold_message = tm.get_thresholds()
show_thresholds(threshold_message, only_active, lc1, idl, lc2, alt)
