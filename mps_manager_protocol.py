from ctypes import *
from enum import Enum
from struct import *

class MpsManagerRequestType(Enum):
    """
    Request types:
    DEVICE_CHECK - send before request to change threshold, to check if a device id
    or name is valid.
    CHANGE_THRESHOLD - sent after a DEVICE_CHECK, for each threshold change request
    RESTORE_APP_THRESHOLDS - sent by IOC after a reboot
    """
    DEVICE_CHECK = '1'
    CHANGE_THRESHOLD = '2'
    RESTORE_APP_THRESHOLDS = '3'

class MpsManagerResponseType(Enum):
    BAD_REQUEST = '1'
    BAD_DEVICE = '2'
    OK = '3'

class MpsManagerResponse():
    def __init__(self, status=0, device_id=0):
        self.status = status
        self.device_id = device_id

        self.format = "ii"
        self.struct = Struct(self.format)
    
    def size(self):
        return calcsize(self.format)

    def pack(self):
        return self.struct.pack(self.status, self.device_id)

    def unpack(self, data):
        self.status, self.device_id = self.struct.unpack(data)

    def to_string(self):
        return 'message.to_string() TDB'

class MpsManagerThresholdResponse():
    def __init__(self, status=0, message='OK'):
        self.status = status
        self.message = message # 1000 chars
        self.format = 'i1000s'
        self.struct = Struct(self.format)

    def size(self):
        return calcsize(self.format)

    def pack(self):
        return self.struct.pack(self.status, self.message)

    def unpack(self, data):
        self.status, self.message = self.struct.unpack(data)
        self.message = self.message.rstrip('\0')

class MpsManagerThresholdRequest():
    def __init__(self):
        self.lc1_active = [[0, 0, 0, 0], # I0, I1, I2, I3 low active
                           [0, 0, 0, 0]] # I0, I1, I2, I3 high active
        self.lc1_value  = [[0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 low values
                           [0.0, 0.0, 0.0, 0.0]] # I0, I1, I2, I3 high values
        self.format = "8i8d"

        self.idl_active = [[0, 0, 0, 0], # I0, I1, I2, I3 low active
                           [0, 0, 0, 0]] # I0, I1, I2, I3 high active
        self.idl_value  = [[0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 low values
                           [0.0, 0.0, 0.0, 0.0]] # I0, I1, I2, I3 high values
        self.format += "8i8d"

        self.lc2_active = [[0, 0, 0, 0], # I0, I1, I2, I3 low active for T0
                           [0, 0, 0, 0], # same for T1 
                           [0, 0, 0, 0], # same for T2 
                           [0, 0, 0, 0], # same for T3 
                           [0, 0, 0, 0], # same for T4 
                           [0, 0, 0, 0], # same for T5 
                           [0, 0, 0, 0], # same for T6 
                           [0, 0, 0, 0], # same for T7 
                           [0, 0, 0, 0], # I0, I1, I2, I3 high active for T0
                           [0, 0, 0, 0], # same for T1 
                           [0, 0, 0, 0], # same for T2 
                           [0, 0, 0, 0], # same for T3 
                           [0, 0, 0, 0], # same for T4 
                           [0, 0, 0, 0], # same for T5 
                           [0, 0, 0, 0], # same for T6 
                           [0, 0, 0, 0]] # same for T7 
        self.format += "64i"

        self.lc2_value  = [[0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 low values for T0
                           [0.0, 0.0, 0.0, 0.0], # same for T1
                           [0.0, 0.0, 0.0, 0.0], # same for T2
                           [0.0, 0.0, 0.0, 0.0], # same for T3
                           [0.0, 0.0, 0.0, 0.0], # same for T4
                           [0.0, 0.0, 0.0, 0.0], # same for T5
                           [0.0, 0.0, 0.0, 0.0], # same for T6
                           [0.0, 0.0, 0.0, 0.0], # same for T7
                           [0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 high values for T0
                           [0.0, 0.0, 0.0, 0.0], # same for T1
                           [0.0, 0.0, 0.0, 0.0], # same for T2
                           [0.0, 0.0, 0.0, 0.0], # same for T3
                           [0.0, 0.0, 0.0, 0.0], # same for T4
                           [0.0, 0.0, 0.0, 0.0], # same for T5
                           [0.0, 0.0, 0.0, 0.0], # same for T6
                           [0.0, 0.0, 0.0, 0.0]] # same for T7
        self.format += "64d"

        self.alt_active = [[0, 0, 0, 0], # I0, I1, I2, I3 low active for T0
                           [0, 0, 0, 0], # same for T1 
                           [0, 0, 0, 0], # same for T2 
                           [0, 0, 0, 0], # same for T3 
                           [0, 0, 0, 0], # same for T4 
                           [0, 0, 0, 0], # same for T5 
                           [0, 0, 0, 0], # same for T6 
                           [0, 0, 0, 0], # same for T7 
                           [0, 0, 0, 0], # I0, I1, I2, I3 high active for T0
                           [0, 0, 0, 0], # same for T1 
                           [0, 0, 0, 0], # same for T2 
                           [0, 0, 0, 0], # same for T3 
                           [0, 0, 0, 0], # same for T4 
                           [0, 0, 0, 0], # same for T5 
                           [0, 0, 0, 0], # same for T6 
                           [0, 0, 0, 0]] # same for T7 
        self.format += "64i"

        self.alt_value  = [[0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 low values for T0
                           [0.0, 0.0, 0.0, 0.0], # same for T1
                           [0.0, 0.0, 0.0, 0.0], # same for T2
                           [0.0, 0.0, 0.0, 0.0], # same for T3
                           [0.0, 0.0, 0.0, 0.0], # same for T4
                           [0.0, 0.0, 0.0, 0.0], # same for T5
                           [0.0, 0.0, 0.0, 0.0], # same for T6
                           [0.0, 0.0, 0.0, 0.0], # same for T7
                           [0.0, 0.0, 0.0, 0.0], # I0, I1, I2, I3 high values for T0
                           [0.0, 0.0, 0.0, 0.0], # same for T1
                           [0.0, 0.0, 0.0, 0.0], # same for T2
                           [0.0, 0.0, 0.0, 0.0], # same for T3
                           [0.0, 0.0, 0.0, 0.0], # same for T4
                           [0.0, 0.0, 0.0, 0.0], # same for T5
                           [0.0, 0.0, 0.0, 0.0], # same for T6
                           [0.0, 0.0, 0.0, 0.0]] # same for T7
        self.format += "64d"        

        self.struct = Struct(self.format)

    def size(self):
        return calcsize(self.format)

    def pack(self):
        all_values = [item for sublist in self.lc1_active for item in sublist]
        all_values += [item for sublist in self.lc1_value for item in sublist]
        all_values += [item for sublist in self.idl_active for item in sublist]
        all_values += [item for sublist in self.idl_value for item in sublist]
        all_values += [item for sublist in self.lc2_active for item in sublist]
        all_values += [item for sublist in self.lc2_value for item in sublist]
        all_values += [item for sublist in self.alt_active for item in sublist]
        all_values += [item for sublist in self.alt_value for item in sublist]

        return self.struct.pack(*all_values)

    def unpack_array(self, array):
        inner_counter = 4
        array_index = 0
        inner_index = 0
        outer_table = []
        inner_table = []

        for value in array:
          inner_table.append(value)
          inner_index += 1
          if (inner_index == inner_counter):
            inner_index = 0
            outer_table.append(inner_table)
            inner_table = []

        return outer_table
        
    def unpack(self, data):
        all_data = self.struct.unpack(data)
        self.lc1_active = self.unpack_array(all_data[0:8])
        self.lc1_value = self.unpack_array(all_data[8:16])
        self.idl_active = self.unpack_array(all_data[16:24])
        self.idl_value = self.unpack_array(all_data[24:32])
        self.lc2_active = self.unpack_array(all_data[32:96])
        self.lc2_value = self.unpack_array(all_data[96:160])
        self.alt_active = self.unpack_array(all_data[160:224])
        self.alt_value = self.unpack_array(all_data[224:288])

    def to_string(self):
        return 'message.to_string() TDB'

class MpsManagerRequest():
    def __init__(self, request_type=100, thr_count=0, thr_table='lc1',
                 thr_index='t0', thr_integrator='i0',
                 thr_type='l', thr_value=0.0, device_id=0,
                 device_name='None', user_name='None', reason='None'):
        self.request_type = request_type # int
        self.thr_count = thr_count # int 
        self.device_id = device_id # int 
        self.device_name = device_name # 50 char
        self.user_name = user_name # 50 char
        self.reason = reason # 200 char

        self.format = "iii50s50s200s"
        self.struct = Struct(self.format)

    def size(self):
        return calcsize(self.format)

    def pack(self):
        return self.struct.pack(self.request_type,
                                self.thr_count,
                                self.device_id,
                                self.device_name,
                                self.user_name, 
                                self.reason)

    def unpack(self, data):
        self.request_type, self.thr_count, self.device_id, self.device_name, self.user_name, self.reason = self.struct.unpack(data)
        self.device_name = self.device_name.rstrip('\0')
        self.user_name = self.user_name.rstrip('\0')
        self.reason = self.reason.rstrip('\0')

    def to_string(self):
        return 'message.to_string() TDB'
