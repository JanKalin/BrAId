##############################################################################
#%% Imports
##############################################################################

import argparse
import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FuncFormatter
import numpy as np
import pandas as pd
from prettytable import PrettyTable
from scipy.optimize import curve_fit
from sklearn.linear_model import TheilSenRegressor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    __IPYTHON__ #noqa
    addpath = os.path.join(os.path.dirname(SCRIPT_DIR), "siwim-pi")
    sys.path.append(addpath)
except:
    addpath = os.path.join(os.path.dirname(SCRIPT_DIR), "siwim-pi")
    sys.path.append(addpath)

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
parser.add_argument("--order", help="Optional order of channels along the width of the bridge. Must be a permutation of [1, 2, ..., --nch], or all hell will break loose", type=int, nargs='+')
parser.add_argument("--noch", help="Eliminate this ch", type=int)
parser.add_argument("--nrows", help="Read this many rows", type=int)
parser.add_argument("--mingvw", help="Minimum GVW in tonnes for inclusion. Requires --xml", type=float)
parser.add_argument("--xml", help="Glob for XML files with vehicles", default=os.path.join(SCRIPT_DIR, "2023-08-01.xml"))
parser.add_argument("--mpf", help="Write out mp_factors.conf", action='store_true')
parser.add_argument("--per-lane-factors", help="Return per-channel MP factors. Default is to use common factors for both/all lanes", action='store_true')
parser.add_argument("--mean-factors", help="Use mean to calculate common factors. Default is to use mediann", action='store_true')

parser.add_argument("--dpi", help="DPI for pngs", type=int, default=300)
sizegroup = parser.add_mutually_exclusive_group()
sizegroup.add_argument("--sizein", help="Figure size in inches", type=float, nargs=2)
sizegroup.add_argument("--sizecm", help="Figure size in centimetres", type=float, nargs=2)
parser.add_argument("--fontfamily", help="Font family", default="Times New Roman")
parser.add_argument("--fontsize", help="Font size", type=int, default=10)
parser.add_argument("--saveplot", help="Save plot")

try:
    __IPYTHON__ #noqa
    args = parser.parse_args((r"--src F:\sites\original\AC_Sentvid_2012_2\rp43\weigh\dists_lane1 "
                              r"--xml F:\sites\original\AC_Sentvid_2012_2\rp42\cf\selected.xml "
                              f"--saveplot {os.path.join(SCRIPT_DIR, 'pos')} "
                              r"--nch 12 --noch 8 --lane 1 --mpf --sizein 10 8").split())
except:
    args = parser.parse_args()

## Graph sizes
if args.sizein:
    graphsize = args.sizein
elif args.sizecm:
    graphsize = [x/2.54 for x in args.sizecm]
else:
    graphsize = [3.85, 2]

# Set fonts
if sys.platform == 'win32' and args.saveplot:
    mpl.rc('font',family=args.fontfamily, size=args.fontsize)
    mpl.rc('legend', fontsize=args.fontsize)


#%% Perhaps read XMLs

vehicles = Vehicle.from_txt_files(args.xml, glob=True)
if args.mingvw:
    if not args.xml:
        raise ValueError("--mingvw requires --xml")
    over_mingvw = pd.Index([x.timestamp for x in sorted(vehicles) if x.gvw() > args.mingvw*9.81])
else:
    over_mingvw = None

#%% Read file and normalise it

filename = os.path.join(SCRIPT_DIR, f"{args.src}.txt")
filename = f"{args.src}.txt"
allchs = [x+1 for x in range(args.nch)]
allcolumns = ['ts', 'MP', 'lane', 'sum'] + allchs

if args.order:
    allcolumns = ['ts', 'MP', 'lane', 'sum'] + args.order

df0 = pd.read_csv(filename, sep='\t', header=None, names=allcolumns, index_col=0, parse_dates=[0], nrows=args.nrows)

if over_mingvw is not None:
    df0 = df0.drop(df0.index.difference(over_mingvw))
    
df0 = df0[~df0.index.duplicated(keep='first')]
    
lanes = df0.lane.unique()
df = {}
dfp = {}
dfc = {}
poss = {}

if args.lane:
    lanes = [args.lane]

lanes = sorted(lanes)

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
plt.show()

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
    for ts in dfp.index:
        p0 = [0, 0, 6, 3]
        try:
            p = curve_fit(fitted, chs, df.loc[ts, chs], p0)
        except:
            print(f"Problems with {ts}")
            raise
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
    
    # if len(pars) == 2:
    #     diff_s = np.abs(pars[0].iloc[-1] - pars[1].iloc[-1])/pars[0].iloc[-1]
    #     print(pars)
    #     print(diff_s)

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
    if args.mpf:
        print(f"[global]\nnumber_of_channels={len(factors.mean(axis=0))}\n\n[factors]")
        print("\n".join([f"ch_factor={x:.3f}" for (idx, x) in enumerate(factors.mean(axis=0), 1)]))
    
    return pars, factors.mean(axis=0) if return_mean_factors else factors

def scale(df, factors):
    if len(factors) == 2:
        for lane in lanes:
            df.loc[df.lane == lane, chs] *= factors[lane-1]
    else:
        df[chs] *= factors
    

use_pars = False
use_median = not args.mean_factors
return_mean_factors = not args.per_lane_factors
sel_tuple = (noch, use_pars, use_median, return_mean_factors)

pars, factors = get_factors(df[noch], dfp[noch], chs, use_pars=use_pars, use_median=use_median, return_mean_factors=return_mean_factors)

dfc[sel_tuple] = df[noch].copy()
scale(dfc[sel_tuple], factors)
renormalise(dfc[sel_tuple], chs)

p = []
for lane in lanes:
    p0 = pars[lane-1]
    p.append(curve_fit(fitted, chs, dfc[sel_tuple].loc[dfc[sel_tuple].lane == lane, chs].mean(axis=0), p0)[0])
if len(p) == 2:
    diff_s = np.abs(p[0][-1] - p[1][-1])/((p[0][-1] + p[1][-1])/2)
    print(f"Relative sigma difference {diff_s*100:.0f}%")

fig, ax = plt.subplots()
for lane in lanes:
    ax.plot(chs, df[noch].loc[df[noch].lane == lane, chs].mean(axis=0), '.-', label=f"lane {lane} pre")
for lane in lanes:
    ax.plot(chs, dfc[sel_tuple].loc[dfc[sel_tuple].lane == lane, chs].mean(axis=0), '.--', label=f"$\\beta_3={pars[lane-1].iloc[-2]:.2f}$, $\\beta_4={pars[lane-1].iloc[-1]:.2f}$\n$\\beta_3'={p[lane-1][-2]:.2f}$, $\\beta_4'={p[lane-1][-1]:.2f}$")
plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
plt.gca().xaxis.set_major_locator(MultipleLocator(1))
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda val, pos: f"{int(val)}"))

title = ("All channels" if not noch else f"Without channel {noch}") + ", "
if use_pars:
    title += "$\\bar{\\beta_i}$, "
else:
    if use_median:
        title += "$\\tilde{k_j}$, "
    else:
        title += "$\\bar{k_j}$, "
title += (("median" if use_median else "mean") if return_mean_factors else " per lane") + " MPs"
ax.set_title(title)

if args.saveplot:
    plt.gcf().set_size_inches(graphsize[0], graphsize[1])
    plt.gcf().savefig(args.saveplot, dpi=args.dpi, bbox_inches='tight', pad_inches=0)
else:
    plt.show()


    
#%% Now rerun fit to get positions

try:
    havedata = poss[(noch, use_pars, use_median, return_mean_factors)] is not None
except:
    havedata = False
if havedata:
    raise RuntimeError(f"Set 'pos[{(noch, use_pars, use_median, return_mean_factors)}] = None' before proceeding")
else:    
    poss[(noch, use_pars, use_median, return_mean_factors)] = fit(dfc[sel_tuple], chs, calc_factors=False)

#%% Get a few timestamps and calculate position

tmp = poss[(noch, use_pars, use_median, return_mean_factors)].sort_index()
pos = tmp.loc[tmp.lane == 1, ['m']]
median = pos.m.median()
mean = pos.m.mean()

fig, ax = plt.subplots()
pos.m.plot.hist(bins=100, logy=True)
ax.legend([f"$\\bar{{\\beta_3}}={mean:.2f}$, $\\tilde{{\\beta_3}}={median:.2f}$"])
ax.set_title("All channels" if not noch else f"Without channel {noch}")
plt.plot()

#%% Get GVW and W1 for vehicles and make a new df

data = pd.DataFrame(index=range(len(vehicles)), columns=['loc', 'gvw', 'w1'], dtype=float)

for idx, vehicle in enumerate(vehicles):
    try:
        idx_val = tmp.index.get_indexer([vehicle.timestamp], method='nearest')[0]
        data.loc[idx, 'loc'] = tmp.iloc[idx_val]['m']
        data.loc[idx, 'gvw'] = vehicle.gvw()/9.81
        data.loc[idx, 'w1'] = vehicle.axle[0].cw/9.81
    except KeyError:
        raise
        

#%%

ts = False
GVW_lim = 32.5
D_loc = 0.10
D_locs = [-np.inf, data['loc'].mean() - D_loc/2, data['loc'].mean() + D_loc/2, np.inf]

fig, ax = plt.subplots()
data['gvw'].hist(bins=40, ax=ax)
ax.axvline(GVW_lim, linestyle=":", color='k')
plt.xlim(10, 55)
fig.savefig(f"{args.saveplot}-GVW_hist-{GVW_lim}t.png", dpi=args.dpi, bbox_inches='tight', pad_inches=0)

fig, ax = plt.subplots()
ax.xaxis.set_major_locator(MultipleLocator(0.5))
ax.xaxis.set_minor_locator(MultipleLocator(0.5))
ax.minorticks_on()
plt.xlim(4.4, 6.4)
plt.ylim(2.5, 50)
plt.plot(data['loc'], data['gvw'], '.', markersize=0.25, label='GVW')
xlo, xhi = ax.get_xlim()
ylo, yhi = ax.get_ylim()

for GVW_lims in zip([-np.inf, GVW_lim], [GVW_lim, np.inf]):
    if not GVW_lims[1]:
        continue
    GVWs = data.loc[(data['gvw'] >= GVW_lims[0]) &  (data['gvw'] <= GVW_lims[1])]
    slcs = [GVWs.loc[(data['loc'] > a) & (data['loc'] <= b)]['gvw'].describe()
            for (a, b) in zip(D_locs[:-1], D_locs[1:])]
    N = [len(GVWs.loc[(data['loc'] > a) & (data['loc'] <= b)]['gvw'])
            for (a, b) in zip(D_locs[:-1], D_locs[1:])]
    
    for idx, ((mean, std), (xmin, xmax)) in enumerate(zip([(x['mean'], x['std']) for x in slcs], zip(D_locs[:-1], D_locs[1:]))):
        if xmin == -np.inf:
            xmin = xlo
        if xmax == np.inf:
            xmax = xhi
        plt.hlines(y=mean, xmin=xmin, xmax=xmax, linewidth=0.75, color='r')
        plt.hlines(y=mean + std, xmin=xmin, xmax=xmax, linestyle='--', linewidth=0.25, color='r')
        plt.hlines(y=mean - std, xmin=xmin, xmax=xmax, linestyle='--', linewidth=0.50, color='r')
        Delta = mean/GVWs['gvw'].mean() - 1
        plt.text((xmin+xmax)/2, mean - 0.25, f"{mean:.1f}t = {Delta*100:+.1f}%\nN = {N[idx]}, $\\Delta$ = {Delta/std*100:.2g}%$\\sigma$", va='top', ha='center', color='r')
        
    if ts:
        model = TheilSenRegressor()
        model.fit(GVWs[['loc']], GVWs['gvw'])
        m = model.coef_[0]
        b = model.intercept_
    else:
        m, b = np.polyfit(GVWs['loc'], GVWs['gvw'], 1)
        p = np.poly1d([m, b])
        y_pred = p(GVWs['loc'])
        ss_res = np.sum((GVWs['gvw'] - y_pred) ** 2)
        ss_tot = np.sum((GVWs['gvw'] - np.mean(GVWs['gvw'])) ** 2)
        r2 = 1 - (ss_res / ss_tot)      
    plt.plot([xlo, xhi], [m*x + b for x in [xlo, xhi]], ':m')
    plt.text((xlo+xhi)/2, m*(xlo+xhi)/2 + b + 0.75, f"slope = {m:.1f}t/m = {m/np.mean(GVWs['gvw'])*100:.0f}%/m, R^2 = {r2:.04f}", ha='center', va='bottom', color='m')

for GVW_limm in GVW_lims:
    plt.axhline(GVW_limm, linestyle=':', linewidth=0.5, color='k')
    plt.text((xlo+xhi)/2, GVW_limm, f"{GVW_limm}t", va='top', ha='center')
for D_locc in D_locs:
    plt.axvline(D_locc, linestyle='--', linewidth=0.5, color='k')
ax.annotate("", xy=(D_locs[1], ylo + 1), xytext=(D_locs[2], ylo + 1),
            arrowprops=dict(arrowstyle="<->", color="k", lw=1.5, shrinkA=0, shrinkB=0))
plt.text((D_locs[1] + D_locs[2])/2, ylo + 1, f"{D_loc:.2f}m", va='bottom', ha='center')

plt.plot(data['loc'], data['w1'], '.', markersize=0.25, label='W1')
m, b = np.polyfit(data['loc'], data['w1'], 1)
p = np.poly1d([m, b])
y_pred = p(data['loc'])
ss_res = np.sum((data['w1'] - y_pred) ** 2)
ss_tot = np.sum((data['w1'] - np.mean(data['w1'])) ** 2)
r2 = 1 - (ss_res / ss_tot)      
plt.plot([xlo, xhi], [m*x + b for x in [xlo, xhi]], ':k')
plt.text((xlo+xhi)/2, 9, f"slope = {m:.1f}t/m = {m/np.mean(data['w1'])*100:.0f}%/m, R^2 = {r2:.04f}", ha='center')

plt.xlabel("y/m")
plt.ylabel("GVW/t, W1/t")
plt.title("GVW and W1 vs lateral position")
plt.legend()
plt.gcf().set_size_inches(graphsize[0], graphsize[1])
plt.gcf().savefig(f"{args.saveplot}-GVW_vs_pos-{GVW_lim}t-{D_loc:.2f}m.png", dpi=args.dpi, bbox_inches='tight', pad_inches=0)

