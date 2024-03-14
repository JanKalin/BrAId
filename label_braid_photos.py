# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 12:00:50 2024

@author: jank
"""

#%% Import stuff

import argparse
import datetime
import getpass
import json
import math
import os
import sys

from matplotlib import pyplot as plt
from matplotlib import image as mpimg
import matplotlib.dates as mdates
from prettytable import PrettyTable

from PyQt5 import QtCore
from PyQt5.QtWidgets import  QApplication, QMainWindow, QMessageBox
from PyQt5.QtGui import QPixmap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getpass.getuser() == 'jank':
    sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args

parser = argparse.ArgumentParser(description="Interactively mark braid photos", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--photo_root", help="Root for photos", default=r"B:\grouped_photos")
parser.add_argument("--siwim_data_root", help="Root for SiWIM data", default=r"S:\sites\original")
parser.add_argument("--siwim_site", help="SiWIM site", default=r"AC_Sentvid_2012_2")
parser.add_argument("--siwim_rpindex", help="SiWIM Replay Index", default=40)
parser.add_argument("--siwim_module", help="SiWIM module", default="vehicle_fad")

parser.add_argument("--count", help="Count vehicles", action='store_true')

try:
    __IPYTHON__
    args = parser.parse_args("--count".split())
except:
    args = parser.parse_args()

#%% SiWIM photo and data paths

def pngpath(root, v):
    return os.path.join(root, v['vehicle_type'], v['axle_groups'], f"{v['photo_id']}-{v['vehicle_type']}-{v['axle_groups']}-{math.floor(v['type_probability']):.0f}.png")

def event_timestamp(v):
    return datetime.datetime.fromtimestamp(v2e[str(v['vehicle_timestamp'].timestamp())])

def eventpath(fs, v):
    ts = datetime2ts(event_timestamp(v))
    return fs.fullname(ts + ".event")

#%% Data functions

def count_vehicles(rvsd):
    return {vehicle_type: [(key, len(item)) for (key, item) in sorted(entries.items(), key=lambda x: len(x[1]), reverse=True)]
            for (vehicle_type, entries) in rvsd.items()}  

#%% Load data first and make datetime from timestamps

data_dir = os.path.join(SCRIPT_DIR, 'data')

print("Loading recognized_vehicles.json, ", end='')
sys.stdout.flush()
with open(os.path.join(data_dir, "recognized_vehicles.json")) as f:
    rvsl = json.load(f)
print("done.")
    
for rv in rvsl:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])

print("Loading vehicle2event.json, ", end='')
sys.stdout.flush()
with open(os.path.join(data_dir, "vehicle2event.json")) as f:
    v2e = json.load(f)
print("done.")

rvsd = {'bus': {}, 'truck': {}}
for rv in rvsl:
    try:
        rvsd[rv['vehicle_type']][rv['axle_groups']].append(rv)
    except:
        rvsd[rv['vehicle_type']][rv['axle_groups']] = [rv]
    
#%% Main window class and helper functions

from ui.main_window_ui import Ui_MainWindow

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.connectSignalsSlots()
        self.sbPhoto.setFocusPolicy(QtCore.Qt.StrongFocus)

    def load_data(self, rvsd):
        self.rvsd = rvsd
        self.vehicle_count = count_vehicles(self.rvsd)
        self.load_cboxAxleGroups()        

    def connectSignalsSlots(self):
        self.actionAbout.triggered.connect(self.about)
        self.actionPictureNext.triggered.connect(self.nxt)
        self.actionPicturePrevious.triggered.connect(self.prv)
        self.actionShortcuts.triggered.connect(self.shortcuts)
        self.radioSelectBusses.toggled.connect(self.load_cboxAxleGroups)
        self.cboxAxleGroups.currentIndexChanged.connect(self.load_photo_ids)

    def about(self):
        QMessageBox.about(
            self,
            "About BrAId photo labeller",
            "<p>A simple utility to check and manually label AI labelled photos</p>"
            "<p>Jan Kalin &lt;jan.kalin@zag.si&gt;</p>"
            "<p>v1.0.0, 12. March 2024</p>"
        )

    def shortcuts(self):
        QMessageBox.about(
            self,
            "Shortcuts used in this app",
            """<table>
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td><kbd>&lt;Up-Arrow&gt;</kbd></td><td>Previous photo</td></tr>
            <tr><td><kbd>&lt;Down-Arrow&gt;</kbd></td><td>Next photo</td></tr>
            """
        )
         
    def vehicle_type(self):
        return 'bus' if self.radioSelectBusses.isChecked() else 'truck'
    
    def axle_groups(self):
        if not self.cboxAxleGroups.currentIndex():
            return None
        else:
            return self.vehicle_count[self.vehicle_type()][self.cboxAxleGroups.currentIndex() - 1][0]
        
    def load_cboxAxleGroups(self):
        self.cboxAxleGroups.clear()
        self.cboxAxleGroups.addItem("--select--")
        self.cboxAxleGroups.addItems([f"{groups} ({count})" for groups, count in
                                      self.vehicle_count[self.vehicle_type()]])

    def load_photo_ids(self):
        try:
            self.photo_ids = [x['photo_id'] for x in rvsd[self.vehicle_type()][self.axle_groups()]]
            self.photo_index = 0
            self.sbPhoto.setMaximum(len(self.photo_ids))
        except:
            self.photo_ids = None
            self.photo_index = None
            self.sbPhoto.setMaximum(0)
        self.show_photo()
        
    def show_photo(self):
        if self.photo_index is None:
            self.lblPhoto.clear()
        else:
            pixmap = QPixmap(pngpath(args.photo_root, rvsd[self.vehicle_type()][self.axle_groups()][self.photo_index]))
            self.lblPhoto.setPixmap(pixmap)
                        
    def prv(self):
        if self.photo_index:
            self.photo_index -= 1
            self.show_photo()
        
    def nxt(self):
        if self.photo_index < len(rvsd[self.vehicle_type()][self.axle_groups()]):
            self.photo_index += 1
            self.show_photo()
        
   
# Load window and run main loop    
        
app = QApplication(sys.argv)
win = Window()

win.load_data(rvsd)

win.show()
sys.exit(app.exec())







