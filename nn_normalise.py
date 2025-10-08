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

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Normalises and shifs signals", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src-hdf5", help="Source signals file in the data directory", default="nn_signals.hdf5")
parser.add_argument("--src-json", help="Source file vehicles in the data directory", default="nn_pulses.json")
parser.add_argument("--dst-hdf5", help="Destination signals file in the data directory. Use NONE to prevent writing", default="nn_normalised_signals.hdf5")
parser.add_argument("--dst-json", help="Destination vehicles file in the data directory. Use NONE to prevent writing", default="nn_normalised_pulses.json")

parser.add_argument("--dx", help="Resampled data spatial resolution", type=float, default=0.05)
parser.add_argument("--threshold", help="Threshold for search of the positive region", type=float, default=0.20)
parser.add_argument("--expand", help="Expand positive region by this many metres to left and right", type=float, nargs=2, default=[8, 8])

grp_selection = parser.add_mutually_exclusive_group()
grp_selection.add_argument("--ets", help="Process single vehicle")
grp_selection.add_argument("--items", help="Process these items. Default is to process all files", type=int, nargs=2)

parser.add_argument("--plot", help="Plot overlayed 11admp signals and first --plot pulses", type=int)
parser.add_argument("--legend", help="Add label to plot (use for small number of items", action='store_true')

parser.add_argument("--admp-only", help="Process just the 11admp signal", action='store_true')
parser.add_argument("--debug", help="Various debugging", action='store_true');

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--plot 1 --admp --legend --dst-hdf5 NONE --dst-json NONE --ets 2014-03-20-06-40-36-943".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

SAMPLING_RATE = 512
RELEVANT_STAGE = 'final'

#%% Define my exception that causes skipping this item

class SkipItem(Exception):
    """Just signals a skip"""
    pass

#%% Read the json file

with open(os.path.join(args.data_dir, args.src_json)) as f:
    items = json.load(f)
    
if args.ets:
    items = [x for x in items if x['ets_str'] == args.ets]        
    if not items:
        raise ValueError(f"{args.ets} not found in {args.src_json}")
    
    
#%% Now process the data

# Perhaps prepare a plot 
if args.plot:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize = (6, 6), sharex=True)
    
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
            if '11admp' not in dataset_names:
                raise RuntimeError(f"Missing dataset '11admp' in {item['ts_str']}")
            if args.dst_hdf5 != "NONE":
                with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'a') as g:
                    g.create_group(item['ts_str'])
    
            # Clear interval
            (p, q) = (None, None)
    
            # Process all signals
            for jdx, dataset_name in enumerate(['11admp'] + [x for x in dataset_names if x != '11admp']):
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
                data_new /= data_new.max()
    
                # Determine the useful interval from the first signal, 11admp
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
                    for stage in ['detected', 'weighed', 'final']:
                        item['vehicle'][stage]['axle_pulses'] = [int(x/dx_dt - p) for x in item['vehicle'][stage]['axle_pulses']]
                    if item['vehicle'][RELEVANT_STAGE]['axle_pulses'][0] < 160 or item['vehicle'][RELEVANT_STAGE]['axle_pulses'][0] > 212:
                        misplaced.append(f"{item['ets_str']}\t{idx + (args.items[0] if args.items else 0)}\t{item['vehicle'][RELEVANT_STAGE]['axle_pulses'][0]}")
                        raise SkipItem()
                    else:
                        new_items.append(item)
                        
                # Now write the slice of the new data
                data_slice = data_new[p:q]
                if args.dst_hdf5 != "NONE":
                    with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'a') as g:
                        g[item['ts_str']].create_dataset(dataset_name, data=data_slice, compression="gzip", compression_opts=4, shuffle=True)
                
                # And plot the first signal
                if not jdx and args.plot:
                    data_plot = data_slice
                    
                # Perhaps just this channel
                if jdx and args.admp_only:
                    break
                
            # If we don't have the interval, something was wrong
            if not p or not q:
                continue
                    
            # And prehaps plot the final pulses
            if args.plot:
                ax1.plot(data_plot, label=item['ets_str'])
                a = np.zeros(len(data_slice), dtype=int)
                a[item['vehicle'][RELEVANT_STAGE]['axle_pulses'][:args.plot]] = 1
                ax2.plot(a, label=item['ets_str'])
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
    firsts = [x['vehicle'][RELEVANT_STAGE]['axle_pulses'][0] for x in new_items]
    print(f"First pulse positions are {np.mean(firsts)} \u00B1 {np.std(firsts):.1f}, min: {np.min(firsts)}, max: {np.max(firsts)}")

    # Show plots
    if args.plot:
        if args.legend:
            ax1.legend()
            ax2.legend()
        plt.tight_layout() 
        plt.show()
else:
    print("No output items")
    
