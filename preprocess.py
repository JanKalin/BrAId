# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank

Removes all non-lane 1 vehicles and changes 'bus' to 'truck' for all "busses"
with groups other than 11, 12, 111 and 121.
"""

#%% Import stuff

import datetime
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.vehicle import Vehicle
from swm.utils import Progress

from locallib import load_metadata, save_metadata

#%% Load all files

print("Loading recognized_vehicles-ORIGINAL.json, ", end='')
sys.stdout.flush()
with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles-ORIGINAL.json")) as f:
    rvs = json.load(f)
print("done.")
sys.stdout.flush()

print("Loading *.nswd, ", end='')
sys.stdout.flush()
vehicles = Vehicle.from_txt_files(os.path.join(SCRIPT_DIR, "data", "*.nswd"), glob=True)
print("done.")
sys.stdout.flush()

metadatafile = os.path.join(SCRIPT_DIR, 'data', 'metadata.hdf5')

#%% Generate sets of files

print("Generating helper sets, ", end='')
sys.stdout.flush()
reconstructed = set([x.timestamp.timestamp() for x in vehicles if x.vehiclereconstructedflag()])
manually_changed = set([x.timestamp.timestamp() for x in vehicles if x.manuallychangedflags()])
fixed = set([x.timestamp.timestamp() for x in vehicles if x.qafixedflag()])
lane1 = set([x.timestamp.timestamp() for x in vehicles if not x.lane])
v2e_all = {x.timestamp.timestamp(): x.event_timestamp.timestamp() for x in vehicles}
v2e_lane1 = {x.timestamp.timestamp(): x.event_timestamp.timestamp() for x in vehicles if not x.lane}
multiple_vehicles = {}
for e in v2e_all.values():
    try:
        multiple_vehicles[e] += 1
    except:
        multiple_vehicles[e] = 0
print("done.")
sys.stdout.flush()

#%% Perhaps just set reconstructed and fixed flags

set_reconstructed_and_fixed_and_multiple_vehicle = False
set_manually_changed = True
countonly = False

noprogress = False

tochange = []
if set_reconstructed_and_fixed_and_multiple_vehicle or set_manually_changed:
    print("Setting reconstructed, fixed, manually fixed and multiple_vehicle flags")
    if not noprogress: progress = Progress("Processing {} photos... {{}}% ".format(len(rvs)), len(rvs))
    for rv in rvs:
        if not noprogress: progress.step()
        metadata = None
        
        if multiple_vehicles[v2e_all[rv['vehicle_timestamp']]] and set_reconstructed_and_fixed_and_multiple_vehicle:
            metadata = load_metadata(rv, metadatafile)
            try:
                metadata['errors']
            except:
                metadata['errors'] = {}
            metadata['errors']['multiple_vehicles'] = 2
            tochange.append(datetime.datetime.fromtimestamp(rv['vehicle_timestamp']).isoformat())
            
        if (rv['vehicle_timestamp'] in lane1
            and (rv['vehicle_timestamp'] in reconstructed or rv['vehicle_timestamp'] in fixed)
            and set_reconstructed_and_fixed_and_multiple_vehicle):
            if metadata is None:
                metadata = load_metadata(rv, metadatafile)
                try:
                    metadata['errors']
                except:
                    metadata['errors'] = {}
            if rv['vehicle_timestamp'] in reconstructed:
                metadata['errors']['reconstructed'] = 2
            if rv['vehicle_timestamp'] in fixed:
                metadata['errors']['fixed'] = 2

        if (rv['vehicle_timestamp'] in lane1
            and rv['vehicle_timestamp'] in manually_changed
            and set_manually_changed):
            if metadata is None:
                metadata = load_metadata(rv, metadatafile)
                try:
                    metadata['errors']
                except:
                    metadata['errors'] = {}
            metadata['errors']['fixed'] = 2

        if metadata is not None:
            if countonly:
                tochange.append(rv)
            else:
                save_metadata(rv, metadata, metadatafile)
            
    if countonly:
        print(f"Will set metadata for {len(tochange)} vehicles")
        
    raise SystemExit

#%% Now change busses for trucks


count = 0
noprogress = False
rvs_lane1 = []

if not noprogress: progress = Progress("Processing {} photos... {{}}% ".format(len(rvs)), len(rvs))
for rv in rvs:
    if not noprogress: progress.step()
    if not rv['vehicle_timestamp'] in lane1:
        continue
    rvs_lane1.append(rv)
    if rv['axle_groups'] in ['11', '12', '111', '121']:
        continue
    metadata = {'seen_by': None, 'changed_by': None}
    changed = 0
    for segment in rv['segments']:
        if segment['type'] == 'bus':
            try:
                metadata['type'][segment['box']['color']] = 'truck'
            except:
                metadata['type'] = {segment['box']['color']: 'truck'}
            changed += 1
    if changed:
        count += changed
        save_metadata(rv, metadata, metadatafile)

print("Found", count, "vehicles bus->truck")

#%% Save only lane 1 vehicles and v2e

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles.json"), 'w') as f:
    json.dump(rvs_lane1, f, indent=2)

with open(os.path.join(SCRIPT_DIR, 'data', "vehicle2event.json"), 'w') as f:
    json.dump(v2e_lane1, f, indent=2)
