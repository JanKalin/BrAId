### Import stuff

import argparse
import getpass
import json
import math
import os
import sys

import h5py
import matplotlib.pyplot as plt
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Use data from events to generate data for NN training", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))

parser.add_argument("--dst", help="Destination file. Use 'NONE' to skip writing", required=True)
parser.add_argument("--sig", help="Destination signal file. Use 'NONE' to skip writing", required=True)
parser.add_argument("--plot", help="Plot data. For testing purposes", action='store_true')

parser.add_argument("--siwim_data_root", help="SiWIM data root", default=r"S:\sites\cestel")
parser.add_argument("--siwim_site", help="SiWIM site", required=True)
parser.add_argument("--siwim_rp_index", help="SiWIM index for data after reconstruction and before machine and manual changes", default=1, type=int)
parser.add_argument("--siwim_module", help="SiWIM output module", default='cf')

group_events = parser.add_mutually_exclusive_group(required=True)
group_events.add_argument("--events_glob", help="Glob for selecting events", nargs='+')
group_events.add_argument("--events_list", help="List for selecting events")

group_channels = parser.add_mutually_exclusive_group(required=True)
group_channels.add_argument("--number_of_channels", help="Number of channels", type=int)
group_channels.add_argument("--channels", help="Channels to include, 1-based", type=int, nargs='+')

parser.add_argument("--subst", help="Substitute stages, e.g., live -> rp01, in list", nargs=2, type=int)


try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        try:
            args = parser.parse_args(r"--siwim_site Moste_18_MM --dst nn_extracted_pulses-Moste_18_MM.json --sig nn_extracted_signals-Moste_18_MM.hdf5"
                                     " --events_list for_nn.list --siwim_rp_index 1 --subst 0 1 --number 16".split())
        except:
            raise SystemExit()
    else:
        raise SystemExit()
except:
    args = parser.parse_args()

fs = FS(args.siwim_data_root, args.siwim_site, args.siwim_rp_index, args.siwim_module)

#%% Functions

def sigfig(x, n):
    return float(f"{x:.{n}g}")

def compare(a, b):
    return (a > b) - (a < b)

#%% Read the vehicles file 

if args.sig != "NONE":
    with h5py.File(os.path.join(args.data_dir, args.sig), 'w') as f:
        pass

items = []

if args.events_glob: 
    filenames = fs.multiglob(args.events_glob, recurse=True)
else:
    with open(fs.fullname(os.path.join('usr', 'lists', fs.rpstring(), args.events_list), fromsite=True)) as f:
        filenames = [x.strip() for x in f.readlines()]
    if args.subst:
        filenames = [x.replace(fs.rpstring(args.subst[0]), fs.rpstring(args.subst[1])) for x in filenames]

#%%

output_vehicles = []
multiple_vehicles = []

class MyException(Exception):
    pass

if args.number_of_channels:
    channels = [x for x in range(args.number_of_channels)]
else:
    channels = [x - 1 for x in args.channels]

for filename in (filenames if len(filenames) < 10 else tqdm(filenames)):
    
    # Read singled detected and weighed vehicle from rp01
    event = read_file(fs.fullname(filename))
    vehicles = {}
    try:
        for label, vehicles_list in [('detected', event.detected_vehicles), ('weighed', event.weighed_vehicles)]:
            if len(vehicles_list) != 1:
                raise MyException(os.path.basename(filename))
            vehicles[label] = vehicles_list[0]
    except MyException as e:
        multiple_vehicles.append(str(e))
        continue
    if vehicles['detected'].timestamp != vehicles['weighed'].timestamp:
        print(f"Mismatched detected and weighed vehicles in event: {os.path.basename(filename)}")
        continue
    
    # Add data to item
    weighed = vehicles['weighed']
    item = {}
    item['ts'] = math.trunc(weighed.timestamp.timestamp()*1000)/1000
    item['ts_str'] = datetime2ts(weighed.timestamp)
    item['ets'] = math.trunc(weighed.event_timestamp.timestamp()*1000)/1000
    item['ets_str'] = datetime2ts(weighed.event_timestamp)
    item['v'] = sigfig(abs(weighed.v()), 6)
    item['vehicle'] = {}
    for key, vehicle in vehicles.items():
        item['vehicle'][key] = {'axle_groups': vehicles[key].groups2str(),
                                'axle_distance': [sigfig(x, 6) for x in vehicles[key].axle_distance],
                                'axle_pulses': [int(x.t0) for x in vehicles[key].axle]}

    # Here we can also see what has changed between detected and weighed vehicles        
    cmp = compare(len(item['vehicle']['detected']['axle_distance']), len(item['vehicle']['weighed']['axle_distance']))
    if not cmp:
        distance_op = 'nop' if item['vehicle']['detected']['axle_distance'] == item['vehicle']['detected']['axle_distance'] else 'mov'
    else:
        distance_op = 'add' if cmp < 0 else 'del'
    item['vehicle']['weighed']['distance_op'] = distance_op
    
    # Rearrange data
    item['vehicle'] = {key: item['vehicle'][key] for key in ['detected', 'weighed']}

    # Save it
    output_vehicles.append(item)
    
    # And perhaps save signal
    if args.sig != 'NONE':
        diags = event.module_trace.last_module('vehicle_fad').diags[0][1].a[0]
        with h5py.File(os.path.join(args.data_dir, args.sig), 'a') as f:
            grp = f.create_group(item['ts_str'])
            _as = [event.acqdata.a[idx] for idx in channels]
            for a in _as:
                grp.create_dataset(a.short_description, data=a.data - a.offset(), compression="gzip", compression_opts=4, shuffle=True)
                if args.plot: plt.plot(a.data - a.offset(), label=a.short_description)
                
        if args.plot:
            plt.title(item['ets_str'])
            plt.legend()
            plt.show()
    
if args.dst != 'NONE':
    with open(os.path.join(args.data_dir, args.dst), 'w') as f:
        json.dump(output_vehicles, f, indent=2)

if multiple_vehicles:
    print(f"Multiple vehicles ignored in: {', '.join(multiple_vehicles)}")