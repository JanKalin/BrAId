# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 12:00:50 2024

@author: jank
"""

#%% Import stuff

import argparse
import copy
import datetime
import getpass
import json
import math
import os
import shutil
import sys
import tempfile
import winsound

import h5py
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import  QApplication, QMainWindow, QMessageBox, QScrollArea

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
parser.add_argument("--siwim_site", help="SiWIM site", default=r"AC_Sentvid_2012_2")
parser.add_argument("--siwim_admp_data_root", help="Root for SiWIM ADMP data", default=r"S:\sites\original")
parser.add_argument("--siwim_admp_rpindex", help="SiWIM ADMP replay index", default=40)
parser.add_argument("--siwim_admp_module", help="SiWIM ADMP module", default="vehicle_fad")
parser.add_argument("--siwim_cf_data_root", help="Root for SiWIM calcualated data", default=r"T:\sites\original")
parser.add_argument("--siwim_cf_rpindex", help="SiWIM CF replay index", default=1)
parser.add_argument("--siwim_cf_module", help="SiWIM CF module", default="cf")
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
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

def load_metadata(rv):
    try:
        with h5py.File(os.path.join(args.data_dir, "metadata.hdf"), 'r') as f:
            return json.loads(f[f"{rv['vehicle_type']}/{rv['axle_groups']}/{rv['photo_id']}"].asstr()[()])
    except:
        return {'seen_by': [], 'changed_by': []}
    
def save_metadata(rv, metadata):
    with h5py.File(os.path.join(args.data_dir, "metadata.hdf"), 'a') as f:
        try:
            grp = f.require_group(f"{rv['vehicle_type']}/{rv['axle_groups']}")
        except TypeError:
            grp = f[f"{rv['vehicle_type']}/{rv['axle_groups']}"]
        try:
            grp[str(rv['photo_id'])] = json.dumps(metadata)
        except:
            data = grp[str(rv['photo_id'])]
            data[...] = json.dumps(metadata)

def count_vehicles(rvsd):
    return {vehicle_type: [(key, len(item)) for (key, item) in sorted(entries.items(), key=lambda x: len(x[1]), reverse=True)]
            for (vehicle_type, entries) in rvsd.items()}  

#%% Load data first and make datetime from timestamps

print("Loading recognized_vehicles.json, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "recognized_vehicles.json")) as f:
    rvsl = json.load(f)
print("done.")
    
for rv in rvsl:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])

print("Loading vehicle2event.json, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "vehicle2event.json")) as f:
    v2e = json.load(f)
print("done.")

rvsd = {'bus': {}, 'truck': {}}
for rv in rvsl:
    try:
        rvsd[rv['vehicle_type']][rv['axle_groups']].append(rv)
    except:
        rvsd[rv['vehicle_type']][rv['axle_groups']] = [rv]

    
#%% Main window class and helper functions

def beep():
    winsound.Beep(1670, 100)

from ui.main_window_ui import Ui_MainWindow

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(f"{self.windowTitle()}, user '{getpass.getuser()}'")
        self.connectSignalsSlots()

        self.figureCanvasADMP = FigureCanvas(Figure(figsize=(5.5, 2)))
        self.layoutGraph.addWidget(self.figureCanvasADMP)
        self.fig = self.figureCanvasADMP.figure
        self.fig.tight_layout()
        self.locator = mdates.AutoDateLocator()
        self.formatter = mdates.ConciseDateFormatter(self.locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M'])
        

    def load_data(self, rvsd):
        self.rvsd = rvsd
        self.vehicle_count = count_vehicles(self.rvsd)
        self.load_cboxAxleGroups()        

    def connectSignalsSlots(self):
        self.actionAbout.triggered.connect(self.about)
        self.actionShortcuts.triggered.connect(self.shortcuts)
        self.actionPictureNext.triggered.connect(self.next_photo)
        self.actionPicturePrevious.triggered.connect(self.previous_photo)
        self.actionLoadADMPs.triggered.connect(self.load_ADMPs)

        self.radioSelectBusses.toggled.connect(self.load_cboxAxleGroups)
        self.cboxAxleGroups.currentIndexChanged.connect(self.setup_scrollbarPhoto)
        self.scrollbarPhoto.valueChanged.connect(self.show_photo)
        self.chkAutoLoadADMPs.toggled.connect(self.set_chkAutoLoadADMPs)
        self.btnLoadEvent.clicked.connect(self.load_event)

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
            <tr><td><kbd>&lt;Alt&gt;-D</kbd></td><td>Load ADMPs</td></tr>
            """
        )
         
    def vehicle_type(self):
        """Returns vehicle type, read from radio buttons"""
        return 'bus' if self.radioSelectBusses.isChecked() else 'truck'
    
    def axle_groups(self):
        """Returns axle groups, read from combo box"""
        if not self.cboxAxleGroups.currentIndex():
            return None
        else:
            return self.vehicle_count[self.vehicle_type()][self.cboxAxleGroups.currentIndex() - 1][0]
        
    def photo_id(self):
        """Returns the photo slider position (photo index)"""
        if not self.scrollbarPhoto.maximum():
            return None
        try:
            return self.rvsd[self.vehicle_type()][self.axle_groups()][self.scrollbarPhoto.sliderPosition()]
        except:
            return None
        
    def load_cboxAxleGroups(self):
        """Loads combo box with groups and count of busses or trucks"""
        self.cboxAxleGroups.clear()
        self.cboxAxleGroups.addItem("--select--")
        self.cboxAxleGroups.addItems([f"{groups} ({count})" for groups, count in
                                      self.vehicle_count[self.vehicle_type()]])

    def setup_scrollbarPhoto(self):
        """Sets up scroll bar for photo selection and shows the first photo"""
        try:
            self.scrollbarPhoto.setMaximum(len(self.rvsd[self.vehicle_type()][self.axle_groups()]) - 1)
            self.scrollbarPhoto.setValue(0)
        except:
            self.scrollbarPhoto.setMaximum(0)
            self.scrollbarPhoto.setValue(0)
        self.show_photo()

    def previous_photo(self):
        """Shows previous photo"""
        self.scrollbarPhoto.setValue(self.scrollbarPhoto.sliderPosition() - 1)        
        
    def next_photo(self):
        """Shows next photo"""
        self.scrollbarPhoto.setValue(self.scrollbarPhoto.sliderPosition() + 1)
        
    def show_photo(self):
        """Shows photo, loads metadata, updates 'seen_by' and perhaps loads ADMPs"""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if not self.axle_groups():
                self.lblPhoto.clear()
                self.rv = None
                self.metadata = None
            else:
                self.rv = self.rvsd[self.vehicle_type()][self.axle_groups()][self.scrollbarPhoto.sliderPosition()]
                filename = pngpath(args.photo_root, self.rv)
                if not os.path.isfile(filename):
                    print(f"Cannot load file {filename}")
                    beep()
                    self.metadata = {}
                    return
                pixmap = QPixmap(filename)
                self.lblPhoto.setPixmap(pixmap)
                self.metadata = load_metadata(self.rv)
                self.metadata['seen_by'].append((datetime.datetime.now().timestamp(),getpass.getuser()))
                save_metadata(self.rv, self.metadata)
                self.new_metadata = self.metadata.copy()
                self.groupboxLabel.setTitle(f"{self.scrollbarPhoto.sliderPosition() + 1}/{self.scrollbarPhoto.maximum() + 1}")
            self.load_ADMPs(force_clear=not self.chkAutoLoadADMPs.isChecked())
        finally:
            QApplication.restoreOverrideCursor()
    
    def set_chkAutoLoadADMPs(self):
        self.load_ADMPs(force_clear=not self.chkAutoLoadADMPs.isChecked())
            
    def load_ADMPs(self, force_clear=False):
        self.fig.clf()
        try:
            plot = self.figureCanvasADMP.figure.subplots(nrows=2, sharex='col')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if not force_clear and self.rv is not None:
                fs = FS(args.siwim_admp_data_root, args.siwim_site, args.siwim_admp_rpindex, args.siwim_admp_module)
                filename = eventpath(fs, self.rv)
                try:
                    event = read_file(filename)
                except:
                    print(f"Cannot load file {filename}")
                    beep()
                    return
                df = event.diag['vehicle_fad'].df()
                for lane, chs in enumerate([['11admp', '11diff'], ['21admp', '21diff']]):
                    for ch in chs:
                        if ch in df.columns:
                            plot[lane].plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
                plot[lane].xaxis.set_major_formatter(self.formatter)
        finally:
            self.fig.canvas.draw_idle()
            QApplication.restoreOverrideCursor()
            
    def load_event(self):
        fs = FS(args.siwim_cf_data_root, args.siwim_site, args.siwim_cf_rpindex, args.siwim_cf_module)
        filename = eventpath(fs, self.rv)
        shutil.copy(filename, tempfile.gettempdir())
        os.system("start " + os.path.join(tempfile.gettempdir(), os.path.basename(filename)))
        
           
# Load window and run main loop    
        
app = QApplication(sys.argv)
win = Window()

win.load_data(rvsd)
#win.cboxAxleGroups.setCurrentIndex(1)

win.show()
sys.exit(app.exec())



