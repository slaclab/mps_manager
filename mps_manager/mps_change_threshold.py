#!/usr/bin/env python
#
# Script for changing thresholds for MPS analog devices
#

import sys
import argparse
import time 
import os
import re
import subprocess

from argparse import RawTextHelpFormatter
from mps_manager_protocol import *
from threshold_manager_client import ThresholdManagerClient
import socket
from ctypes import *
from struct import *

#=== main ==================================================================================

parser = argparse.ArgumentParser(description='change thresholds for analog devices',
                                 formatter_class=RawTextHelpFormatter)
parser.add_argument('--reason', metavar='reason', type=str, nargs=1, help='reason for the threshold change', required=True)
parser.add_argument('-t', nargs=5, action='append', 
                    help='<table threshold_index integrator threshold_type value>\nwhere:\n'+
                         '  table: lc2, alt, lc1 or idl\n'
                         '  threshold_index: t0 through t7 (must be t0 for lcls-i and idle thresholds)\n'+
                         '  integrator_index: i0, i1, i2, i3, x, y or tmit\n'+
                         '  threshold_type: lolo or hihi\n'+
                         '  value: new threshold value\n\ntables:\n'+
                         '  lc2: lcls-ii thresholds\n'+
                         '  alt: alternative lcls-ii thresholds\n'+
                         '  lc1: lcls-i thresholds, only t0 available\n'+
                         '  idl: no beam thresholds, only t0 available\n')

parser.add_argument('--disable', action='store_true', default=False, help="Disable specified thresholds")

group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. bpm1b)', type=str, nargs='?', help='device name as found in the mps database')

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

reason = args.reason[0]

tm = ThresholdManagerClient(host=args.host, port=args.port)

if (tm.build_threshold_table(args.t) == False):
  exit(1)

if (tm.check_device(device_id, device_name, int(MpsManagerRequestType.CHANGE_THRESHOLD.value)) == False):
  exit(2)

if (tm.change_thresholds(user, reason, device_id,
                         device_name, args.disable) == False):
  exit(3)

