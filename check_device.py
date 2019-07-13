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
import socket
from ctypes import *
from struct import *

class ThresholdManager:
  def __init__(self):
    self.host = 'lcls-dev3'
    self.port = 1975
    self.num_thresholds = 0
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect((self.host, self.port))
    self.device_id = -1

  def check_device(self, dev_id, dev_name):
    message = MpsManagerRequest(request_type=int(MpsManagerRequestType.DEVICE_CHECK.value),
                                request_device_id=dev_id, request_device_name=dev_name)
    self.sock.send(message.pack())

    response = MpsManagerResponse()
    data = self.sock.recv(response.size())
    response.unpack(data)

    if (response.status == int(MpsManagerResponseType.OK.value)):
      self.device_id = response.device_id
      print('Device is valid (id={})'.format(response.device_id))
      return True
    else:
      print('ERROR: Invalid device')
      return False
    
#=== main ==================================================================================

parser = argparse.ArgumentParser(description='check device',
                                 formatter_class=RawTextHelpFormatter)

group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. bpm1b)', type=str, nargs='?', help='device name as found in the mps database')

args = parser.parse_args()

device_id = -1
if (args.device_id):
  device_id = args.device_id

device_name = "None"
if (args.device_name):
  device_name =args.device_name

tm = ThresholdManager()

if (tm.check_device(device_id, device_name) == False):
  exit(2)

