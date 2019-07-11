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
from pprint import *

class ThresholdManager:
  """
  Changes thresholds of analog devices - save value in database and set device using channel access
  """
  def __init__(self, session, rt_session, mps_names):
    self.session = session
    self.rt_session = rt_session
    self.mps_names = mps_names

  def updateThreshold(self, rt_d, t_table, integrator_k, t_type, value_v):
    """
    Save the threshold value to the database as the current value, also
    set the active field (it will be False if the threshold was never used before)
    """
    setattr(getattr(rt_d, t_table), '{0}_{1}'.format(integrator_k,t_type), value_v)
    setattr(getattr(rt_d, t_table), '{0}_{1}_active'.format(integrator_k,t_type), True)
    self.rt_session.commit()

  def getThresholdHistoryName(self, table_k, t_index):
    """
    Returns the database table that contains the history for the type of
    threshold.
    """
    if (table_k == 'idl'):
      return 'ThresholdHistoryIdl'
    elif (table_k == 'lc1'):
      return 'ThresholdHistoryLc1'
    elif (table_k == 'lc2'):
      return 'Threshold{0}History'.format(t_index[1])
    elif (table_k == 'alt'):
      return 'ThresholdAlt{0}History'.format(t_index[1])

    return None
  
  def addHistory(self, table_k, t_index, rt_d, t_table, user, reason):
    """
    Make an entry recording the threshold setting history - sets the user
    name, date and reason for the change
    """
    hist_name = self.getThresholdHistoryName(table_k, t_index)
    hist_class = globals()[hist_name]
    hist = hist_class(user=user, reason=reason, device_id=rt_d.id)

    # Copy thresholds from rt_d.threshold to history
    for k in getattr(rt_d, t_table).__dict__.keys():
      if (re.match('i[0-3]_[lh]', k)):
        db_value = float(getattr(getattr(rt_d, t_table), k))
        setattr(hist, k, db_value)

    self.rt_session.add(hist)
    self.rt_session.commit()

    return True

  def writeThreshold(self, pv, value, pv_enable, pv_enable_value):
    try:
      pv.put(value)
    except epics.ca.CASeverityException:
      if (self.force_write):
        return True
      else:
        print('ERROR: Tried to write to a read-only PV ({}={})'.format(pv.pvname, value))
        return False

    try:
      pv_enable.put(pv_enable_value)
    except epics.ca.CASeverityException:
      if (self.force_write):
        return True
      else:
        print('ERROR: Tried to write to a read-only PV ({}={})'.format(pv_enable.pvname, pv_enable_value))
        return False

    return True

  def build_entries(self, table_name, active, values, t_type, t_index):
    integrator_index = 0
    table = []
    for a, v in zip(active, values):
      threshold_index_str = 'T{}'.format(t_index)
      integrator_index_str = 'I{}'.format(integrator_index)
      if a == 1:
        table.append([table_name, threshold_index_str,
                      integrator_index_str, t_type, v])
      integrator_index += 1
      if integrator_index == 4:
        integrator_index = 0

    return table

  def build_table(self, lc1_active, lc1_value, idl_active, idl_value,
                  lc2_active, lc2_value, alt_active, alt_value):
    table = []
    table += self.build_entries('lc1', lc1_active[0], lc1_value[0], 'lolo', 0)
    table += self.build_entries('lc1', lc1_active[1], lc1_value[1], 'hihi', 0)
    
    table += self.build_entries('idl', idl_active[0], idl_value[0], 'lolo', 0)
    table += self.build_entries('idl', idl_active[1], idl_value[1], 'hihi', 0)

    for t in range(0,8):
      table += self.build_entries('lc2', lc2_active[t], lc2_value[t], 'lolo', t)
      table += self.build_entries('lc2', lc2_active[t+8], lc2_value[t+8], 'hihi', t)
    
      table += self.build_entries('alt', alt_active[t], alt_value[t], 'lolo', t)
      table += self.build_entries('alt', alt_active[t+8], alt_value[t+8], 'hihi', t)
    
    return table

  #
  # Update the thresholds in database and make enty in the history table.
  #
  def change_thresholds(self, rt_d, user, reason, is_bpm,
                        lc1_active, lc1_value, idl_active, idl_value,
                        lc2_active, lc2_value, alt_active, alt_values,
                        disable):

    t = self.build_table(lc1_active, lc1_value, idl_active, idl_value,
                         lc2_active, lc2_value, alt_active, alt_values)

    if disable:
      pv_enable_value = 0
    else:
      pv_enable_value = 1

    force_write = True
    ignore_pv = True
    message, pv_names, status = self.build_threshold_table(rt_d, t, force_write, ignore_pv, is_bpm)
    if (not status):
      return message, pv_names, False

    message, status = self.verify_thresholds(rt_d)
    if (not status):
      return message, '', False

    log = '=== Threshold Change for device "{0}" ===\n'.format(rt_d.mpsdb_name)
    log = log + 'User: {0}\n'.format(user)
    log = log + 'Reason: {0}\n'.format(reason)
    log = log + 'Date: {0}\n\n'.format(time.strftime("%Y/%m/%d %H:%M:%S"))
    pv_change_status = True
    pv_names = ''

    for table_k, table_v in self.table.items():
      for threshold_k, threshold_v in table_v.items():
        for integrator_k, integrator_v in threshold_v.items():
          # Get threshold table
          t_table = self.getThresholdTableName(table_k, integrator_k, threshold_k)
          for value_k, value_v in integrator_v.items():
            if (value_k == 'l'):
              pv = integrator_v['l_pv']
              pv_enable = integrator_v['l_pv_enable']
            elif (value_k == 'h'):
              pv = integrator_v['h_pv']
              pv_enable = integrator_v['h_pv_enable']

            if (value_k == 'l' or value_k == 'h'):
              old_value = getattr(getattr(rt_d, t_table), '{1}_{2}'.format(t_table, integrator_k, value_k))
              if (not self.writeThreshold(pv, value_v, pv_enable, pv_enable_value)):
                pv_change_status = False
                pv_names = '{}* {}={}\n'.format(pv_names,pv.pvname, value_v)
              self.updateThreshold(rt_d, t_table, integrator_k, value_k, value_v)
              pv_name = pv.pvname
              log = log + '{}: threshold={} integrator={} type={} prev={} new={}\n'.\
                  format(pv_name, threshold_k, integrator_k, value_k, old_value, value_v)

        self.addHistory(table_k, threshold_k, rt_d, t_table, user, reason)


    log = log + "==="
    
    if (not pv_change_status):
      print('ERROR: Failed to update the following PVs:')
      print(pv_names)
      return log, pv_names, False

    return log, '', True

  def getThresholdTableName(self, table_name, integrator_name, threshold_name):
    if (table_name == 'lc2'):
      t_table = 'threshold{0}'.format(threshold_name[1])

    if (table_name == 'alt'):
      t_table = 'threshold_alt{0}'.format(threshold_name[1])

    if (table_name == 'lc1'):
      t_table = 'threshold_lc1'

    if (table_name == 'idl'):
      t_table = 'threshold_idl'

    return t_table

  #
  # Check if the specified thresholds are valid, i.e. HIHI > LOLO value
  # If only the LOLO or HIHI is specified, then check against the
  # current value in the database
  #
  def verify_thresholds(self, rt_d):
    for table_k, table_v in self.table.items():
      for threshold_k, threshold_v in table_v.items():
        for integrator_k, integrator_v in threshold_v.items():

          new_low = None
          new_high = None

          if ('l' in integrator_v.keys()):
            new_low = float(integrator_v['l'])
          if ('h' in integrator_v.keys()):
            new_high = float(integrator_v['h'])


          if (new_low != None and new_high != None):
            if (new_low >= new_high):
              error_message = 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
                  format(rt_d.mpsdb_name, table_k, integrator_k, threshold_k)
              error_message += '\nERROR: HIHI threshold (value={0}) smaller or equal to LOLO (value={1}), cannot proceed'.format(new_high, new_low)
              print(error_message)

              return error_message, False

          if (new_low == None or new_high == None):
            t_table = self.getThresholdTableName(table_k, integrator_k, threshold_k)
            t_type = 'h'
            if (new_low == None):
              t_type = 'l'

            db_value = float(getattr(getattr(rt_d, t_table), '{0}_{1}'.format(integrator_k,t_type)))

            if (new_low == None):
  #            print 'Checking new_high{1} <= db_value{0}'.format(db_value, new_high)
              if (new_high <= db_value):
                error_message = 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
                  format(rt_d.mpsdb_name, table_k, integrator_k, threshold_k)
                error_message += '\nERROR: Specified HIHI value ({0}) is smaller or equal than the database LOLO value ({1})'.\
                    format(new_high, db_value)
                return error_message, False

            if (new_high == None):
   #           print 'Checking new_low {0} >= db_value{1}'.format(new_low, db_value)
              if (new_low >= db_value):
                error_message = 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
                  format(rt_d.mpsdb_name, table_k, integrator_k, threshold_k)
                error_message += '\nERROR: Specified LOLO value ({0}) is greater or equal than the database HIHI value ({1})'.\
                    format(new_low, db_value)
                return error_message, False

  #        print 'low={0} high={1}'.format(new_low, new_high)

    return '', True

  #
  # Build a table/dictionary from the command line parameters
  #
  def build_threshold_table(self, rt_d, t, force_write, ignore_pv, is_bpm):
    # fist check the parameters
    valid_pvs = True
    bad_pv_names = ''
    ro_pvs = False
    ro_pv_names = '' # read-only pv names
    self.force_write = force_write
    self.ignore_pv = ignore_pv
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
        print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
            format(rt_d.mpsdb_name, table_name, integrator, t_index)
        print 'ERROR: Invalid table "{0}" (parameter={1})'.format(l[0], l)
        return False

      if (not (((integrator.startswith('i')) and
                len(integrator)==2 and
                int(integrator[1])>=0 and
                int(integrator[1])<=3) or
               integrator=='x' or
               integrator=='y' or
               integrator=='tmit')):
        print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
            format(rt_d.mpsdb_name, table_name, integrator, t_index)
        print 'ERROR: Invalid integrator "{0}" (parameter={1})'.format(integrator, l)
        return False

      if (not (t_index.startswith('t'))):
        print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
            format(rt_d.mpsdb_name, table_name, integrator, t_index)
        print 'ERROR: Invalid threshold "{0}", must start with T (parameter={1})'.format(t_index, l)
        return False
      else:
        if (len(t_index) != 2):
          print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
              format(rt_d.mpsdb_name, table_name, integrator, t_index)
          print 'ERROR: Invalid threshold "{0}", must be in T<index> format (parameter={1})'.format(t_index, l)
          return False
        else:
          if (table_name == 'lc2' or table_name == 'alt'):
            if (int(t_index[1])<0 or int(t_index[1])>7):
              print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
                  format(rt_d.mpsdb_name, table_name, integrator, t_index)
              print 'ERROR: Invalid threshold index "{0}", must be between 0 and 7 (parameter={1})'.\
                  format(t_index[1], l)
              return False
          else:
            if (int(t_index[1]) != 0):
              print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
                  format(rt_d.mpsdb_name, table_name, integrator, t_index)
              print 'ERROR: Invalid threshold index "{0}", must be 0'.\
                  format(t_index[1], l)
              return False

      if (not (t_type == 'lolo' or
               t_type == 'hihi')):
        print 'ERROR: Invalid thresholds for device {0}, table {1}, integrator {2}, threshold {3}'.\
            format(rt_d.mpsdb_name, table_name, integrator, t_index)
        print 'ERROR: Invalid threshold type "{0}", must be LOLO or HIHI (parameter={1})'.\
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

      # Rename fields to match database
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
        pv_name = self.mps_names.getThresholdPv(self.mps_names.getAnalogDeviceNameFromId(rt_d.mpsdb_id),
                                                table_name, t_index, integrator, t_type, is_bpm)
        pv_name_enable = pv_name + '_EN'
        pv = PV(pv_name)
        pv_enable = PV(pv_name_enable)

        if (t_type == 'l'):
          self.table[table_name][t_index][integrator]['l_pv']=pv
          self.table[table_name][t_index][integrator]['l_pv_enable']=pv_enable
        else:
          self.table[table_name][t_index][integrator]['h_pv']=pv
          self.table[table_name][t_index][integrator]['h_pv_enable']=pv_enable

        if (pv.host == None or pv_enable.host == None):
          if (not ignore_pv):
            valid_pvs = False
            bad_pv_names = '{} {}'.format(bad_pv_names, pv_name)
        elif (not force_write):
          if (not pv.write_access):
            ro_pvs = True
            ro_pv_names = '{} {}'.format(ro_pv_names, pv_name)

#    pp=PrettyPrinter(indent=4)
#    pp.pprint(self.table)

    if (not valid_pvs):
      error_message = 'Cannot find PV(s)'
      print('ERROR: The following PV(s) cannot be reached, threshold change not allowed:')
      print(bad_pv_names)
      return error_message, bad_pv_names, False

    if (ro_pvs):
      error_message = 'Read-only PV(s)'
      print('ERROR: The following PV(s) are read-only, threshold change not allowed:')
      print(ro_pv_names)
      return error_message, ro_pv_names, False

    return 'OK', '', True
    
