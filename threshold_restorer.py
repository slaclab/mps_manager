from mps_config import MPSConfig, models, runtime
from mps_names import MpsName
from runtime_utils import RuntimeChecker
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

class ThresholdRestorer:
  threshold_tables = ['threshold0','threshold1','threshold2','threshold3',
                      'threshold4','threshold5','threshold6','threshold7',
                      'threshold_alt0', 'threshold_alt1','threshold_alt2', 'threshold_alt3',
                      'threshold_alt4', 'threshold_alt5','threshold_alt6', 'threshold_alt7',
                      'threshold_lc1', 'threshold_idl']
  threshold_tables_pv = ['lc2', 'lc2', 'lc2', 'lc2', 'lc2', 'lc2', 'lc2', 'lc2',
                         'alt', 'alt', 'alt', 'alt', 'alt', 'alt', 'alt', 'alt', 
                         'lc1', 'idl']
  threshold_types = ['l','h']
  integrators = ['i0','i1','i2','i3']
  threshold_index = ['t0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
                     't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
                     't0', 't0']
  def __init__(self, db=None, rt_db=None, mps_names=None, force_write=False, verbose=False):
    """
    Restore thresholds of analog devices - using latest thresholds saved in database
    force_write: True -> ignore PV read-only errors
                 False -> return error when writing to read-only PVs
    """
    self.session = db
    self.rt_session = rt_db
    self.mps_names = mps_names
    self.error_message = ''

    self.verbose = verbose
    self.force_write = force_write
    self.rt = RuntimeChecker(self.session, self.rt_session, self.verbose)

    self.app = None

  def check_app(self, app_id):
    if (self.verbose):
      sys.stdout.write('Checking app_id {}... '.format(app_id))
    
    self.app = None
    try:
      self.app = self.session.query(models.ApplicationCard).\
          filter(models.ApplicationCard.global_id==app_id).one()
    except:
      self.error_message='ERROR: Cannot find application with global id {}.'.format(app_id)
      print(self.error_message)
      return None

    if (self.verbose):
      print('found')


    if (len(self.app.analog_channels) == 0):
      self.error_message='ERROR: There are no analog channels defined for this application (global id={})'.\
          format(app_id)
      print(self.error_message)
      print('Name: {}'.format(self.app.name))
      print('Description: {}'.format(self.app.description))
      print('Crate: {}, Slot: {}'.format(self.app.crate.get_name(), app.slot_number))
      return None

    print('Name: {}'.format(self.app.name))
    print('Description: {}'.format(self.app.description))
    print('Crate: {}, Slot: {}'.format(self.app.crate.get_name(), self.app.slot_number))

    return self.app

  def check_devices(self, app):
    if (self.verbose):
      sys.stdout.write('Checking devices... ')

    devices = []
    for c in app.analog_channels:
      [device, rt_device] = self.rt.check_device(c.analog_device.id)
      if (rt_device == None):
        return None
      else:
        devices.append([device, rt_device])

    if (self.verbose):
      print('done.')

    return devices

  def get_restore_list(self, devices):
    """
    Assembles and returns a list of dicts [{ 'device': device, 'pv': pyepicspv,
                                             'pv_enable': pyepicspv, 'value': threshold},...].
    The thresholds in the list are only those that have been set in the past,
    that is given by the '*_active' table field.

    The input parameter devices in a list of pairs [[device, rt_device],...]
    """
    if (self.verbose):
      print('Retrieving thresholds from database:')

    restore_list=[]
    for [d, rt_d] in devices:
      is_bpm = False
      if (d.device_type.name == 'BPMS'):
        is_bpm = True

      threshold_list = self.rt.get_thresholds(d)

      for threshold_item in threshold_list:
        restore_item = {}
        if (threshold_item['active']):
          restore_item['device'] = rt_d
          restore_item['pv'] = threshold_item['pv']
          restore_item['pv_enable'] = threshold_item['pv_enable']
          restore_item['value'] = threshold_item['value']
          restore_list.append(restore_item)
          if (self.verbose):
            print('{}={}'.format(threshold_item['pv'].pvname, threshold_item['value']))
        else:
          if (threshold_item['pv'] != None):
            threshold_item['pv'].disconnect()
          if (threshold_item['pv_enable'] != None):
            threshold_item['pv_enable'].disconnect()

    if (self.verbose):
      print('done.')
 
    return restore_list

  def check_pvs(self, restore_list, max_fail_pvs=0):
    """
    Check if the PVs in the restore list are available
    max_fail_pvs: number of PVs allowed to fail (host==None) before returning, if 0 then test them all
    """
    fail_count = 0
    if (self.verbose):
      print('Checking PVs...')
    valid_pvs = True
    bad_pv_names = ''
    for restore_item in restore_list:
      print(restore_item['pv'].pvname)
      if (restore_item['pv'].host == None):
        valid_pvs = False
        bad_pv_names = '{} * {}\n'.format(bad_pv_names, restore_item['pv'].pvname)
        fail_count += 1
      print(restore_item['pv_enable'].pvname)
      if (restore_item['pv_enable'].host == None):
        valid_pvs = False
        bad_pv_names = '{} * {}\n'.format(bad_pv_names, restore_item['pv_enable'].pvname)
        fail_count += 1
      # Give up if to many PVs fail to connect
      if (max_fail_pvs > 0 and fail_count >= max_fail_pvs):
        break;
    
    if (not valid_pvs):
      self.error_message = 'ERROR: PV(s) cannot be reached, threshold change not allowed.'
      print('ERROR: The following PV(s) cannot be reached, threshold change not allowed:')
      print(bad_pv_names)
      return False

    if (self.verbose):
      print('done.')
    return True

  def do_restore(self, restore_list):
    if (self.verbose):
      print('Starting restore process')

    for restore_item in restore_list:
      try:
        restore_item['pv'].put(restore_item['value'])
      except epics.ca.CASeverityException:
        self.error_message='ERROR: Tried to write to a read-only PV ({}={})'.\
            format(restore_item['pv'].pvname, restore_item['value'])
        print self.error_message
        if (self.force_write):
          return True
        else:
          return False

      try:
        restore_item['pv_enable'].put(1)
      except epics.ca.CASeverityException:
        self.error_message='ERROR: Tried to write to a read-only PV ({}=1)'.\
            format(restore_item['pv_enable'].pvname)
        print self.error_message
        if (self.force_write):
          return True
        else:
          return False

    if (self.verbose):
      print('Finished restore process')

    return True

  def disconnect(self, restore_list):
    for restore_item in restore_list:
      restore_item['pv'].disconnect()
      restore_item['pv_enable'].disconnect()

  def release(self):
    if (self.app == None):
      return False

    release_pv = PV('{}:THR_LOADED'.format(self.app.get_pv_name()))

    if (self.verbose):
      sys.stdout.write('Releasing IOC (setting {})...'.format(release_pv.pvname))

    # do release
    if (release_pv.host == None):
      print('ERROR: Failed to read release PV {}'.format(release_pv.pvname))
      return False

    try:
      release_pv.put(1)
    except epics.ca.CASeverityException:
      print('ERROR: Tried to write to a read-only PV ({}=1)'.\
              format(release_pv.pvname))
      return False
      
    release_pv.disconnect()

    if (self.verbose):
      print(' done.')

  def restore(self, app_id, release=False):
    app = self.check_app(app_id)
    if (app == None):
      return False

    devices = self.check_devices(app)
    if (devices == None):
      self.error_message = 'ERROR: found no devices for application {}'.format(app_id)
      print(self.error_message)
      return False
      
    restore_list = self.get_restore_list(devices)
    if (not self.check_pvs(restore_list, max_fail_pvs=2)):
      return False

    if (not self.do_restore(restore_list)):
      return False

    if (release):
      self.release(app)

    self.disconnect(restore_list)
      
    return True

  def check(self, app_id):
    return self.rt.check_app_thresholds(app_id)
    
