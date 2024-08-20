#%% Import stuff

import json
import os

import h5py

from swm.utils import Progress

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
srcfile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")

#%% Analyse data

count = 0
fixed = 0
unseen = 0
seen = 0
ok = {}

with h5py.File(srcfile, 'r') as src:
    progress = Progress(f"{len(src)} groups of data: {{}}%", len(src))
    for grp in src:
        progress.step()
        for photo_id in src[grp]:
            count += 1
            data = json.loads(src[f"{grp}/{photo_id}"].asstr()[()])
            
            # If it was fixed with fix or manually, it's not ok
            try:
                if data['errors']['fixed']:
                    ok[photo_id] = False
                    fixed += 1
                    continue
            except:
                pass
            
            # If it wasn't seen by anyone, skip
            try:
                if not data['seen_by']:
                    unseen += 1
                    continue
            except:
                unseen += 1
                continue
            seen += 1
        
            # Groups empty
            try:
                data['groups']
                groups_empty = False
            except:
                groups_empty = True
            
            # Done
            ok[photo_id] = groups_empty or data['groups'] == grp
                    
#%% Save

