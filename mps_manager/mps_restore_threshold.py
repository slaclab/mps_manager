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
from threshold_manager_client import ThresholdManagerClient
import socket
from ctypes import *
from struct import *

#=== main ==================================================================================

parser = argparse.ArgumentParser(description='restore thresholds for analog applications',
                                 formatter_class=RawTextHelpFormatter)

parser.add_argument('--app-id', metavar='app_id', type=int, nargs='?', required=True,
                    help='global application id')
parser.add_argument('--port', metavar='port', type=int, default=1975, nargs='?', help='server port (default=1975)')
parser.add_argument('--host', metavar='host', type=str, default='lcls-daemon2', nargs='?', help='server port (default=lcls-daemon2)')

args = parser.parse_args()

rm = ThresholdManagerClient(host=args.host, port=args.port)

if (rm.restore(args.app_id) == False):
  exit(3)

