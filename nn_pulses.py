### Import stuff

import argparse
from difflib import SequenceMatcher
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

parser = argparse.ArgumentParser(description="Use data from `nn_axles.json` to generate data for NN training", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--src", help="Source file, output `from nn_axles.py`, in the data directory", default="nn_axles.json")
parser.add_argument("--dst", help="Destination file", default="nn_pulses.json")

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--src nn_axles-some.json --dst nn_pulses-some.json".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

#%% Read the vehicles file 

with open(os.path.join(args.data_dir, args.src)) as f:
    input_vehicles = json.load(f)
    
output_vehicles = []
eligible = {True: 0, False: 0}

for item in [input_vehicles[2]]:
    # Short names
    dist_w = item['vehicle']['weighed']['axle_distance']
    pulse_w = item['vehicle']['weighed']['axle_pulses']
    dist_f = item['vehicle']['final']['axle_distance']
    
    # Match and just skip if *none* of the distances match
    m = SequenceMatcher(a=dist_w, b=dist_f)
    item['eligible'] = m.ratio() > 0
    eligible[item['eligible']] += 1
    if not item['eligible']:
        continue
    
    # Calculate diff for pulses
    diff_w = [y - x for (x, y) in zip(pulse_w[:-1], pulse_w[1:])]
    
    # Find the longest matching sequence and use it for scaling
    longest = m.find_longest_match()
    sum_dist = sum([x for x in dist_w[longest.a : longest.a + longest.size]])
    sum_pulse = sum([x for x in diff_w[longest.a : longest.a + longest.size]])
    scale = sum_pulse/sum_dist
    
    # Now create a new diff and fill it
    diff_f = [0]*len(dist_f)
    diff_f[longest.b:longest.b + longest.size] = diff_w[longest.a:longest.a + longest.size]
    diff_f[0:longest.b] = [round(x*scale) for x in dist_f[0:longest.b]]
    diff_f[longest.b:] = [round(x*scale) for x in dist_f[longest.b:]]
    
    # And from diff make new pulses
    pulse_f = [0]*(len(diff_f) + 1)
    pulse_f[longest.b + 1:longest.b + 1 + longest.size] = pulse_w[longest.a + 1:longest.a + 1 + longest.size]
    for idx in range(longest.b + 1 + longest.size, len(pulse_f)):
        pulse_f[idx] = pulse_f[idx - 1] + diff_f[idx-1]
    for idx in range(longest.b, -1, -1):
        pulse_f[idx] = pulse_f[idx + 1] - diff_f[idx]
    
print(eligible)

with open(os.path.join(args.data_dir, args.dst), 'w') as f:
    json.dump(output_vehicles, f, indent=2)
