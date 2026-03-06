#%% Import stuff

import datetime
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

import locallib

#%% Load all files

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles.json")) as f:
    rvs = json.load(f)
# for rv in rvs:
#     rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
#     rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    
with open(os.path.join(SCRIPT_DIR, 'data', 'nn_normalised_pulses.json')) as f:
    pulses = json.load(f)
    
metafile = os.path.join(SCRIPT_DIR, 'data', 'metadata.hdf5')

#%% Get photo names and iterate over them

srcdir = os.path.join(SCRIPT_DIR, 'nn_photos', 'rename', 'src')
dstdir = os.path.join(SCRIPT_DIR, 'nn_photos', 'rename', 'dst')

stages = ['detected', 'weighed', 'final']

srcfiles = sorted(os.listdir(srcdir))

for srcfile in srcfiles:
    
    # Read from files/dicts
    photo_id, axle_groups, status = os.path.splitext(srcfile)[0].split('_')
    meta = locallib.load_metadata(None, metafile, axle_groups, photo_id)
    rv = [x for x in rvs if str(x['photo_id']) == photo_id][0]
    entry = [x for x in pulses if x['ts'] == rv['vehicle_timestamp']][0]
    
    # Gather data
    WIM_groups = {stage: entry['vehicle'][stage]['axle_groups'] for stage in stages}
    
    # Load image
    image = Image.open(os.path.join(srcdir, srcfile))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("courbd.ttf", size=24)
    
    # Write groups
    AI_status = status[-1]
    WIM_status = ''
    for x, stage in zip((330, 430, 530), stages):
        position = (x, 110)
        if WIM_groups[stage] == axle_groups:
            if stage != 'final':
                text_color = (0, 0xFF//4*3, 0)
                WIM_status += 'T'
            else:
                try:
                    man = entry['vehicle'][stage]['man']
                except:
                    man = False
                try:
                    fix = entry['vehicle'][stage]['fix']
                except:
                    fix = False
                if WIM_groups[stage] == WIM_groups['weighed']:
                    text_color = (0, 0xFF//4*3, 0)
                    WIM_status += 'T'
                elif man:
                    text_color = (0, 0, 0xFF)
                    WIM_status += 'M'
                elif fix:
                    text_color = (0, 0xFF//4*3, 0)
                    WIM_status += 'H'
                else:
                    raise
        else:
            text_color = (0xFF, 0, 0)
            WIM_status += 'F'
        draw.text(position, WIM_groups[stage], fill=text_color, font=font)
    
    # Save it
    status = f"{WIM_status}_{AI_status}"
    os.makedirs(os.path.join(dstdir, status), exist_ok=True)
    image.save(os.path.join(dstdir, status, f"{photo_id}_{axle_groups}_{status}.png"))
    