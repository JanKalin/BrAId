# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank
"""

#%% Import stuff

import argparse
import datetime
import json
import math
import os
import sys

from matplotlib import pyplot as plt
from matplotlib import image as mpimg
import matplotlib.dates as mdates
from prettytable import PrettyTable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts

#%% Parse args

parser = argparse.ArgumentParser(description="Interactively mark braid photos", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--photo_root", help="Root for photos", default=r"B:\grouped_photos")
parser.add_argument("--siwim_data_root", help="Root for SiWIM data", default=r"S:\sites\original")
parser.add_argument("--siwim_site", help="SiWIM site", default=r"AC_Sentvid_2012_2")
parser.add_argument("--siwim_rpindex", help="SiWIM Replay Index", default=40)
parser.add_argument("--siwim_module", help="SiWIM module", default="vehicle_fad")

parser.add_argument("--count", help="Count vehicles", action='store_true')

try:
    __IPYTHON__
    args = parser.parse_args("--count".split())
except:
    args = parser.parse_args()

#%% Read files

with open(os.path.join(SCRIPT_DIR, "recognized_vehicles.json")) as f:
    rvs = json.load(f)
for rv in rvs:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    
with open(os.path.join(SCRIPT_DIR, "v2e.json")) as f:
    v2e = json.load(f)
    
def pngpath(root, v):
    return os.path.join(root, v['vehicle_type'], v['axle_groups'], f"{v['photo_id']}-{v['vehicle_type']}-{v['axle_groups']}-{math.floor(v['type_probability']):.0f}.png")

def event_timestamp(v):
    return datetime.datetime.fromtimestamp(v2e[str(v['vehicle_timestamp'].timestamp())])

def eventpath(fs, v):
    ts = datetime2ts(event_timestamp(v))
    return fs.fullname(ts + ".event")


#%% Prehaps count

if args.count:
    groups = []
    for rv in rvs:
        if rv['axle_groups'] not in groups:
            groups.append(rv['axle_groups'])
    count = {group: {'total': 0, 'bus': 0, 'truck': 0} for group in groups}
    for rv in rvs:
        count[rv['axle_groups']]['total'] += 1
        count[rv['axle_groups']][rv['vehicle_type']] += 1
    table = PrettyTable(['groups', 'total', 'bus', 'truck'])
    table.align = 'r'
    for key, item in sorted(count.items(), key=lambda item: item[1]['total'], reverse=True):
        table.add_row([key, item['total'], item['bus'], item['truck']])
    print(table)
    
    raise SystemExit
        
    
        
#%% Split into groups according to groups

v = {'bus': {}, 'truck': {}}

for rv in rvs[:10]:
    typ = rv['vehicle_type']
    try:
        v[typ][rv['axle_groups']].append(rv)
    except:
        v[typ][rv['axle_groups']] = [rv]


#%% Get PNG and event and plot

photo_id = 181417

rv = [x for x in rvs if x['photo_id'] == photo_id][0]

pngname = pngpath(r"B:\grouped_photos", rv)
print(os.path.basename(pngname))

image = mpimg.imread(pngname)

# plt.imshow(image)
# plt.show()

fs_vehicle_fad = FS(args.siwim_data_root, args.siwim_site, args.siwim_rpindex, args.siwim_module)
fs_cf = FS(r"t:\sites\original", args.siwim_site, 1, "cf")

event_name = eventpath(fs_vehicle_fad, rv)
print(os.path.basename(event_name))
event = read_file(event_name)

df = event.diag['vehicle_fad'].df()

# for ch in ['11admp', '11diff', '21admp', '21diff']:
#     try:
#         plt.plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
#     except:
#         print(ch)

# plt.legend()
# locator = mdates.AutoDateLocator()
# plt.gca().xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M']))
# # for label in plt.gca().get_xticklabels(which='major'):
# #     label.set(rotation=30, horizontalalignment='right')
# plt.show()

fig = plt.figure()
gs = fig.add_gridspec(nrows=2, ncols=2, width_ratios=[2, 1.5])
ax0 = fig.add_subplot(gs[:, 0])
ax0.imshow(image)
ax0.axis('off')

locator = mdates.AutoDateLocator()
formatter = mdates.ConciseDateFormatter(locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M'])

if '11admp' in df.columns and '11diff' in df.columns:
    ax1 = fig.add_subplot(gs[0, 1])
    for ch in ['11admp', '11diff']:
        try:
            ax1.plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
        except:
            print(ch)
    ax1.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M']))

if '21admp' in df.columns and '21diff' in df.columns:
    ax2 = fig.add_subplot(gs[1, 1])
    for ch in ['21admp', '21diff']:
        try:
            ax2.plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
        except:
            print(ch)
    ax2.xaxis.set_major_formatter(formatter)

ax3=fig.add_subplot(gs[0, 1])
ax3.axis('off')

plt.tight_layout()
plt.show()

print(rv['vehicle_timestamp'])
event = read_file(eventpath(fs_cf, rv))
event.write_file(os.path.join(SCRIPT_DIR, "tmp.event"))
