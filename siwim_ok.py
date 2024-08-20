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
cannot_label = 0
groups_empty = 0
groups_match = 0
ok = {}
siwim_grp = {}
true_grp = {}

with h5py.File(srcfile, 'r') as src:
    progress = Progress(f"{len(src)} groups of data: {{}}%", len(src))
    for grp in src:
        siwim_grp[grp] = {'ok': 0, 'no': 0, 'to': {}}
        progress.step()
        for photo_id in src[grp]:
            count += 1
            data = json.loads(src[f"{grp}/{photo_id}"].asstr()[()])
            
            # If it was fixed with fix or manually, it's not ok
            try:
                if data['errors']['fixed']:
                    fixed += 1
                    continue
            except KeyError:
                pass
            
            # If it wasn't seen by anyone, skip
            try:
                if not data['seen_by']:
                    unseen += 1
                    continue
            except KeyError:
                unseen += 1
                continue
            seen += 1
        
            # If it has cannot label, skip
            try:
                if data['errors']['cannot_label']:
                    cannot_label += 1
                    continue
            except KeyError:
                pass
        
            # Groups empty
            try:
                data['axle_groups']
            except:
                ok[photo_id] = True
                siwim_grp[grp]['ok'] += 1
                try:
                    true_grp[grp]
                except KeyError:
                    true_grp[grp] = {'ok': 0, 'no': 0, 'from': {}}
                true_grp[grp]['ok'] += 1
                groups_empty += 1
                continue
            
            # Done
            ok[photo_id] = data['axle_groups'] == grp
            groups_match += ok[photo_id]
            siwim_grp[grp]['ok' if ok[photo_id] else 'no'] += 1
            try:
                true_grp[data['axle_groups']]
            except KeyError:
                true_grp[data['axle_groups']] = {'ok': 0, 'no': 0, 'from': {}}
            true_grp[data['axle_groups']]['ok' if ok[photo_id] else 'no'] += 1

            if not ok[photo_id]:
                try:
                    siwim_grp[grp]['to'][data['axle_groups']] += 1
                except KeyError:
                    siwim_grp[grp]['to'][data['axle_groups']] = 1
                try:
                    true_grp[data['axle_groups']]['from'][grp] += 1
                except KeyError:
                    true_grp[data['axle_groups']]['from'][grp] = 1
                    
#%% Save

with open("data/siwim_ok.json", 'w') as f:
    json.dump(ok, f, indent=2)

with open("data/siwim_per_grp.json", 'w') as f:
    json.dump(siwim_grp, f, indent=2)
    
with open("data/true_per_grp.json", 'w') as f:
    json.dump(true_grp, f, indent=2)
    
