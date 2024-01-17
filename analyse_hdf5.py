##############################################################################
#%% Imports
##############################################################################

import os
import sys
try:
    __IPYTHON__
except:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    addpath = os.path.join(os.path.split(os.path.dirname(SCRIPT_DIR))[0], "siwim-pi")
    sys.path.append(addpath)

import argparse
import platform

import numpy as np
import pandas as pd

from swm.filesys import FS

##############################################################################
#%% Read arguments
##############################################################################

parser = argparse.ArgumentParser(description="Compare SiWIM and HBM sensors", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("src", help="Source filename")
parser.add_argument("--data_root", help="Data root directory", default=r'D:\siwim\sites' if platform.system() == 'Windows' else '/mnt/siwim/sites/cestel')
parser.add_argument("--site", help="Site directory", default='Crnuce')
parser.add_argument("--rpindex", help="Replay index", type=int, default=11)
parser.add_argument("--module", help="Output module", default='cf')
parser.add_argument("--mingvw", help="Minimal GVW in tons to include", type=float)
parser.add_argument("--maxgvw", help="Maximal GVW in tons to include", type=float)
parser.add_argument("--noflags", help='Drop rows with flags', action='store_true')

try:
    __IPYTHON__
    args = parser.parse_args("X.hdf5 --noflags --maxgvw=45".split())
except:
    args = parser.parse_args()

#%% Get a list of files

fs = FS(args.data_root, args.site, args.rpindex, args.module)
df = pd.read_hdf(fs.fullname(args.src), 'data')

if args.noflags:
    df.drop(df[df['flags'] != 0].index, inplace=True)
if args.mingvw:
    df.drop(df[df['gvw'] < args.mingvw].index, inplace=True)
if args.maxgvw:
    df.drop(df[df['gvw'] > args.maxgvw].index, inplace=True)

diff = df[[x for x in df.columns if x[-4:] == 'diff']]
maxx = df[[x for x in df.columns if x[-3:] == 'max']]
perc = df[[x for x in df.columns if x[-4:] == 'perc']]

for ch in ['S1', 'H1', 'H2', 'SD', 'S2']:
    df[f"{ch}_rela"] = df[f"{ch}_diff"]/maxx.mean()[f"{ch}_max"]
rela = df[[x for x in df.columns if x[-4:] == 'rela']]
gvw = df[[x for x in df.columns if x[-4:] == 'rela'] + ['gvw']]
