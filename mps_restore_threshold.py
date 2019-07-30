#!/usr/bin/env python
#
# Script for restoring for an MPS analog application (that may include multiple devices)
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

class RestoreManager:
  def __init__(self):
    self.host = 'lcls-dev3'
    self.port = 1975
    self.num_thresholds = 0
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect((self.host, self.port))
    self.device_id = -1

  def restore(self, app_id):
    message = MpsManagerRequest(request_type=int(MpsManagerRequestType.RESTORE_APP_THRESHOLDS.value),
                                request_device_id=app_id)
    self.sock.send(message.pack())

    response = MpsManagerResponse()
    data = self.sock.recv(response.size())
    response.unpack(data)

    if (response.status == int(MpsManagerResponseType.OK.value)):
      print(response.status_message)
      return True
    else:
      print('ERROR: Failed to restore thresholds')
      if (len(response.status_message) > 0):
        print(response.status_message)
      return False
    
#=== main ==================================================================================

parser = argparse.ArgumentParser(description='restore thresholds for analog applications',
                                 formatter_class=RawTextHelpFormatter)

parser.add_argument('--app-id', metavar='app_id', type=int, nargs='?', required=True,
                    help='global application id')

args = parser.parse_args()

rm = RestoreManager()

if (rm.restore(args.app_id) == False):
  exit(3)

