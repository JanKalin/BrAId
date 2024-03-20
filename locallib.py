# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 12:00:50 2024

@author: jank
"""

#%% Import stuff

import datetime
import getpass
import json
import math
import os
import sys
import time
import winsound

import h5py

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getpass.getuser() == 'jank':
    sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.utils import datetime2ts

#%% SiWIM photo and data paths

def pngpath(root, v):
    """Returns path for PNG file"""
    return os.path.join(root, v['vehicle_type'], v['axle_groups'], f"{v['photo_id']}-{v['vehicle_type']}-{v['axle_groups']}-{math.floor(v['type_probability']):.0f}.png")

def event_timestamp(v, v2e):
    """Returns event timestamp from vehicle and v2e dict"""
    return datetime.datetime.fromtimestamp(v2e[str(v['vehicle_timestamp'].timestamp())])

def eventpath(fs, v, v2e):
    """Returns event path using FS() and vehicle"""
    ts = datetime2ts(event_timestamp(v, v2e))
    return fs.fullname(ts + ".event")

def load_metadata(rv, filename, exists=False):
    """Loads metadata for recognised vehicle"""
    try:
        with h5py.File(filename, 'r') as f:
            result = json.loads(f[f"{rv['vehicle_type']}/{rv['axle_groups']}/{rv['photo_id']}"].asstr()[()])
            return True if exists else result
    except:
        return False if exists else {'seen_by': None, 'changed_by': None}
    
def save_metadata(rv, metadata, filename, timeout=None):
    """Saves metadata for recognised vehicle"""
    f = None
    wait_until = datetime.datetime.now()
    if timeout:
         wait_until += datetime.timedelta(seconds=timeout)
    try:
        while True:
            try:
                f = h5py.File(filename, 'a')
                break
            except:
                if datetime.datetime.now() < wait_until:
                    time.sleep(0.1)
                    continue
                else:
                    raise RuntimeError(filename)
        try:
            grp = f.require_group(f"{rv['vehicle_type']}/{rv['axle_groups']}")
        except TypeError:
            grp = f[f"{rv['vehicle_type']}/{rv['axle_groups']}"]
        try:
            grp[str(rv['photo_id'])] = json.dumps(metadata)
        except:
            data = grp[str(rv['photo_id'])]
            data[...] = json.dumps(metadata)
    finally:
        if f is not None:
            f.close()

def count_vehicles(rvsd):
    return {vehicle_type: [(key, len(item)) for (key, item) in sorted(entries.items(), key=lambda x: len(x[1]), reverse=True)]
            for (vehicle_type, entries) in rvsd.items()}  

def beep():
    winsound.Beep(1670, 100)

