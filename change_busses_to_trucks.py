# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank
"""

#%% Import stuff


import datetime
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from locallib import save_metadata
from swm.utils import Progress

#%% Load all files

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles.json")) as f:
    rvs = json.load(f)
for rv in rvs:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])

#%% Now change busses for trucks

metadata = {'seen_by': None, 'changed_by': (datetime.datetime.now().timestamp(), "SCRIPT"), 'vehicle_type': 'truck'}
datadir = os.path.join(SCRIPT_DIR, 'data')

progress = Progress("Processing {} events... {{}}% ".format(len(rvs)), len(rvs))
for rv in rvs:
    progress.step()
    if rv['vehicle_type'] == 'truck' or rv['axle_groups'] in ['11', '12', '111']:
        continue
    save_metadata(rv, metadata, datadir)