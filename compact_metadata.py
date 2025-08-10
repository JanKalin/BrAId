#%% Import stuff

import json
import os
import sys

import h5py

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.utils import Progress

srcfile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")
dstfile = os.path.join(SCRIPT_DIR, "data", "metadata_compact.hdf5")

#%% Count vehicles in input file

seen = [0, 0]

with h5py.File(srcfile, 'r') as src:
    src_count = 0
    for grp in src:
        for veh in src[grp]:
            src_count += 1
            seen[json.loads(src[f"{grp}/{veh}"].asstr()[()])['seen_by'] is not None] += 1
    print(f"src vehicles: {src_count}, seen: {seen[1]}, unseen: {seen[0]}, total: {seen[0] + seen[1]}")
    print("Last photo", grp, veh, src[f"{grp}/{veh}"].asstr()[()])
    
#%% Copy data

with h5py.File(srcfile, 'r') as src, h5py.File(dstfile, 'w') as dst:
    count = 0
    for group in src:
        count += 1
    progress = Progress(f"{count} groups of data: {{}}%", count)
    for group in src:
        progress.step()
        src.copy(src[group], dst["/"])
        
        
#%% Count vehicles in output file

with h5py.File(dstfile, 'r') as dst:
    dst_count = 0
    for grp in dst:
        for veh in dst[grp]:
            dst_count += 1
    print(f"dst vehicles: {dst_count}")
    print("Last photo", grp, veh, dst[f"{grp}/{veh}"].asstr()[()])
    
