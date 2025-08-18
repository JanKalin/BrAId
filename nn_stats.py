### Import stuff

import argparse
import getpass
import json
import os
import sys
from tabulate import tabulate

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Get some stats from nn_pulses.jsob", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src", help="Source file", default="nn_pulses.json")

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

#%% Read the vehicles file 

with open(os.path.join(args.data_dir, args.src)) as f:
    items = json.load(f)
    
#%% Get stats

count = {x: {True: 0, False: 0} for x in ['detected', 'weighed', 'final']}
raised = 0
no_rcn = 0

for item in items:
    if not item['photo_match'] and item['raised_axles']:
        raised += 1
        continue
    if item['vehicle']['weighed']['distance_op'] == 'nop':
        no_rcn += 1
        continue
    
    try:
        axle_groups = item['axle_groups']
    except:
        axle_groups = item['vehicle']['final']['axle_groups']
    for stage in count.keys():
        count[stage][item['vehicle'][stage]['axle_groups'] == axle_groups] += 1

print(f"raised: {raised}")
print(f"no_rcn: {no_rcn}")
print()
rows = [[key, value[True], value[False]] for (key, value) in count.items()]
print(tabulate(rows, headers=['stage', 'ok', 'no'], tablefmt="github"))