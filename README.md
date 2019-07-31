# MpsManager

The MpsManager provides an extra security layer for important MPS configuration parameters: analog device thresholds and bypasses. The MpsManager server writes/reads information to/from the MPS runtime configuration database (https://github.com/slaclab/mps_database/tree/master/runtime).

## Server

The MpsManager server needs information from the the configuration and runtime databases (which are located at $PHYSICS_TOP/mps_configuration/current).

The server is available through the specified TCP port, accepting requests for threshold and bypass operations. Currently the following requests are supported:

* Device check: verifies if a given device id or name is defined in the configuration/runtime databases (`mps_check_device.py` command).
* Change threshold: performs a threshold modification for a given device, changing the value in both runtime database and application IOC. The operation is recorded in history tables of the runtime database (`mps_change_threshold.py` command).
* Resore thresholds: restores threshold values from the runtime database to the IOC - this request is usually started by an application IOC after reboot. The request to restore thresholds is automatically initiated by the `l2MpsAsyn` EPICS module. If thresholds are not properly restored the MPS can't be enabled in for the IOC (MPS_EN PV). (`mps_restore_threshold.py` command).
* Get thresholds: returns the current threshold values for the specified device (`mps_get_threshold.py` command).


The following are the server command line options:

```
usage: mps_manager.py [-h] [--port [port]] [--log-file [log_file]] [-c] --hb
                      [PV]
                      db

Receive MPS status messages

positional arguments:
  db                    database file name (e.g. mps_gun_config.db)

optional arguments:
  -h, --help            show this help message and exit
  --port [port]         server port (default=3356)
  --log-file [log_file]
                        MpsManager log file base, e.g.
                        /data/mps_manager/server.log
  -c                    Print log messages to stdout
  --hb [PV]             PV used as heart beat by the server
```

## User Commands

### `mps_check_device.py`
Verifies if a given device name (e.g. BPMS26 or YAG1B) or id (this is the device database id) is defined in both the config and runtime databases. It returns the device name/device id and the type (analog or digital)

### `mps_change_threshold.py`
Request threshold change for an analog device. Multiple threshold types can be specified on the same command. The server will check the values (e.g. low < high) and try to connect to the threshold PVs that reside in the application IOC. If values are valid and PVs accessibly then server records the new values in the runtime database and update the thresholds.

When a threshold is changed it is enabled by in the application IOC. A threshold must be enabled in order to be evaluated in the application IOC.

The command also provides an option to disable specified thresholds.

### `mps_restore_threshold.py`
Restore the current thresholds for one MPS application (which includes one or more devices). For example, a BPM application may have one or two BPM devices.

### `mps_get_threshold.py`
Requests the current threshold values for a given device.
