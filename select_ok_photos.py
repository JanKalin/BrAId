# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank
"""

#%% Import stuff

import bisect
import datetime
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.vehicle import Vehicle
from swm.utils import Progress

#%% Load all files

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles-ORIGINAL.json")) as f:
    rvs = json.load(f)
for rv in rvs:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    
vehicles = Vehicle.from_txt_files(os.path.join(SCRIPT_DIR, 'data', "201?.nswd"), glob=True)

#%% Get filter

fromdate = datetime.datetime(2014, 3, 5)
todate = datetime.datetime(2014, 9, 3)

fltr = sorted([x.timestamp for x in vehicles if x.timestamp >= fromdate and x.timestamp <= todate and not x.lane])

v2e = {(x.timestamp, x.lane): x.event_timestamp for x in vehicles}

#%% Filter and save

def index(a, x):
    i = bisect.bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i
    raise ValueError

vehicle2event = {}    
progress = Progress("Processing {} photos... {{}}% ".format(len(rvs)), len(rvs))
remaining = []
for rv in rvs:
    progress.step()
    try:
        index(fltr, rv['vehicle_timestamp'])
        remaining.append(rv)
        vehicle2event[rv['vehicle_timestamp']] = v2e[(rv['vehicle_timestamp'], 0)]
    except ValueError:
        pass

#%% Save remaining vehicles

for rv in remaining:
    rv['vehicle_timestamp'] = rv['vehicle_timestamp'].timestamp()
    rv['photo_timestamp'] = rv['photo_timestamp'].timestamp()
    
with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles.json"), 'w') as f:
    json.dump(remaining, f)


#%%

raise RuntimeError("Please use the script `vehicle2event.py` to generate `vehicle2event.json`")

# remaining_v2e = {key.timestamp(): value.timestamp() for (key, value) in vehicle2event.items()}
# with open(os.path.join(SCRIPT_DIR, 'data', "vehicle2event.json"), 'w') as f:
#     json.dump(remaining_v2e, f)
