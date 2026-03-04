#%% Import stuff

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

srcfiles = sorted(os.listdir(srcdir))

for srcfile in srcfiles:
    
    # Read from files/dicts
    photo_id, axle_groups, status = os.path.splitext(srcfile)[0].split('_')
    meta = locallib.load_metadata(None, metafile, axle_groups, photo_id)
    rv = [x for x in rvs if str(x['photo_id']) == photo_id][0]
    entry = [x for x in pulses if x['ts'] == rv['vehicle_timestamp']][0]
    
    # Gather data
    detected = entry['vehicle']['detected']['axle_groups']
    weighed = entry['vehicle']['weighed']['axle_groups']
    
    # Load image
    image = Image.open(os.path.join(srcdir, srcfile))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("courbd.ttf", size=24)
    
    # Write groups
    AI_status = status[-1]
    WIM_status = ''
    for x, text in [(330, detected), (430, weighed)]:
        position = (x, 110)
        if text == axle_groups:
            text_color = (0, 0xFF//4*3, 0)
            WIM_status += 'T'
        else:
            text_color = (0xFF, 0, 0)
            WIM_status += 'F'
        draw.text(position, text, fill=text_color, font=font)
    
    # Save it
    status = f"{WIM_status}_{AI_status}"
    os.makedirs(os.path.join(dstdir, status), exist_ok=True)
    image.save(os.path.join(dstdir, status, f"{photo_id}_{axle_groups}_{status}.png"))
    