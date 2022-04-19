#!/usr/bin/env python

import socket
import sys
import os
import errno
import argparse
import time
import datetime
import signal

from mps_names import MpsName
from mps_config import MPSConfig, runtime, models
from mps_manager_protocol import *
from runtime import *
from sqlalchemy import func
from epics import PV

from threshold_manager import ThresholdManager
from threshold_restorer import ThresholdRestorer
from ctypes import *
import threading
from threading import Thread, Lock

def signal_hander(sig, frame):
    print('=== MpsManager exiting ===')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_hander)

class DatabaseReader():
    def __init__(self, db_file_name, rt_file_name):
        self.mps = MPSConfig(db_file_name, rt_file_name)
        self.session = self.mps.session
        self.rt_session = self.mps.runtime_session
        self.mps_names = MpsName(self.session)

    def __del__(self):
        self.session.close()
        self.rt_session.close()

class ReaderThread(threading.Thread):
    def __init__(self, mps_manager, message, conn, ip, port, check_only=False):
        threading.Thread.__init__(self)
        self.mps_manager = mps_manager
        self.message = message
        self.conn = conn
        self.ip = ip
        self.port = port
        self.check_only = check_only
        self.dbr = DatabaseReader(self.mps_manager.db_file_name, self.mps_manager.rt_file_name)
        
    def run(self):
        self.mps_manager.log_string('Reader [START]')
        self.mps_manager.db_reader_start()
        # Process request
        if (self.check_only):
            self.mps_manager.check_device_request(self.conn, self.dbr,
                                                  self.message.request_device_id,
                                                  self.message.request_device_name)
        elif (self.message.request_type == int(MpsManagerRequestType.GET_THRESHOLD.value)):
            self.mps_manager.get_threshold(self.dbr, self.message, self.conn, self.ip, self.port)
        else: # The message.request_device_id contains the app_id
            self.mps_manager.restore(self.conn, self.dbr, self.message.request_device_id)
        self.mps_manager.db_reader_end()
        self.mps_manager.log_string('Reader [END]')
    
class WriterThread(threading.Thread):
    def __init__(self, mps_manager, message, conn, ip, port):
        threading.Thread.__init__(self)
        self.mps_manager = mps_manager
        self.message = message
        self.conn = conn
        self.ip = ip
        self.port = port
        self.dbr = DatabaseReader(self.mps_manager.db_file_name, self.mps_manager.rt_file_name)
        
    def run(self):
        self.mps_manager.log_string('Writer [START]')
        self.mps_manager.db_write_lock.acquire()
        self.mps_manager.change_threshold(self.dbr, self.message, self.conn, self.ip, self.port)
        self.mps_manager.past_writers += 1
        self.mps_manager.db_write_lock.release()
        self.mps_manager.log_string('Writer [END]')

class MpsManager: 
  session = 0
  host = 'lcls-dev3'
  port = 1975
  log_file_name = '/tmp/mps_manager.log'
  sock = 0
  logFile = None
  logFileName = None
  log_file_lock = None
  messageCount = 0
  currentFileName = None
  stdout = False
  past_readers = 0
  past_writers = 0
  hb_pv = None
  hb_count = 0

  def __init__(self, host, port, log_file_name, db_file_name, hb_pv_name, stdout):
      self.db_file_name = db_file_name
      self.rt_file_name = '{}/{}_runtime.db'.format(os.path.dirname(self.db_file_name),
                                         os.path.basename(self.db_file_name).\
                                             split('.')[0])
      self.stdout = stdout
      self.host = host
      self.port = port
      self.log_file_name = log_file_name
      self.file = None
      self.log_file_lock = Lock()
      self.db_read_lock = Lock()
      self.db_write_lock = Lock()
      self.db_readers = 0
      self.readers = []
      self.writers = []

      if (hb_pv_name != None):
          self.hb_pv = PV(hb_pv_name)
          if (self.hb_pv.host == None):
              print(('ERROR: Cannot connect to specified heart beat PV ({})'.format(hb_pv_name)))
              exit(1)

      try:
          self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
          self.tcp_server.bind(('0.0.0.0', port))
      except socket.error:
          print('Failed to create socket')
          sys.exit()

      if (self.log_file_name != None):
          if (os.path.isfile(self.log_file_name)):
              base_name = os.path.basename(self.log_file_name)
              dir_name = os.path.dirname(self.log_file_name)
              if not '.' in base_name:
                  backup_file_name = '{}-{}'.format(base_name,
                                                    datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S'))
              else:
                  backup_file_name = '{}-{}.{}'.format(base_name.split('.')[0],
                                                       datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S'),
                                                       base_name.split('.')[1])
              os.rename(self.log_file_name, dir_name + '/' + backup_file_name)
          try:
              self.file = open(self.log_file_name, 'a', 0)
          except IOError as e:
              if e.errno == errno.EACCES:
                  print(('ERROR: No permission to write file {}'.format(self.log_file_name)))
              else:
                  print(('ERROR: errno={}, cannot write to file {}'.format(e.errno, self.log_file_name)))
              exit(1)

      myAddr = (self.host, self.port)
  
  def db_reader_start(self):
      self.db_read_lock.acquire()
      self.db_readers += 1
      if (self.db_readers == 1):
          self.db_write_lock.acquire()
      self.db_read_lock.release()

  def db_reader_end(self):
      self.db_read_lock.acquire()
      self.db_readers -= 1
      if (self.db_readers == 0):
          self.db_write_lock.release()
      self.past_readers += 1
      self.db_read_lock.release()
      
  def cleanup(self):
      old=self.readers
      self.readers = []
      for r in old:
          if not r.isAlive():
              del r
          else:
              self.readers.append(r)

      old=self.writers
      self.writers = []
      for r in old:
          if not r.isAlive():
              del r
          else:
              self.readers.append(r)


  def run(self):
      done = False
      self.log_string("+== MpsManager Server ==============================")
      self.log_string("| Host      : {}".format(self.host))
      self.log_string("| Port      : {}".format(self.port))
      self.log_string("| Config Db : {}".format(self.db_file_name))
      self.log_string("| Runtime Db: {}".format(self.rt_file_name))
      self.log_string("+===================================================")
      self.tcp_server.settimeout(5)
      while not done:
          self.tcp_server.listen(4)
          try:
              (conn, (ip, port)) = self.tcp_server.accept()
              self.process_request(conn, ip, port)
          except socket.timeout:
              self.heartbeat() # Increment heart beat PV every 5 seconds
              self.cleanup()   # Removes finished worker threads
              if (self.hb_count % 32 == 0):
                  self.log_stats()
              
  def log_string(self, message):
      self.log_file_lock.acquire()
      if self.log_file_name != None:
          self.file.write('[{}] {}\n'.format(datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S'),
                                             str(message)))
      if self.stdout:
          print(('[{}] {}'.format(datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S'),
                                 str(message))))
      self.log_file_lock.release()

  def log_stats(self):
      message = 'Active R={}/W={}, Past R={}/W={}'.\
          format(len(self.readers), len(self.writers),
                 self.past_readers, self.past_writers)
      self.log_string(message)
      
  def heartbeat(self):
      self.hb_count += 1
      try:
          if (self.hb_pv != None):
              self.hb_pv.put(self.hb_count)
      except epics.ca.CASeverityException:
          self.log_string('ERROR: Cannot update heartbeat PV ({})'.format(self.hb_pv.pvname)) 

  def decode_message(self, message, conn, ip, port):
      if (message.request_type == int(MpsManagerRequestType.RESTORE_APP_THRESHOLDS.value)):
          self.log_string('Request for restore app thresholds')
          reader = ReaderThread(self, message, conn, ip, port)
          self.readers.append(reader)
          reader.start()
      elif (message.request_type == int(MpsManagerRequestType.CHANGE_THRESHOLD.value)):
          self.log_string('Request for change device thresholds')
          writer = WriterThread(self, message, conn, ip, port)
          self.writers.append(writer)
          writer.start()
      elif (message.request_type == int(MpsManagerRequestType.GET_THRESHOLD.value)):
          self.log_string('Request for current device thresholds')
          reader = ReaderThread(self, message, conn, ip, port)
          self.readers.append(reader)
          reader.start()
      elif (message.request_type == int(MpsManagerRequestType.DEVICE_CHECK.value)):
          self.log_string('Request for restore app thresholds')
          reader = ReaderThread(self, message, conn, ip, port, True)
          self.readers.append(reader)
          reader.start()
      else:
          self.log_string('Invalid request type: {}'.format(message.request_type))

  def process_request(self, conn, ip, port):
    message=MpsManagerRequest()
    data = conn.recv(message.size())
    if data:
        message.unpack(data)
        self.decode_message(message, conn, ip, port)

  def is_analog(self, dbr, dev_id):
    analog_devices = dbr.session.query(models.AnalogDevice).filter(models.AnalogDevice.id==dev_id).all()
    if (len(analog_devices)==1):
      return True
    else:
      digital_devices = dbr.session.query(models.DigitalDevice).filter(models.DigitalDevice.id==dev_id).all()
      if (len(digital_devices)==0):
        self.log_string('ERROR: Device not found (invalid device id {0})'.format(dev_id))
      return False

  def check_device(self, dbr, dev_id, dev_name):
    if (dev_id < 0):
      try:
        d = dbr.session.query(models.Device).filter(models.Device.name==dev_name).one()
        dev_id = d.id
      except Exception as e:
          print((str(e)))
          self.log_string('ERROR: Cannot find device with name "{0}" in config database'.format(dev_name))
          return None, "name in config database"
    else:
      try:
          d = dbr.session.query(models.Device).filter(models.Device.id==dev_id).one()
      except:
          self.log_string('ERROR: Cannot find device with id="{0}" in config database'.format(dev_id))
          return None, "id not in config database"

    try:
        rt_d = dbr.rt_session.query(runtime.Device).filter(runtime.Device.id==dev_id).one()
    except Exception as e:
        print((str(e)))

        self.log_string('ERROR: Cannot find device with id="{0}" in runtime database'.format(dev_id))
        return None, "id in runtime database"

    if (rt_d.mpsdb_name != d.name):
        self.log_string('ERROR: Device names do not match in config ({0}) and runtime databases ({1})'.\
                            format(d.name, rt_d.mpsdb_name))
        return None, "Invalid names in config/runtime databases"

    if (self.is_analog(dbr, dev_id)):
        return rt_d, "Analog device"
    else:
        return rt_d, "Digital device"

  def check_analog_device(self, dbr, dev_id, dev_name):
    if (dev_id < 0):
      try:
        d = dbr.session.query(models.Device).filter(models.Device.name==dev_name).one()
        dev_id = d.id
      except Exception as e:
          print((str(e)))
          self.log_string('ERROR: Cannot find device with name "{0}" in config database'.format(dev_name))
          return None, None

    if (self.is_analog(dbr, dev_id)):
      try:
        rt_d = dbr.rt_session.query(runtime.Device).filter(runtime.Device.id==dev_id).one()
      except Exception as e:
        print((str(e)))

        self.log_string('ERROR: Cannot find device with id="{0}" in runtime database'.format(dev_id))
        return None, None

      try:
        d = dbr.session.query(models.Device).filter(models.Device.id==dev_id).one()
      except:
        self.log_string('ERROR: Cannot find device with id="{0}" in config database'.format(dev_id))
        return None, None

      if (rt_d.mpsdb_name != d.name):
        self.log_string('ERROR: Device names do not match in config ({0}) and runtime databases ({1})'.\
            format(d.name, rt_d.mpsdb_name))
        return None, None

      is_bpm = False
      if (d.device_type.name == 'BPMS'):
          is_bpm = True

    else:
      self.log_string('ERROR: Cannot set threshold for digital device')
      return None, None

    return rt_d, is_bpm

  def check_device_request(self, conn, dbr, device_id, device_name):
      self.log_string('Checking device id={}, name={}'.\
                          format(device_id, device_name))
      rt_d, status_message = self.check_device(dbr, int(device_id), device_name)
      response = MpsManagerResponse()
      if (rt_d == None):
          response.status = int(MpsManagerResponseType.BAD_DEVICE.value)
          response.device_id = 0
          response.status_message = 'Device not valid'
          if (device_id < 0):
              response.status_message += ' (name={}, '.format(device_name)
          else:
              response.status_message += ' (id={}, '.format(device_id)
          response.status_message += '{})'.format(status_message)
      else:
          response.status = int(MpsManagerResponseType.OK.value)
          response.device_id = rt_d.mpsdb_id
          response.status_message = 'Device is valid (name={}, id={}, info={})'.format(rt_d.mpsdb_name,
                                                                                       rt_d.mpsdb_id,
                                                                                       status_message)
      conn.send(response.pack())

  def check_analog_device_request(self, conn, dbr, device_id, device_name):
      self.log_string('Checking device id={}, name={}'.\
                          format(device_id, device_name))
      rt_d, is_bpm = self.check_analog_device(dbr, int(device_id), device_name)
      response = MpsManagerResponse()
      if (rt_d == None):
          response.status = int(MpsManagerResponseType.BAD_DEVICE.value)
          response.device_id = 0
          response.status_message = 'Device not valid'
          if (device_id < 0):
              response.status_message += ' (name={})'.format(device_name)
          else:
              response.status_message += ' (id={})'.format(device_id)
      else:
          response.status = int(MpsManagerResponseType.OK.value)
          response.device_id = rt_d.mpsdb_id
          response.status_message = 'Device is valid (name={}, id={})'.format(rt_d.mpsdb_name,
                                                                              rt_d.mpsdb_id)
      conn.send(response.pack())

      return rt_d, is_bpm

  def restore(self, conn, dbr, app_id):
      self.log_string('Restoring thresholds for app={}'.format(app_id))
      # Restore thresholds here
      tr = ThresholdRestorer(db=dbr.session, rt_db=dbr.rt_session, mps_names=dbr.mps_names, 
                             force_write=False, verbose=True)

      response = MpsManagerResponse()
      if (tr.restore(app_id) == False):
          response.status = int(MpsManagerResponseType.RESTORE_FAIL.value)
          response.status_message = tr.error_message
          conn.send(response.pack())
          return
      else:
          if (tr.check(app_id) == False):
              response.status = int(MpsManagerResponseType.RESTORE_FAIL.value)
              response.status_message = tr.error_message
              conn.send(response.pack())
              return
          else:
              if (tr.release() == False):
                  response.status = int(MpsManagerResponseType.RESTORE_FAIL.value)
                  response.status_message = tr.error_message
                  conn.send(response.pack())
                  return

      response.status = int(MpsManagerResponseType.OK.value)
      response.device_id = app_id
      response.status_message = 'Thresholds restored for app {}'.format(app_id)
      conn.send(response.pack())

  def get_threshold(self, dbr, message, conn, ip, port):
      self.log_string('Getting thresholds for device id={}, name={}'.\
                          format(message.request_device_id, message.request_device_name))
      rt_d, is_bpm = self.check_analog_device_request(conn, dbr, int(message.request_device_id),
                                                      message.request_device_name)
      if rt_d == None:
          self.log_string('Get threshold: invalid device')
          return

      tm = ThresholdManager(dbr.session, dbr.rt_session, dbr.mps_names)
      threshold_message = tm.get_thresholds(rt_d, is_bpm)
      threshold_message.device_name = message.request_device_name
      threshold_message.device_id = message.request_device_id
      conn.send(threshold_message.pack())

  def change_threshold(self, dbr, message, conn, ip, port):
      self.log_string('Checking device id={}, name={}'.\
                          format(message.request_device_id, message.request_device_name))
      rt_d, is_bpm = self.check_analog_device_request(conn, dbr, int(message.request_device_id),
                                                      message.request_device_name)
      if rt_d == None:
          self.log_string('Change threshold: invalid device')
          return

      # Receive list of thresholds to be changed
      threshold_message = MpsManagerThresholdRequest()
      data = conn.recv(threshold_message.size())
      print(('Received {} bytes'.format(len(data))))
      threshold_message.unpack(data)

      tm = ThresholdManager(dbr.session, dbr.rt_session, dbr.mps_names)
      log, error_pvs, status = tm.change_thresholds(rt_d, threshold_message.user_name,
                                                    threshold_message.reason, is_bpm,
                                                    threshold_message.lc1_active, threshold_message.lc1_value,
                                                    threshold_message.idl_active, threshold_message.idl_value,
                                                    threshold_message.lc2_active, threshold_message.lc2_value,
                                                    threshold_message.alt_active, threshold_message.alt_value,
                                                    threshold_message.disable)

      self.log_string('\n' + log + ': ' + error_pvs)
      if status:
          response_message = MpsManagerThresholdResponse(status=0, message="OK")
      else:
          response_message = MpsManagerThresholdResponse(status=1, 
                                                         message='{}:{}'.format(log,error_pvs))
      conn.send(response_message.pack())

  def send_response(self, response, requestor):
      self.sock.sendto(response.pack(), requestor)
      

#===========================================================================
# Main

def main(host, port, log_file_name, database_name, hb_pv_name, stdout):
    mps_manager = MpsManager(host, port, log_file_name, database_name, hb_pv_name, stdout)
    mps_manager.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Receive MPS status messages')
    parser.add_argument('--port', metavar='port', type=int, nargs='?', help='server port (default=3356)')
    parser.add_argument('database', metavar='db', type=file, nargs=1,
                        help='database file name (e.g. mps_gun_config.db)')
    parser.add_argument('--log-file', metavar='log_file', type=str, nargs='?',
                        help='MpsManager log file base, e.g. /data/mps_manager/server.log')
    parser.add_argument('-c', action='store_true', default=False, dest='stdout', help='Print log messages to stdout')
    parser.add_argument('--hb', metavar='PV', type=str, nargs='?', 
                        default=None, required=False, help='PV used as heart beat by the server')

    args = parser.parse_args()

    host = socket.gethostname()

    log_file_name=None
    if args.log_file:
        log_file_name = args.log_file

    port=1975
    if args.port:
        port = args.port

    stdout=False
    if args.stdout:
        stdout=True
       
    main(host=host, port=port, log_file_name=log_file_name,
         database_name=args.database[0].name,
         hb_pv_name=args.hb, stdout=stdout)

