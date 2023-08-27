##############################################################################
#%% Imports
##############################################################################

import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    __IPYTHON__
except:
    addpath = os.path.join(os.path.split(os.path.dirname(SCRIPT_DIR))[0], "siwim-pi")
    sys.path.append(addpath)

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prettytable import PrettyTable
from scipy.optimize import curve_fit
from swm.vehicle import Vehicle

import warnings
warnings.filterwarnings("error")

##############################################################################
#%% Read arguments
##############################################################################

parser = argparse.ArgumentParser(description="Calculate transverse position", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--src", help="Source", default='dists')
parser.add_argument("--lane", help="Lane", type=int, choices=[0, 1, 2])
parser.add_argument("--nch", help="Number of channels", type=int, default=12)
parser.add_argument("--noch", help="Eliminate this ch", type=int, default=0)
parser.add_argument("--nrows", help="Read this many rows", type=int)
parser.add_argument("--mingvw", help="Minimum GVW in tonnes for inclusion. Requires --xml", type=float)
parser.add_argument("--xml", help="Glob for XML files with vehicles", default=os.path.join(SCRIPT_DIR, "203-08-01.xml"))

try:
    __IPYTHON__
    args = parser.parse_args(f"--src nomp --mingvw 3.5 --xml {os.path.join(SCRIPT_DIR, '*.xml')}".split())
except:
    args = parser.parse_args()


#%% Perhaps read XMLs

if args.mingvw:
    if not args.xml:
        raise ValueError("--mingvw requires --xml")
    vehicles = Vehicle.from_xml_files(args.xml, glob=True)
    over_mingvw = pd.Index([x.timestamp for x in sorted(vehicles) if x.gvw() > args.mingvw*9.81])
else:
    over_mingvw = None

#%% Read file and normalise it

filename = os.path.join(SCRIPT_DIR, f"{args.src}.txt")
allchs = [x+1 for x in range(args.nch)]
allcolumns = ['ts', 'MP', 'lane', 'sum'] + allchs

df0 = pd.read_csv(filename, sep='\t', header=None, names=allcolumns, index_col=0, parse_dates=[0], nrows=args.nrows)

#%%

if over_mingvw is not None:
    df0 = df0.drop(df0.index.difference(over_mingvw))
    
lanes = df0.lane.unique()
df = {}
dfp = {}
dfc = {}
poss = {}

if args.lane:
    lanes = [args.lane]


#%% Drop channel and renormalise data

noch = args.noch

if noch:
    chs = [x for x in allchs if x != noch]
    df[noch] = df0.drop(noch, axis=1)
else:
    chs = allchs
    df[noch] = df0.copy()

def renormalise(df, chs):
    df['sum'] = df[chs].sum(axis=1)
    df[chs] = df[chs].div(df['sum'], axis=0)

renormalise(df[noch], chs)
    
fig, ax = plt.subplots()
for lane in lanes:
    df[noch][chs].loc[df[noch].lane == lane].mean(axis=0).plot(ax=ax, style=".-")
ax.legend([f"lane {x}" for x in lanes])
plt.plot()

#%% Fit

def fitted(x, n, k, m, s):
    return np.array(n + x*k + 1/(s*np.sqrt(2*np.pi))*np.exp(-1/2*((x - m)/s)**2))

parnames = ['n', 'k', 'm', 's']
def fit(df, chs, calc_factors=False):
    columns = ['lane'] + parnames
    if calc_factors:
        columns += chs
    dfp = pd.DataFrame(index=df.index, columns=columns, dtype=float)
    dfp.lane = df.lane
    for ts in df.index:
        p0 = [0, 0, 6, 3]
        try:
            p = curve_fit(fitted, chs, df.loc[ts, chs], p0)
        except:
            print(f"Problems with {ts}")
            continue
        dfp.loc[ts, parnames] = p[0]
        if calc_factors:
            dfp.loc[ts, chs] = fitted(np.array(chs), *p[0])/np.array(df.loc[ts, chs])
    return dfp

try:
    havedata = dfp[noch] is not None
except:
    havedata = False
if havedata:
    raise RuntimeError(f"Set 'dfp[{noch}] = None' before proceeding")
else:    
    dfp[noch] = fit(df[noch], chs, calc_factors=True)

#%% Plot fitted and determine s difference

def get_factors(df, dfp, chs, use_pars=False, use_median=False, return_mean_factors=True):
    pars = [dfp.loc[dfp.lane == lane, parnames].mean() for lane in lanes]
    dist = [df.loc[df.lane == lane, chs].mean() for lane in lanes]
    table = PrettyTable(['lane'] + parnames)
    table.float_format = "6.3"
    for lane in lanes:
        table.add_row([lane] + list(pars[lane-1]))
    print(table)
    
    if len(pars) == 2:
        diff_s = np.abs(pars[0][-1] - pars[1][-1])/pars[0][-1]
        print(diff_s)

    if use_pars:
        factors = np.array([fitted(np.array(chs), *pars[lane-1])/dist[lane-1] for lane in lanes])
    else:
        factors = np.array([dfp.loc[dfp.lane == lane, chs].median(axis=0) if use_median else dfp.loc[dfp.lane == lane, chs].mean(axis=0) for lane in lanes])
        
    table = PrettyTable(['lane'] + chs)
    table.float_format = "5.2"
    table.align = 'r'
    for lane in lanes:
        table.add_row([lane] + list(factors[lane-1]))
    
    table.add_row(['mean'] + list(factors.mean(axis=0)))
    print(table)
    
    return pars, factors.mean(axis=0) if return_mean_factors else factors

def scale(df, factors):
    if len(factors) == 2:
        for lane in lanes:
            df.loc[df.lane == lane, chs] *= factors[lane-1]
    else:
        df[chs] *= factors
    

use_pars = True
use_median = True
return_mean_factors = True
sel_tuple = (noch, use_pars, use_median, return_mean_factors)

pars, factors = get_factors(df[noch], dfp[noch], chs, use_pars=use_pars, use_median=use_median, return_mean_factors=return_mean_factors)

dfc[sel_tuple] = df[noch].copy()
scale(dfc[sel_tuple], factors)
renormalise(dfc[sel_tuple], chs)

p = []
for lane in lanes:
    p0 = pars[lane-1]
    p.append(curve_fit(fitted, chs, dfc[noch].loc[dfc[noch].lane == lane, chs].mean(axis=0), p0)[0])
if len(p) == 2:
    diff_s = np.abs(p[0][-1] - p[1][-1])/p[0][-1]
    print(diff_s)

fig, ax = plt.subplots()
for lane in lanes:
    ax.plot(chs, df[noch].loc[df[noch].lane == lane, chs].mean(axis=0), '.-', label=f"lane {lane} pre")
    ax.plot(chs, dfc[sel_tuple].loc[dfc[sel_tuple].lane == lane, chs].mean(axis=0), '.-', label=f"$\\beta_3={pars[lane-1][-2]:.2f}$, $\\beta_4={pars[lane-1][-1]:.2f}$\n$\\beta_3'={p[lane-1][-2]:.2f}$, $\\beta_4'={p[lane-1][-1]:.2f}$")
ax.legend(loc='upper left')

title = ("All channels" if not noch else f"Without channel {noch}") + ", "
if use_pars:
    title += "$\\bar{\\beta_i}$, "
else:
    if use_median:
        title += "$\\tilde{k_j}$, "
    else:
        title += "$\\bar{k_j}$, "
title += "mean MPs" if return_mean_factors else "per lane MPs" 
ax.set_title(title)
plt.plot()
    
#%% Now rerun fit to get positions

try:
    havedata = poss[(noch, use_pars, use_median, return_mean_factors)] is not None
except:
    havedata = False
if havedata:
    raise RuntimeError(f"Set 'pos[{(noch, use_pars, use_median, return_mean_factors)}] = None' before proceeding")
else:    
    poss[(noch, use_pars, use_median, return_mean_factors)] = fit(dfc[sel_tuple], chs, calc_factors=False)

#%% Get a few timestamps

tmp = poss[(noch, use_pars, use_median, return_mean_factors)].sort_values('m')
pos = tmp.loc[tmp.lane == 1, ['m']]
median = pos.m.median()
mean = pos.m.mean()

fig, ax = plt.subplots()
pos.m.plot.hist(bins=100, logy=True)
ax.legend([f"$\\bar{{\\beta_3}}={mean:.2f}$, $\\tilde{{\\beta_3}}={median:.2f}$"])
ax.set_title("All channels" if not noch else f"Without channel {noch}")
plt.plot()

# print("min:", pos.iloc[:5])
# print(" -1:", 

