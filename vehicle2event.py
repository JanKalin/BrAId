### Import stuff

import argparse
import datetime
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm import vehicle

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Generates vehicle2event.json", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--siwim_site", help="SiWIM site", default=r"S:\sites\original\AC_Sentvid_2012_2")

try:
    __IPYTHON__ # noqa
    args = parser.parse_args(r"".split())
except:
    args = parser.parse_args()


#%% Load NSWDs for all stages and add data to the dict

vehicle2event = {}
rps = ['rp01', 'rp02', 'rp03']
for rp in rps:
    print("Reading", rp)
    all_vehicles = vehicle.Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', 'braid.nswd'))
    vehicle2event.update({x.timestamp: x.event_timestamp for x in all_vehicles})
    
#%% Convert and save the file

with open(os.path.join(SCRIPT_DIR, 'data', "vehicle2event.json"), 'w') as f:
    json.dump({x.timestamp(): y.timestamp() for (x,y) in vehicle2event.items()}, f, indent=2)
