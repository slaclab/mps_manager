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

  def check_device(self, user, reason, dev_id, dev_name):
    message = MpsManagerRequest()
    message.request_type = int(MpsManagerRequestType.DEVICE_CHECK.value)
    message.device_id = dev_id
    message.device_name = dev_name
    message.user_name = user
    message.reason = reason
    message.thr_count = self.num_thresholds
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

  def change_thresholds(self):
    message = MpsManagerThresholdRequest()

    for thr_table, v in self.table.items(): # lc1, lc2, idl or aln
#      print thr_table
      for thr_index, v2 in v.items(): # T0 through T7
#        print ' ' + thr_index
        thr_index_index = int(thr_index[1])
        for thr_integrator, v3 in v2.items(): # I0 through I4
#          print('  ' + thr_integrator)
          thr_int_index = int(thr_integrator[1])
          for thr_type, thr_value in v3.items(): # LOLO or HIHI
            thr_type_index = 0 if thr_type == 'l' else  1
#            print('    {} = {}'.format(thr_type, thr_value))
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
    
    self.sock.send(message.pack())

    response = MpsManagerThresholdResponse()
    data = self.sock.recv(response.size())
    response.unpack(data)

    if response.status != 0:
      print('ERROR: Operation failed - {}'.format(response.message))

  #
  # build a table/dictionary from the command line parameters
  #
  def build_threshold_table(self, t):
    # fist check the parameters

    for l in t:
      self.num_thresholds += 1
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
    self.table = {}
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

      if (not table_name in self.table.keys()):
        self.table[table_name]={}

      if (not t_index in self.table[table_name].keys()):
        self.table[table_name][t_index]={}

      if (not integrator in self.table[table_name][t_index].keys()):
        self.table[table_name][t_index][integrator]={}

      if (not t_type in self.table[table_name][t_index][integrator].keys()):
        self.table[table_name][t_index][integrator][t_type]=value

    return True
    
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

group_list = parser.add_mutually_exclusive_group()
group_list.add_argument('--device-id', metavar='database device id', type=int, nargs='?', help='database id for the device')
group_list.add_argument('--device-name', metavar='database device name (e.g. bpm1b)', type=str, nargs='?', help='device name as found in the mps database')

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

tm = ThresholdManager()

if (tm.build_threshold_table(args.t) == False):
  exit(1)

if (tm.check_device(user, reason, device_id, device_name) == False):
  exit(2)

if (tm.change_thresholds() == False):
  exit(3)

