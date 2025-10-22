### Import stuff

import argparse
import getpass
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Generates some first pulse stats", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src-json", help="Source file vehicles in the data directory", default="nn_normalised_pulses.json")

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

RELEVANT_STAGE = 'final'

#%% Read the json file

with open(os.path.join(args.data_dir, args.src_json)) as f:
    items = json.load(f)
    
#%% Data stats

firsts = np.array([x['vehicle'][RELEVANT_STAGE]['axle_pulses'][0] for x in items])
etss = [x['ets_str'] for x in items]

print(f"{len(firsts)} vehicles, first pulse positions are {np.mean(firsts)} \u00B1 {np.std(firsts):.1f}, min: {np.min(firsts)}, max: {np.max(firsts)}")

#%% Number of vehicles

ok = len([x for x in items if x['photo_match']])
raised = len([x for x in items if not x['photo_match'] and x.get('raised_axles')])
no = len([x for x in items if not x['photo_match'] and not x.get('raised_axles')])

print(f"{len(items)} all vehicles, {ok} ok training vehicles, {raised} not ok with raised axles and {no} not ok with no raised axles")


#%% Plot a histogram

plt.hist(firsts, bins=50, log=True)