#/usr/bin/python3
#%% Import stuff

import os

import h5py

from swm.utils import Progress

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
srcfile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")
dstfile = os.path.join(SCRIPT_DIR, "data", "metadata_clean.hdf5")

#%% Count photos in input file

with h5py.File(srcfile, 'r') as src:
    src_count = 0
    progress = Progress(f"Counting photos in src, {len(src.keys())} groups of data: {{}}%", len(src.keys()))
    for grp in src:
        progress.step()
        for photo_id in src[grp]:
            src_count += 1
    print(f"Count: {src_count}, last photo {grp}/{photo_id}:", src[f"{grp}/{photo_id}"].asstr()[()])
    
#%% Copy data

problems = []
with h5py.File(srcfile, 'r') as src, h5py.File(dstfile, 'w') as dst:
    progress = Progress(f"Copying {src_count} photos from src to dst: {{}}%", src_count)
    for src_grp in src:
        dst_grp = dst.require_group(f"{src_grp}")
        for photo_id in src[src_grp]:
            progress.step()
            try:
                metadata = src[f"{src_grp}/{photo_id}"].asstr()[()]
                dst_grp[photo_id] = metadata
            except:
                problems.append([src_grp, photo_id])

if problems:
    print(problems)
    with open("problems.txt", 'w') as f:
        f.writelines(str(problems))
        
#%% Count photos in output file

with h5py.File(dstfile, 'r') as dst:
    dst_count = 0
    progress = Progress(f"Counting photos in dst, {len(dst.keys())} groups of data: {{}}%", len(dst.keys()))
    for grp in dst:
        progress.step()
        for veh in dst[grp]:
            dst_count += 1
    print(f"Count: {dst_count}, last photo {grp}/{photo_id}:", dst[f"{grp}/{photo_id}"].asstr()[()])
    
