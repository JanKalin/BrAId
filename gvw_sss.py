# -*- coding: utf-8 -*-
"""
Created on Thu Mar  7 11:29:25 2024

@author: jank
"""

import os
import sys 

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.vehicle import Vehicle

#%% Construct a GVW vs SSS DataFrame

vehicles = Vehicle.from_txt_files(os.path.join(SCRIPT_DIR, "201?.nswd"), glob=True)
df = pd.DataFrame([[x.lane, x.gvw()/9.81, x.sum_of_signals[0], x.sum_of_signals[1]] for x in vehicles if
                   (len(x.sum_of_signals) == 2 and x.gvw()/9.81 > 3.5 and x.gvw()/9.81 < 100)],
                  columns=['lane', 'gvw', 'sss1', 'sss2'])

#%% Fit

lanes = [df.loc[df.lane == x].reset_index() for x in range(2)]
fits = [np.polyfit(lanes[x]['gvw'], lanes[x]['sss1'], 1) for x in range(2)]

fig, ax = plt.subplots(nrows=2, ncols=2, squeeze=False)
fig.set_size_inches(6,4)

for idx, (lane, fit) in enumerate(zip(lanes, fits)):
    print(fit[0], fit[1])
    for jdx in range(2):
        lane.plot(x='gvw', y=f"sss{idx+1}", ax=ax[idx][jdx], style='.', markersize=0.2)
        xs = [lane['gvw'].min(), lane['gvw'].max()]
        ys = [x*fit[0] + fit[1] for x in xs]
        ax[idx][jdx].plot(xs, ys)
        if jdx:
            ax[idx][jdx].set_ylim([0.5*ys[0], 1.5*ys[-1]])

plt.tight_layout()
fig.savefig(os.path.join(SCRIPT_DIR, "SSS.png"), dpi=150)