### Import stuff

import argparse
import getpass
import gc
import h5py
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.utils import ts2datetime

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# raise SystemExit("Do not run this script indiscriminately or you will overwrite data!")

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Normalises and shifs signals", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src-hdf5", help="Source signals file in the data directory", required=True)
parser.add_argument("--src-json", help="Source file vehicles in the data directory", required=True)
parser.add_argument("--dst-hdf5", help="Destination signals file in the data directory. Use NONE to prevent writing", required=True)
parser.add_argument("--dst-json", help="Destination vehicles file in the data directory. Use NONE to prevent writing", required=True)
parser.add_argument("--recognized-vehicles-json", help="Needed for option --photo-ids", default="recognized_vehicles.json")
parser.add_argument("--vehicle-to-event-json", help="Needed for option --photo-ids", default="vehicle2event.json")

parser.add_argument("--admp", help="ADMP signal name", required=True)
parser.add_argument("--dx", help="Resampled data spatial resolution", type=float, default=0.05)
parser.add_argument("--threshold", help="Threshold for search of the positive region", type=float, default=0.20)
parser.add_argument("--expand", help="Expand positive region by this many metres to left and right", type=float, nargs=2, default=[8, 16])

grp_selection = parser.add_mutually_exclusive_group()
grp_selection.add_argument("--photo-ids", help="Process one or more vehicles based on photo ID", nargs='+')
grp_selection.add_argument("--ets", help="Process one or more vehicles based on event timestamp", nargs='+')
grp_selection.add_argument("--items", help="Process these items. Default is to process all files", type=int, nargs=2)

parser.add_argument("--plot", help="Plot overlayed --admp signals and first --plot pulses", type=int)
parser.add_argument("--signal-plot", help="Plots all signals in each loaded file", action='store_true')
parser.add_argument("--legend", help="Add label to plot (use for small number of items", action='store_true')

parser.add_argument("--admp-only", help="Process just the 11admp signal", action='store_true')
parser.add_argument("--debug", help="Various debugging", action='store_true');

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--plot 1 --src-hdf5 nn_extracted_signals-Moste_18_MM.hdf5 --src-json nn_extracted_pulses-Moste_18_MM.json "
                                 " --dst-hdf5 nn_extracted_signals-normalised-Moste_18_MM.hdf5 --dst-json nn_extracted_pulses-normalised-Moste_18_MM.json ".split() + ['--admp', 's212 a21'])
    else:
        raise Exception
except:
    args = parser.parse_args()

SAMPLING_RATE = 512

#%% Define my exception that causes skipping this item

class SkipItem(Exception):
    """Just signals a skip"""
    pass

#%% Read the json file(s)

with open(os.path.join(args.data_dir, args.src_json)) as f:
    items = json.load(f)
    
events = None

if args.photo_ids:
    with open(os.path.join(args.data_dir, args.recognized_vehicles_json)) as f:
        photo2ts = {str(x['photo_id']): x['vehicle_timestamp'] for x in json.load(f)}
    with open(os.path.join(args.data_dir, args.vehicle_to_event_json)) as f:
        veh2event = json.load(f)
    events = [veh2event[str(photo2ts[x])] for x in args.photo_ids]

if args.ets:
    events = [ts2datetime(x).timestamp() for x in args.ets]
    
if events:
    items = [x for x in items if x['ets'] in events]
    if not items:
        raise ValueError(f"{args.ets} not found in {args.src_json}")
    
#%% Now process the data

# Perhaps plot
if args.plot:
    summary_fig, (summary_ax1, summary_ax2) = plt.subplots(2, 1, figsize = (8, 6), sharex=True)

# Init file and list of items
if args.dst_hdf5 != "NONE":
    with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'w') as f: pass
new_items = []
no_zero = []
misplaced = []
skipped = []

# Loop over all items     
for idx, item in enumerate(tqdm(items[args.items[0]:args.items[1]] if args.items else items, ncols=60, mininterval=1, ascii=True)):
    if not idx % 1000:
        gc.collect()
    v = item['v']
    try:
        with h5py.File(os.path.join(args.data_dir, args.src_hdf5), 'r') as f:
            src_grp = f[item['ts_str']]
            dataset_names = [name for name, obj in src_grp.items() if isinstance(obj, h5py.Dataset)]
            if args.admp not in dataset_names:
                raise RuntimeError(f"Missing dataset {args.admp}' in {item['ts_str']}")
            if args.dst_hdf5 != "NONE":
                with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'a') as g:
                    g.create_group(item['ts_str'])
    
            # Clear interval
            (p, q) = (None, None)
    
            # Perhaps plot all signals
            if args.signal_plot:
                fig_sig, ax_sig = plt.subplots(1, 1, figsize=(8, 6))

            # Record maxes
            item['max'] = {}
    
            # Process all signals
            for jdx, dataset_name in enumerate([args.admp] + [x for x in dataset_names if x != args.admp]):
                
                # Shortcut
                data = src_grp[dataset_name]
                if args.debug:
                    data_old = np.array(data)
                    
                # Determine resample values
                if not jdx:
                    a_old = np.array(range(len(data)))
                    dx_dt = args.dx*SAMPLING_RATE/v
                    item['dx/dt'] = dx_dt
                    x_max = float(f"{(np.floor(v*len(data)/SAMPLING_RATE/args.dx) * args.dx):.3f}")
                    a_new = np.arange(0, x_max, args.dx)/v*SAMPLING_RATE
                
                # Resample and normalise
                data_new = np.interp(a_new, a_old, data)
                _max = data_new.max()
                data_new /= _max
                item['max'][dataset_name] = _max
    
                # Determine the useful interval from the first signal, args.admp
                if not jdx:
                    above = np.where(data_new > args.threshold)[0]
                    try:
                        p = np.where((data_new[:above[0]] <= 0))[0][-1] + 1
                        q = np.where((data_new[above[-1]:] <= 0))[0][0] + above[-1]
                        p = max(int(p - args.expand[0]/args.dx), 0)
                        q = min(int(q + args.expand[1]/args.dx), len(data_new))
                    except IndexError:
                        no_zero.append(f"{item['ets_str']}\t{idx + (args.items[0] if args.items else 0)}")
                        raise SkipItem()
    
                    # Adjust the pulses and flag an error if they are too soon
                    stages = ['detected', 'weighed']
                    try:
                        item['vehicle']['final']
                        stages.append('final')
                    except:
                        pass
                    for stage in stages:
                        item['vehicle'][stage]['axle_pulses'] = [int(x/dx_dt - p) for x in item['vehicle'][stage]['axle_pulses']]
                    if item['vehicle'][stages[-1]]['axle_pulses'][0] < 160 or item['vehicle'][stages[-1]]['axle_pulses'][0] > 212:
                        misplaced.append(f"{item['ets_str']}\t{idx + (args.items[0] if args.items else 0)}\t{item['vehicle'][stages[-1]]['axle_pulses'][0]}")
                        raise SkipItem()
                    else:
                        new_items.append(item)
                        
                # Now write the slice of the new data
                data_slice = data_new[p:q]
                if args.dst_hdf5 != "NONE":
                    with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'a') as g:
                        g[item['ts_str']].create_dataset(dataset_name, data=data_slice, compression="gzip", compression_opts=4, shuffle=True)
                
                # And perhaps plot the first signal
                if not jdx and args.plot:
                    data_plot = data_slice
                if args.signal_plot:
                    ax_sig.plot(data_slice, label=dataset_name)
                    
                # Perhaps just this channel
                if jdx and args.admp_only:
                    break
                
            
            # If we don't have the interval, something was wrong
            if not p or not q:
                continue
                    
            # And prehaps plot the final pulses
            if args.plot:
                # fig, (ax1, ax2) = plt.subplots(2, 1, figsize = (8, 6), sharex=True)
                # ax1.plot(data_plot, label=item['ets_str'])
                # ax1.axhline(y=0, color='k', linestyle=':')
                # a = np.zeros(len(data_plot), dtype=int)
                # a[item['vehicle'][stages[-1]]['axle_pulses'][:args.plot]] = 1
                # ax2.plot(a, label=item['ets_str'])
                # ax1.legend()
                
                summary_ax1.plot(data_plot, label=item['ets_str'])
                a = np.zeros(len(data_plot), dtype=int)
                a[item['vehicle'][stages[-1]]['axle_pulses'][:args.plot]] = 1
                summary_ax2.plot(a, label=item['ets_str'])
                
            # And all signals
            if args.signal_plot:
                if args.legend:
                    ax_sig.legend()
                plt.show()
                
    except SkipItem:
        skipped.append(item['ets_str'])
        continue
            
# Now just write the changed JSON
if args.dst_json != 'NONE':
    with open(os.path.join(args.data_dir, args.dst_json), 'w') as f:
        json.dump(items[args.items[0]:args.items[1]] if args.items else new_items, f, indent=2)
    
# Dump no_zeros and misplaced
if no_zero:
    print(f"There were {len(no_zero)} files where zero could not be found.")
    with open("no_zero.log", 'w') as f:
        f.writelines("\n".join(no_zero))

if misplaced:
    print(f"There were {len(misplaced)} files where pulse was misplaced.")
    with open("misplaced.log", 'w') as f:
        f.writelines("\n".join(misplaced))
        
if skipped:
    print(f"There were {len(skipped)} files that were skipped.")
    with open("skipped.log", 'w') as f:
        f.writelines("\n".join(skipped))
        
        
# Calculate stats for the first pulse
if new_items:
    firsts = [x['vehicle'][stages[-1]]['axle_pulses'][0] for x in new_items]
    print(f"First pulse positions are {np.mean(firsts)} \u00B1 {np.std(firsts):.1f}, min: {np.min(firsts)}, max: {np.max(firsts)}")

    # Show plots
    if args.plot:
        if args.legend:
            summary_ax1.legend()
            summary_ax2.legend()
        plt.tight_layout() 
        plt.show()
else:
    print("No output items")
    
