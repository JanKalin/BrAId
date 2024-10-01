#%% Import stuff

import argparse
import datetime
import glob
import json

import h5py
from prettytable import PrettyTable

from swm.utils import Progress


#%% Args

parser = argparse.ArgumentParser(description="Find latest changed_by/seen_by", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("src", help="Files, can use glob", nargs='+')

try:
    __IPYTHON__
    args = parser.parse_args("data\\*.hdf5".split())
except:
    args = parser.parse_args()

#%% Get filenames

filenames = sorted({item for sublist in [glob.glob(x) for x in args.src] for item in sublist})
if not filenames:
    raise ValueError("No files selected")

#%% Get values

table = PrettyTable(['file', 'last changed', 'last seen'])
table.align = 'l'

for filename in filenames:
    try:
        last_changed_by = None
        last_seen_by = None
        with h5py.File(filename, 'r') as f:
            count = 0
            for group in f:
                count += 1
            progress = Progress(f"{filename}, {count} groups of data: {{}}%", count)
            for grp in f:
                progress.step()
                for veh in f[grp]:
                    metadata = json.loads(f[f"{grp}/{veh}"].asstr()[()])
                    try:
                        if not last_changed_by:
                            last_changed_by = metadata['changed_by']
                        if metadata['changed_by'][0] > last_changed_by[0]:
                            last_changed_by = metadata['changed_by']
                    except (KeyError, TypeError):
                        pass
                    try:
                        if not last_seen_by:
                            last_seen_by = metadata['seen_by']
                        if metadata['seen_by'][0] > last_seen_by[0]:
                            last_seen_by = metadata['seen_by']
                    except (KeyError, TypeError):
                        pass
        if last_changed_by:
            last_changed_by = f"{datetime.datetime.fromtimestamp(last_changed_by[0])} by {last_changed_by[1]}"
        if last_seen_by:
            last_seen_by = f"{datetime.datetime.fromtimestamp(last_seen_by[0])} by {last_seen_by[1]}"
        table.add_row([filename, last_changed_by, last_seen_by])
    except:
        raise
        table.add_row([filename] + ['']*2)
        
print(table)
