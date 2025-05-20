###############################################################################
# Imports
###############################################################################

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

# Get script dir - not the same as CWD - and add the `siwim-pi` to search path
sdir = os.path.split(os.path.realpath(__file__))[0]
sys.path.append(os.path.join(os.path.split(os.path.split(sdir)[0])[0], 'siwim-pi'))

from swm import factory

###############################################################################
#%% Load data and plot all valid analogue channels
###############################################################################

filename = "2014-03-27-12-02-16-234.event"

# Load event
event = factory.read_file(filename)
acqdata = event.acqdata

# Plot valid (non-empty) channels
for a in acqdata.a:
    if not a.empty():
        plt.plot(a.data - a.offset(), label=a.short_description)

plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
plt.tight_layout()
plt.show()

###############################################################################
#%% Plot ADMP and axles for the time that the vehicle is on the bridge
###############################################################################

# Channels for this site
admp_ch = 7
axle_ch = 0

# Trim the signals or not
trim = True

# Remove offset from analogue data and get detected axle positions
admp = acqdata.a[admp_ch].data - acqdata.a[admp_ch].offset()
axles = [int(x[0]) for x in acqdata.d[axle_ch].data]

# If trimming data, get weigh diags to determine the single "on" period that we are seeking
if trim:
    try:
        weigh_diag = event.module_trace.last_module('weigh').diags[0][1]
    except:
        raise RuntimeError(f"No 'weigh' diags in {filename}")
    on = weigh_diag.d[0].data
    if len(on) > 1:
        raise RuntimeError(f"More than one 'on' interval in {filename}")
    on = tuple(int(x) for x in on[0])
else:
    on = (0, len(admp))    

# Trim data
admp = admp[on[0]:on[1]]

# Plot data
plt.plot(admp)
plt.vlines(x=[x - on[0] for x in axles], ymin=-np.max(admp)/10, ymax=0, color='k')

plt.axhline(color='k', linewidth=0.5, linestyle='--')
plt.tight_layout()
plt.show()