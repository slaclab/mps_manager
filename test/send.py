#!/usr/bin/env python

import socket
from mps_manager_protocol import *

host='lcls-dev3'
udp_ip='134.79.216.240'
port=1975

message = MpsManagerRequest()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
message.type = '{}'.format(MpsManagerRequestType.RESTORE_APP_THRESHOLDS.value)
sock.sendto(message, (host, port))

message.type = '{}'.format(MpsManagerRequestType.DEVICE_CHECK.value)
sock.sendto(message, (host, port))
