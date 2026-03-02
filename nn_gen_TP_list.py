### Import stuff

import argparse
import getpass
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Get the list of 113 vehicles from the normalised data", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src-json", help="Source file vehicles in the data directory", default="nn_normalised_pulses.json")
parser.add_argument("--input-stage", help="Input stage and module for events", default="/rp41/cf")
parser.add_argument("--dst-list", help="Output list", default=os.path.join(SCRIPT_DIR, 'data', "TP.list"))

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
    
#%% Find 113 vehicles

etss = [f"{args.input_stage}/{x['ets_str']}.event" for x in items if x['vehicle'][RELEVANT_STAGE]['axle_groups'] == '113']
with open(args.dst_list, 'w') as f:
    f.write('\n'.join(etss))

