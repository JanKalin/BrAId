### Import stuff

import argparse
import getpass
import json
import os
import sys

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Get errors for 113 from nn_pulses.json", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
    
#%% Remove all but 113 without raised axles

semis = [x for x in items if (x['eligible']
                              and ((x['photo_match'] and x['vehicle']['final']['axle_groups'] == '113')
                                   or (not x['photo_match'] and x['axle_groups'] == '113' and not x['raised_axles'])))]

with open(os.path.join(args.data_dir, "nn_semis.json"), 'w') as f:
    json.dump(semis, f, indent=2)
    
#%% Now get average axle distance for the correctly identified semis

ads = np.array([x['vehicle']['final']['axle_distance'] for x in semis if x['photo_match']])
mean_ads = np.mean(ads, axis=0)