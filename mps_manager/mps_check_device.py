#!/usr/bin/env python
#
# Script for changing checking if device is in run time db
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

parser = argparse.ArgumentParser(description='check device',
                                 formatter_class=RawTextHelpFormatter)

group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. bpm1b)', type=str, nargs='?', help='device name as found in the mps database')

parser.add_argument('--port', metavar='port', type=int, default=1975, nargs='?', help='server port (default=1975)')
parser.add_argument('--host', metavar='host', type=str, default='lcls-daemon2', nargs='?', help='server port (default=lcls-daemon2)')

args = parser.parse_args()

device_id = -1
if (args.device_id):
  device_id = args.device_id

device_name = "None"
if (args.device_name):
  device_name =args.device_name

tm = ThresholdManagerClient(host=args.host, port=args.port)

if (tm.check_device(device_id, device_name) == False):
  exit(2)

