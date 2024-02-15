# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank
"""

#%% Import stuff

import argparse
import datetime
import json
import os

from matplotlib import pyplot as plt
from matplotlib import image as mpimg

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

try:
    __IPYTHON__
    args = parser.parse_args()
except:
    args = parser.parse_args()

#%% Read files

with open("recognized_vehicles.json") as f:
    rvs = json.load(f)
    
with open("v2e.json") as f:
    v2e = json.load(f)
    

#%% Split into groups according to groups

v = {'bus': {}, 'truck': {}}

for rv in rvs[:10]:
    typ = rv['vehicle_type']
    try:
        v[typ][rv['axle_groups']].append(rv)
    except:
        v[typ][rv['axle_groups']] = [rv]


#%% Get PNG

def pngpath(root, v):
    return os.path.join(root, v['vehicle_type'], v['axle_groups'], f"{v['photo_id']}-{v['vehicle_type']}-{v['axle_groups']}-{v['type_probability']:.0f}.png")


pngname = pngpath(r"B:\grouped_photos", rvs[0])

image = mpimg.imread(pngname)
plt.imshow(image)
plt.show()

#%% Get event

fs = FS(args.siwim_data_root, args.siwim_site, args.siwim_rpindex, args.siwim_module)

def eventpath(fs, v):
    ts = datetime2ts(datetime.datetime.fromtimestamp(v2e[str(v['vehicle_timestamp'])]))
    return fs.fullname(ts + ".event")

event_name = eventpath(fs, rvs[2])
event = read_file(event_name)

df = event.diag['vehicle_fad'].df()

for ch in ['11admp', '11diff', '21admp', '21diff']:
    try:
        plt.plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
    except:
        print(ch)
plt.legend()
plt.show()