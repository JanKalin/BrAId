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
import os
import sys

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import  QApplication, QMainWindow, QMessageBox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getpass.getuser() == 'jank':
    sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from locallib import pngpath, eventpath, load_metadata, save_metadata, count_vehicles, beep

#%% Parse args

parser = argparse.ArgumentParser(description="Interactively mark BrAId photos", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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

#%% Load data first and make datetime from timestamps

print("Loading recognized_vehicles.json, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "recognized_vehicles.json")) as f:
    rvs_loaded = json.load(f)
print("done.")
    
for rv in rvs_loaded:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])

print("Loading vehicle2event.json, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "vehicle2event.json")) as f:
    v2e = json.load(f)
print("done.")

rvs_lists = {'bus': {}, 'truck': {}}
for rv in rvs_loaded:
    try:
        rvs_lists[rv['vehicle_type']][rv['axle_groups']].append(rv)
    except:
        rvs_lists[rv['vehicle_type']][rv['axle_groups']] = [rv]

    
#%% Main window class and helper functions

from ui.main_window_ui import Ui_MainWindow

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(f"{self.windowTitle()}, user '{getpass.getuser()}'")
        self.connect_signals_slots()

        self.figureCanvasADMP = FigureCanvas(Figure(figsize=(5.5, 2)))
        self.layoutGraph.addWidget(self.figureCanvasADMP)
        self.fig = self.figureCanvasADMP.figure
        self.fig.tight_layout()
        self.locator = mdates.AutoDateLocator()
        self.formatter = mdates.ConciseDateFormatter(self.locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M'])
        
        self.lblLastSeen.setText("")
        self.lblLastChanged.setText("")
        self.updating_metadata = False

    def load_data(self, rvs_lists):
        self.rvs_lists = rvs_lists
        self.vehicle_count = count_vehicles(self.rvs_lists)
        self.load_cboxAxleGroups()  

    def connect_signals_slots(self):
        self.actionAbout.triggered.connect(self.about)
        self.actionShortcuts.triggered.connect(self.shortcuts)
        self.actionPictureNext.triggered.connect(self.next_photo)
        self.actionPicturePrevious.triggered.connect(self.previous_photo)
        self.actionLoadADMPs.triggered.connect(self.load_ADMPs)

        self.radioSelectBusses.toggled.connect(self.load_cboxAxleGroups)
        self.cboxAxleGroups.currentIndexChanged.connect(self.setup_scrollbarPhoto)
        self.chkOnlyUnseen.toggled.connect(self.setup_scrollbarPhoto)
        self.scrollbarPhoto.valueChanged.connect(self.show_photo)
        self.chkAutoLoadADMPs.toggled.connect(self.set_chkAutoLoadADMPs)
        self.btnShowADMPEvent.clicked.connect(lambda: self.load_event('ADMP'))
        self.btnShowCFEvent.clicked.connect(lambda: self.load_event('CF'))
        self.btnShowPhoto.clicked.connect(lambda: self.load_event('photo'))
        
        self.radioIsABus.toggled.connect(lambda: self.set_vehicle_type('bus'))
        self.radioIsATruck.toggled.connect(lambda: self.set_vehicle_type('truck'))
        self.actionChangeVehicleType.triggered.connect(lambda: self.set_vehicle_type('truck' if self.radioIsABus.isChecked() else 'bus'))
        self.edtGroups.editingFinished.connect(self.set_groups)
        self.edtRaised.editingFinished.connect(self.set_raised)
            
        self.actionWrongLane.triggered.connect(lambda: self.toggle_checkbox(self.chkWrongLane))
        self.actionWrongVehicle.triggered.connect(lambda: self.toggle_checkbox(self.chkWrongVehicle))
        self.actionOffLane.triggered.connect(lambda: self.toggle_checkbox(self.chkOffLane))
        self.actionTruncatedFront.triggered.connect(lambda: self.toggle_checkbox(self.chkTruncatedFront))
        self.actionTruncatedBack.triggered.connect(lambda: self.toggle_checkbox(self.chkTruncatedBack))
        self.actionVehicleHalved.triggered.connect(lambda: self.toggle_checkbox(self.chkVehicleHalved))
        self.actionCannotLabel.triggered.connect(lambda: self.toggle_checkbox(self.chkCannotLabel))
        
        self.chkWrongLane.stateChanged.connect(lambda: self.set_error(self.chkWrongLane, 'wrong_lane'))
        self.chkWrongVehicle.stateChanged.connect(lambda: self.set_error(self.chkWrongVehicle, 'wrong_vehicle'))
        self.chkOffLane.stateChanged.connect(lambda: self.set_error(self.chkOffLane, 'off_lane'))
        self.chkTruncatedFront.stateChanged.connect(lambda: self.set_error(self.chkTruncatedFront, 'truncated_front'))
        self.chkTruncatedBack.stateChanged.connect(lambda: self.set_error(self.chkTruncatedBack, 'truncated_back'))
        self.chkVehicleHalved.stateChanged.connect(lambda: self.set_error(self.chkVehicleHalved, 'vehicle_halved'))
        self.chkCannotLabel.stateChanged.connect(lambda: self.set_error(self.chkCannotLabel, 'cannot_label'))
        
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
            """
            <table>
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td><kbd>&lt;Up-Arrow&gt;</kbd></td><td>Previous photo</td></tr>
            <tr><td><kbd>&lt;Down-Arrow&gt;</kbd></td><td>Next photo</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-D</kbd></td><td>Load ADMPs</td></tr>
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td><kbd>&lt;Alt&gt;-C</kbd></td><td>Toggle vehicle type: <tt>bus<-->truck</tt></tr>
            <tr><td><kbd>&lt;Alt&gt;-L</kbd></td><td>Wrong Lane</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-V</kbd></td><td>Wrong Vehicle</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-O</kbd></td><td>Off Lane</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-F</kbd></td><td>Truncated Front</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-B</kbd></td><td>Truncated Back</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-H</kbd></td><td>Vehicle Halved</td></tr>
            <tr><td><kbd>&lt;Alt&gt;-N</kbd></td><td>Cannot Verify</td></tr>
            </table>
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
            return self.selected[self.scrollbarPhoto.sliderPosition()]
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
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.selected = [x for x in self.rvs_lists[self.vehicle_type()][self.axle_groups()]
                                 if not self.chkOnlyUnseen.isChecked() or not load_metadata(x, exists=True)]
                self.scrollbarPhoto.setMaximum(len(self.selected) - 1)
                self.scrollbarPhoto.setValue(0)
            except:
                self.scrollbarPhoto.setMaximum(0)
                self.scrollbarPhoto.setValue(0)
        finally:
            QApplication.restoreOverrideCursor()
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
            if not self.axle_groups() or self.scrollbarPhoto.sliderPosition() == -1:
                self.lblPhoto.clear()
                self.rv = None
                self.metadata = None
                if self.scrollbarPhoto.sliderPosition() == -1:
                    self.groupboxLabel.setTitle(f"Vehicle 0/{self.scrollbarPhoto.maximum() + 1}"
                                                + (f" ({len(rvs_lists[self.vehicle_type()][self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else ""))
                else:
                    self.groupboxLabel.setTitle("Vehicle 0/0")
            else:
                self.rv = self.selected[self.scrollbarPhoto.sliderPosition()]
                filename = pngpath(args.photo_root, self.rv)
                if not os.path.isfile(filename):
                    print(f"Cannot load file {filename}")
                    beep()
                    self.metadata = None
                    return
                pixmap = QPixmap(filename)
                self.lblPhoto.setPixmap(pixmap)
                self.metadata = load_metadata(self.rv, args.data_dir)
                try:
                    self.last_seen_by = self.metadata['seen_by']
                except:
                    self.last_seen_by = None
                self.metadata['seen_by'] = (datetime.datetime.now().timestamp(), getpass.getuser())
                save_metadata(self.rv, self.metadata, args.data_dir)
                self.show_metadata()
                try:
                    changed = ", CHANGED" if self.metadata['changed_by'] else ", ORIGINAL"
                except:
                    pass
                self.groupboxLabel.setTitle(f"Vehicle {self.scrollbarPhoto.sliderPosition() + 1}/{self.scrollbarPhoto.maximum() + 1}"
                                            + (f" ({len(rvs_lists[self.vehicle_type()][self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else "")
                                            + f", ts: {datetime2ts(self.rv['vehicle_timestamp'])}"
                                            + f", photo id: {self.rv['photo_id']}"
                                            + f"{changed}")
            self.load_ADMPs(force_clear=not self.chkAutoLoadADMPs.isChecked())
            self.show_metadata()
        except:
            raise
        finally:
            QApplication.restoreOverrideCursor()
    
    def show_metadata(self):
        """Shows metadata in the 'Label' group box
        First sets self.updating_metadata = True to prevent any loops and stuff
        """
        
        def frmt(t):
            return t.strftime('on %a, %d. %b %Y at %H:%M:%S')
        
        try:
            self.updating_metadata = True
            if self.metadata == None:
                self.lblLastSeen.setText("")
                self.lblLastChanged.setText("")
            else:
                # Audit log
                try:
                    at = frmt(datetime.datetime.fromtimestamp(self.last_seen_by[0]))
                    by = self.last_seen_by[1]
                except (KeyError, IndexError, TypeError):
                    at = 'now'
                    by = getpass.getuser()
                self.lblLastSeen.setText(f"Last seen {at} by '{by}'")
                try:
                    at = frmt(datetime.datetime.fromtimestamp(self.metadata['changed_by'][0]))
                    by = self.metadata['changed_by'][1]
                    self.lblLastChanged.setText(f" Last changed {at} by '{by}'")
                except (KeyError, IndexError, TypeError):
                    self.lblLastChanged.setText("")
                
                #  Vehicle type
                try:
                    vehicle_type = self.metadata['vehicle_type']
                except:
                    vehicle_type = self.rv['vehicle_type']
                if vehicle_type == 'bus' and not self.radioIsABus.isChecked():
                    self.radioIsABus.setChecked(True)
                elif vehicle_type == 'truck' and not self.radioIsATruck.isChecked():
                    self.radioIsATruck.setChecked(True)
                    
                # Axle groups and raised
                try:
                    self.edtGroups.setText(self.metadata['axle_groups'])
                except:
                    self.edtGroups.setText(self.rv['axle_groups'])
                try:
                    self.edtRaised.setText(self.metadata['raised_axles'])
                except:
                    self.edtRaised.setText("")
                    
                # Errors
                try:
                    self.chkWrongLane.setCheckState(self.metadata['errors']['wrong_lane'])
                except:
                    self.chkWrongLane.setCheckState(False)
                try:
                    self.chkWrongVehicle.setCheckState(self.metadata['errors']['wrong_vehicle'])
                except:
                    self.chkWrongVehicle.setCheckState(False)
                try:
                    self.chkOffLane.setCheckState(self.metadata['errors']['off_lane'])
                except:
                    self.chkOffLane.setCheckState(False)
                try:
                    self.chkTruncatedFront.setCheckState(self.metadata['errors']['truncated_front'])
                except:
                    self.chkTruncatedFront.setCheckState(False)
                try:
                    self.chkTruncatedBack.setCheckState(self.metadata['errors']['truncated_back'])
                except:
                    self.chkTruncatedBack.setCheckState(False)
                try:
                    self.chkVehicleHalved.setCheckState(self.metadata['errors']['vehicle_halved'])
                except:
                    self.chkVehicleHalved.setCheckState(False)
                try:
                    self.chkCannotLabel.setCheckState(self.metadata['errors']['cannot_label'])
                except:
                    self.chkCannotLabel.setCheckState(False)
        finally:
            self.updating_metadata = False
            
    def set_chkAutoLoadADMPs(self):
        """Perhaps clears ADMPs"""
        self.load_ADMPs(force_clear=not self.chkAutoLoadADMPs.isChecked())
            
    def load_ADMPs(self, force_clear=False):
        """Load ADMPs from event"""
        self.fig.clf()
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            plot = self.figureCanvasADMP.figure.subplots(nrows=2, sharex='col')
            if not force_clear and self.rv is not None:
                fs = FS(args.siwim_admp_data_root, args.siwim_site, args.siwim_admp_rpindex, args.siwim_admp_module)
                filename = eventpath(fs, self.rv, v2e)
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
            
    def load_event(self, region):
        """Loads event and calls external viewer"""
        if self.rv == None:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if region in ['CF', 'ADMP']:
                fs = (FS(args.siwim_cf_data_root, args.siwim_site, args.siwim_cf_rpindex, args.siwim_cf_module) if region == 'CF'
                      else FS(args.siwim_admp_data_root, args.siwim_site, args.siwim_admp_rpindex, args.siwim_admp_module))
                filename = eventpath(fs, self.rv, v2e)
            else:
                filename = pngpath(args.photo_root, self.rv)
            # shutil.copy(filename, tempfile.gettempdir())
            # os.system("start " + os.path.join(tempfile.gettempdir(), os.path.basename(filename)))
            os.system("start " + filename)
        finally:
            QApplication.restoreOverrideCursor()

    def save_changed_metadata(self):
        """Common code for all changes of metadata"""
        self.metadata['changed_by'] = (datetime.datetime.now().timestamp(), getpass.getuser())
        save_metadata(self.rv, self.metadata, args.data_dir)
        self.show_metadata()
        
    def set_vehicle_type(self, vehicle_type):
        """Sets vehicle type"""
        if self.updating_metadata or self.rv == None:
            return
        self.metadata['vehicle_type'] = vehicle_type
        self.save_changed_metadata()
        
    def set_groups(self):
        """Sets axle groups"""
        if self.updating_metadata or self.rv == None:
            return
        try:
            if self.metadata['axle_groups'] == self.edtGroups.text():
                return 
        except:
            pass
        self.metadata['axle_groups'] = self.edtGroups.text()
        self.save_changed_metadata()
        
               
    def set_raised(self):
        """Sets raised axles"""
        if self.updating_metadata or self.rv == None:
            return
        try:
            if self.metadata['raised_axles'] == self.edtRaised.text():
                return
        except:
            pass
        self.metadata['raised_axles'] = self.edtRaised.text()
        self.save_changed_metadata()

    def toggle_checkbox(self, widget):
        """Helper function for toggling checkboxes with actions"""
        widget.setCheckState(0 if widget.isChecked() else 2)
        
    def set_error(self, widget, name):
        """Sets one of the error flags"""
        if self.updating_metadata or self.rv == None:
            return
        try:
            self.metadata['errors']
        except:
            self.metadata['errors'] = {}
        self.metadata['errors'][name] = widget.checkState()
        self.save_changed_metadata()
                
           
# Load window and run main loop    
        
app = QApplication(sys.argv)
win = Window()

win.load_data(rvs_lists)
# DEBUG
win.cboxAxleGroups.setCurrentIndex(win.cboxAxleGroups.count() - 1)

win.show()
sys.exit(app.exec())



