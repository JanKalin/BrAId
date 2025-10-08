# Project BrAId

A collection of Python scripts to prepare and tag data from SiWIM B-WIM systems. Used for input to deep learning for axle group detection, for which the scripts can be found [here](https://github.com/DomenSoberlFamnit/BrAId).

## Folders

- `doc`: Documentation, mostly for the `label_braid_photos.py` app
- `sample_code`: Self explanatory
- `sss`: Contains script that plots *sum of signals* versus GVW
- `ui`: PyQt5 source for the UI for `label_braid_photos.py`

## Scripts

- `clean_metadata.py`: Used to reduce the size of the `metadata.hdf5` file
- `compact_metadata.py`: Used to reduce the size of the `metadata.hdf5` file
- `compare_nswd.py`: Compares axle distances and speeds across two NSWDs
- `find_latest.py`: Find latest changed_by and seen_by tags in the `metadata.hdf5` file
- `find_noon_photos.py`: Finds photos nearest to midday, to check the camera quality
- `label_braid_photos.py`: The main script used to manually scan photos and `nswd` files and writes tags for various detection and photography errors into `metadata.hdf5` file
- `locallib.py`: Collection of utility functions for the other scripts
- `main_window_ui.py`: PyQt5 form generated with `pyuic5` from definition in directory `ui`
- `nn_*.py`: Axle pulse-related scripts. The documentation is in  [axles.pdf](doc/axles/axles.pdf).
- `preprocess.py`: Removes all non-lane 1 vehicles and changes tag `bus` to `truck` for all "busses"
  with groups other than 11, 12, 111 and 121
- `read_one_photo.py`: Proto-script for `label_braid_photos.py`
- `select_ok_photos.py`: Selects only photos from the period when the camera angle and quality were good
- `siwim_changes.py`: Summarises changes made by the `fix.py` (part of the SiWIM system) in the first stage and by human checking in the second stage
- `siwim_ok.py`: Find all vehicles for which SiWIM had correctly identified axles

- `vehicles_for_axles.py`: Prepare intermediate file for axle NN
