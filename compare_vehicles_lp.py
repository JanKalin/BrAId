##############################################################################
#%% Imports
##############################################################################

import argparse

import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 300

import pandas as pd

from swm.vehicle import Vehicle
from swm.utils import datetime2ts

##############################################################################
#%% Read arguments
##############################################################################

parser = argparse.ArgumentParser(description="Compare vehicles", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--left", help="Left file", default='left.xml')
parser.add_argument("--right", help="Right file", default='right.xml')
parser.add_argument("--mingvw", help="Min GVW in tonnes", default=3.5)
parser.add_argument("--vrange", help="Allowed speed range in km/h", type=float, nargs=2)
parser.add_argument("--axconfig", help="Use this axle configuration")
parser.add_argument("--nomp", help="No MP", action='store_true')
parser.add_argument("--list", help="Generate replay lists and filters. Value is suffix for files")

try:
    __IPYTHON__
    args = parser.parse_args("--left left_all.xml --right right_all.xml --axconfig H2S3 --vrange 80 90 --nomp --list H2S3".split())
except:
    args = parser.parse_args()
    
#%% Load data

left_all = Vehicle.from_txt_files(args.left)   
right_all = Vehicle.from_txt_files(args.right)

#%% Filter

left = []
right = []

count = {'mingvw': 0, 'mp': 0, 'naxles': 0, 'groups': 0, 'vrange': 0, 'axconfig': 0}

for l, r in zip(left_all, right_all):
    skip = False
    if l.anpr_lp != r.anpr_lp:
        raise RuntimeError(f"LPs don't match: {l.anpr_lp} and {r.anpr_lp}, tsl: {l.timestamp}, tsr: {r.timestamp}")
    if args.mingvw and (l.gvw()/9.81 < args.mingvw or r.gvw()/9.81 < args.mingvw):
        skip = True
        count['mingvw'] += 1
    if args.nomp and (l.mpflag() or r.mpflag()):
        skip = True
        count['mp'] += 1
    if len(l.axle) != len(r.axle):
        skip = True
        count['naxles'] += 1
    if l.groups != r.groups:
        skip = True
        count['groups'] += 1
    if args.vrange and (l.v()*3.6 < args.vrange[0] or l.v()*3.6 > args.vrange[1] or r.v()*3.6 < args.vrange[0] or r.v()*3.6 > args.vrange[1]):
        skip = True
        count['vrange'] += 1
    if args.axconfig and (l.axconfig != args.axconfig or r.axconfig != args.axconfig):
        skip = True
        count['axconfig'] += 1
    if not skip:
        left.append(l)
        right.append(r)

print(f"All vehicles: {len(left_all)}")
print("\n".join([f"{x}: {count[x]} ({count[x]/len(left_all)*100:.0f}%)" for x in count.keys()]))
print(f"Remaining: {len(left)} ({len(left)/len(left_all)*100:.0f}%)")

#%% Save lists

if args.list:
    with open(f"left_{args.list}.list", 'w') as f:
        f.writelines("\n".join([f"/live/save/{datetime2ts(x.event_timestamp)}.event" for x in left]))
    with open(f"left_{args.list}.filter", 'w') as f:
        f.writelines("\n".join([f"{datetime2ts(x.timestamp)},{x.lane+1}" for x in left]))
    with open(f"right_{args.list}.list", 'w') as f:
        f.writelines("\n".join([f"/live/save/{datetime2ts(x.event_timestamp)}.event" for x in right]))
    with open(f"right_{args.list}.filter", 'w') as f:
        f.writelines("\n".join([f"{datetime2ts(x.timestamp)},{x.lane+1}" for x in right]))

#%% Plot

df = pd.DataFrame([x.timestamp for x in left]).set_index([0])
# df['Dt'] = [(y.timestamp - x.timestamp).total_seconds() for (x, y) in zip(left, right)]
# df['Dv'] = [(y.v() - x.v())*3.6 for (x, y) in zip(left, right)]
# df['DGVW'] = [(y.gvw() - x.gvw())/9.81 for (x, y) in zip(left, right)]
df['GVWl'] = [x.gvw()/9.81 for x in left]
df['GVWr'] = [x.gvw()/9.81 for x in right]
df['W1l'] = [x.axle[0].cw/9.81 for x in left]
df['W1r'] = [x.axle[0].cw/9.81 for x in right]

plt.figure(figsize=(6, 4))
plt.scatter(df.GVWl, df.W1l, alpha=0.33, s=1, label="Moerdijkbrug")
plt.scatter(df.GVWr, df.W1r, alpha=0.33, s=1, label="Klaverpolder")
plt.xlabel('GVW/t')
plt.ylabel('W1/t')
plt.title("No MP")
plt.legend()
