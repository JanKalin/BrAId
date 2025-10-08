### Import stuff

import argparse
import getpass
import json
import os
import sys

import h5py
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts, Progress

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Use data from `nn_vehicles.json` to generate data for NN training", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src", help="Source file, output `from nn_vehicles.py`, in the data directory", default="nn_vehicles.json")
parser.add_argument("--dst", help="Destination file", default="nn_axles.json")
parser.add_argument("--sig", help="Destination signal file. Use 'NONE' to skip writing", default="nn_signals.hdf5")
parser.add_argument("--plot", help="Plot data. For testing purposes", action='store_true')

parser.add_argument("--siwim_data_root", help="SiWIM data root", default=r"E:\sites\original")
parser.add_argument("--siwim_site", help="SiWIM site", default="AC_Sentvid_2012_2")
parser.add_argument("--siwim_original_index", help="SiWIM index for data after reconstruction and before machine and manual changes", default=1)
parser.add_argument("--siwim_vehicle_fad_index", help="SiWIM index for data with vehicle_fad signals", default=41)

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--sig NONE".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

fs1 = FS(args.siwim_data_root, args.siwim_site, args.siwim_original_index, 'cf')
fs2 = FS(args.siwim_data_root, args.siwim_site, args.siwim_vehicle_fad_index, 'cf')

#%% Functions

def sigfig(x, n):
    return float(f"{x:.{n}g}")

def compare(a, b):
    return (a > b) - (a < b)

#%% Read the vehicles file 

if args.sig != "NONE":
    with h5py.File(os.path.join(args.data_dir, args.sig), 'w') as f:
        pass

with open(os.path.join(args.data_dir, args.src)) as f:
    input_vehicles = json.load(f)
    
output_vehicles = []

progress = Progress("Processing {} events... {{}}% ".format(len(input_vehicles)), len(input_vehicles))
for item in input_vehicles:
    progress.step()
    
    # Read singled detected and weighed vehicle from rp01
    filename = fs1.fullname(f"{item['ets_str']}.event")
    event = read_file(filename)
    vehicles = {}
    for label, vehicles_list in [('detected', event.detected_vehicles), ('weighed', event.weighed_vehicles)]:
        try:
            vehicles[label] = [x for x in vehicles_list if datetime2ts(x.timestamp) == item['ts_str']][0]
        except Exception as e:
            print(f"Could not find vehicle {item['ts_str']} in {label}_vehicles in {os.path.split(filename)[1]}: {e}")
            continue
    
    # Add data to item
    item['vehicle']['detected'] = {'axle_groups': vehicles['detected'].groups2str(),
                                   'axle_distance': [sigfig(x, 6) for x in vehicles['detected'].axle_distance]}
    for key, vehicle in vehicles.items():
        item['vehicle'][key]['axle_pulses'] = [int(x.t0) for x in vehicle.axle]

    # Here we can also see what has changed between detected and weighed vehicles        
    cmp = compare(len(item['vehicle']['detected']['axle_distance']), len(item['vehicle']['weighed']['axle_distance']))
    if not cmp:
        distance_op = 'nop' if item['vehicle']['detected']['axle_distance'] == item['vehicle']['detected']['axle_distance'] else 'mov'
    else:
        distance_op = 'add' if cmp < 0 else 'del'
    item['vehicle']['weighed']['distance_op'] = distance_op
    
    # Rearrange data
    item['vehicle'] = {key: item['vehicle'][key] for key in ['detected', 'weighed', 'final']}

    # Save it
    output_vehicles.append(item)
    
    # And perhaps save signal
    if args.sig != 'NONE':
        filename = fs2.fullname(f"{item['ets_str']}.event")
        event = read_file(filename)
        diags = event.module_trace.last_module('vehicle_fad').diags[0][1].a[0]
        with h5py.File(os.path.join(args.data_dir, args.sig), 'a') as f:
            grp = f.create_group(item['ts_str'])
            _as = [event.acqdata.a[6], event.acqdata.a[7]] + event.module_trace.last_module('vehicle_fad').diags[0][1].a
            for a in _as:
                grp.create_dataset(a.short_description, data=a.data - a.offset(), compression="gzip", compression_opts=4, shuffle=True)
                if args.plot: plt.plot(a.data - a.offset(), label=a.short_description)
                
        if args.plot:
            plt.title(item['ets_str'])
            plt.legend()
            plt.show()
    
with open(os.path.join(args.data_dir, args.dst), 'w') as f:
    json.dump(output_vehicles, f, indent=2)
