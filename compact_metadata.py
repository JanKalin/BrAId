#%% Import stuff

import json
import os

import h5py

from locallib import load_metadata, save_metadata
from swm.utils import Progress

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
srcfile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")
dstfile = os.path.join(SCRIPT_DIR, "data", "metadata_compact.hdf5")

#%% Count vehicles in input file

with h5py.File(srcfile, 'r') as src:
    src_count = 0
    for grp in src:
        for veh in src[grp]:
            src_count += 1
    print(f"src vehicles: {src_count}")
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
    
