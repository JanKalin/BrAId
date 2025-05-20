# Sample code

This directory contains sample code for reading and writing SiWIM data used for the BrAId project. This document will be expanded when/if necessary.

## Prerequisites

The latest version of the library `swm` must be installed by cloning the appropriate repo from GitHub, opening a console in the cloned directory and executing `pip install .` If the repo `siwim-pi` is cloned so that it is a sibling of the `BrAId` repo, you don't need to install it, the appropriate libraries will be loaded from there.

## `plot_event_data.py`

This script demonstrates:

- How to load libraries and a file from a disk
- How to plot valid channels
- How to extract the ADMP (Axle Detection Measurement Point) signal and correlate it with the detected axles

Some comments about the code follow.

### Lines 12…15

Add the `siwim-pi` directory to library search path and load the factory class.

### Lines 24 and 25

This is the way to read a file from a disk and return an object of the `Event` class. N.B., the class names in SiWIM-Pi lose the `SWM_` prefix that is used in C++ library, so `Event` in Python is equivalent to `SWM_Event` in C++.

Object `event` has the field `acqdata`, which contains the acquired data. 

### Lines 28…30

`acqdata` has two relevant fields. `a` is a list of analogue channels of the `ACQ_Analogue_Data` class,  and `d` is a list of digital channels. The latter are relevant for obtaining information about when a vehicle is on the bridge and where the SiWIM system detected axles.

`a[ch].empty()` means that there was a problem with the channel. Either zeroing occurred within the event or the channel was manually disabled.

`a[ch].data` is a NumPy Array of float32. `a[ch].offset(sample=0)` is a function returning the offset closest to the `sample`-th sample. Since the data is stored as read, the offset needs to be subtracted for calculations. `a[ch].short_description` is a few characters long description of the channel's contents. The convention is that `w<X>` is the X-th weighing channel, `a<L><N>` is the N-th ADMP channel for lane L and `s<L><N><P>` is N-th speed measurement point channel for lane L, where P is either 1 or 2, for the first and second speed detection channels. N.B.: A channel can have multiple roles.

### Lines 41 and 42

These are:

- the index of the analogue channel used for axle detection on Šentvid and
- the index of the digital channel that contains the pulses for detected axles

### Line 45

In principle one only needs to look at the region of signal where the vehicle is on the bridge. But this information is based on the speed, on the length of the influence line and, crucially, on the detected axles. If an axle is dropped, the apparent "on the bridge" interval will be shorter than in reality.

So this switch controls whether the entire signal or just the trimmed part is used. Which of these will be used is TBD.

### Lines 48 and 49

The ADMP signal is read in line 48 and the axle positions in line 49.

The latter are read from a digital channel. The contents of the channel are a list of tuples, where the two elements of the tuple are the sample numbers of the rising and the falling edge of a pulse, respectively. For this application the rising edge is used.

### Lines 52…62

Calculate the "on the bridge" interval if required, otherwise the complete signal is used.

The `weigh_diag` is the weighing diagnostic, where the "on the bridge" interval is defined. If there's more than one interval, it's considered illegal for this application.

The tuple `on` contains the first and last sample indeces.

### Line 65

The ADMP signal is trimmed, if required.

### Line 69

If the ADMP signal is trimmed, the plot of the axle pulses needs to be shifted to the left by the value of `on[0]`, to keep the alignment of the ADMP and detected axle signals.
