### Import stuff

import argparse
import datetime
import getpass
import json
import os
import re
import shutil
import sys
import tempfile

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QPixmap, QWindow, QValidator
from PyQt5.QtWidgets import  QApplication, QMainWindow, QMessageBox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts, str2groups, groups2str

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from locallib import pngpath, eventpath, load_metadata, save_metadata, beep

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
parser.add_argument("--timeout", help="File write timeout in seconds", type=int, default=10)
parser.add_argument("--batchsize", help="Batch size for better motivation :)", type=int, default=1000)

try:
    __IPYTHON__
    args = parser.parse_args("--timeout 10".split())
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

metadata_filename = os.path.join(args.data_dir, "metadata.hdf5")

#%% Make batches

rvs_batches = {'bus': {}, 'truck': {}}
maxbatches = 0
for vehicle_type in rvs_lists:
    for axle_groups in rvs_lists[vehicle_type]:
        batches = len(rvs_lists[vehicle_type][axle_groups]) // args.batchsize + 1
        maxbatches = max(maxbatches, batches)
        if batches == 1:
            rvs_batches[vehicle_type][axle_groups] = rvs_lists[vehicle_type][axle_groups]
        else:
            for batch in range(batches):
                rvs_batches[vehicle_type][f"{axle_groups} [{batch + 1:02}/{batches:02}]"] = rvs_lists[vehicle_type][axle_groups][batch*args.batchsize:(batch+1)*args.batchsize]   

#%% Main window class and helper functions

class RaisedValidator(QValidator):
    def __init__(self, parent = None, window=None):
        QValidator.__init__(self, parent)
        self.acceptable = re.compile("(\d)(,\d)*")
        self.intermediate = re.compile("([\d,])*")
        self.window = window
    
    def validate(self, s, pos):
        if not len(s):
            return (QValidator.Acceptable, s, pos)
        elif self.acceptable.fullmatch(s):
            try:
                self.window.groups_from_raised(s, self.window.rv['axle_groups'])
                return (QValidator.Acceptable, s, pos)
            except:
                return (QValidator.Intermediate, s, pos)
        elif self.intermediate.fullmatch(s):
            return (QValidator.Intermediate, s, pos)
        else:
            return (QValidator.Invalid, s, pos)

from main_window_ui import Ui_MainWindow

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
        
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress and type(source) is QWindow:
            if event.key() == Qt.Key_D:
                self.load_ADMPs()                               
            elif event.key() == Qt.Key_B and not self.radioIsABus.isChecked():
                self.set_vehicle_type('bus')
            elif event.key() == Qt.Key_T and self.radioIsABus.isChecked():
                self.set_vehicle_type('truck')
            elif event.key() == Qt.Key_C:
                self.set_vehicle_type('truck' if self.radioIsABus.isChecked() else 'bus')
            elif event.key() == Qt.Key_L:
                self.chkWrongLane.setCheckState(0 if self.chkWrongLane.checkState() else 2)
            elif event.key() == Qt.Key_V:
                self.chkWrongVehicle.setCheckState(0 if self.chkWrongVehicle.checkState() else 2)
            elif event.key() == Qt.Key_O:
                self.chkOffLane.setCheckState(0 if self.chkOffLane.checkState() else 2)
            elif event.key() == Qt.Key_F:
                self.chkTruncatedFront.setCheckState(0 if self.chkTruncatedFront.checkState() else 2)
            elif event.key() == Qt.Key_B:
                self.chkTruncatedBack.setCheckState(0 if self.chkTruncatedBack.checkState() else 2)
            elif event.key() == Qt.Key_H:
                self.chkVehicleHalved.setCheckState(0 if self.chkVehicleHalved.checkState() else 2)
            elif event.key() == Qt.Key_R:
                self.chkCrosstalk.setCheckState(0 if self.chkCrosstalk.checkState() else 2)
            elif event.key() == Qt.Key_G:
                self.chkGhostAxle.setCheckState(0 if self.chkGhostAxle.checkState() else 2)
            elif event.key() == Qt.Key_I:
                self.chkInconsistentData.setCheckState(0 if self.chkInconsistentData.checkState() else 2)
            elif event.key() == Qt.Key_N:
                self.chkCannotLabel.setCheckState(0 if self.chkCannotLabel.checkState() else 2)
            else:
                pass
        return super().eventFilter(source, event)
    
    def load_data(self, rvs_batches):
        self.rvs_batches = rvs_batches
        self.vehicle_count = {}
        for (vehicle_type, entries) in rvs_batches.items():
            counts = {}
            for key, items in entries.items():
                groups = key.split()[0]
                count = len(items)
                try:
                    counts[groups]['count'] += count
                    counts[groups]['keys'].append((key, count))
                except KeyError:
                    counts[groups] = {'count': count, 'keys': [(key, count)]}
            order = sorted(counts.items(), key=lambda x: x[1]['count'], reverse=True)
            self.vehicle_count[vehicle_type] = [y for x in order for y in x[1]['keys']]
        self.load_cboxAxleGroups()  

    def connect_signals_slots(self):
        self.actionAbout.triggered.connect(self.about)
        self.actionShortcuts.triggered.connect(self.shortcuts)
        self.actionUserManual.triggered.connect(lambda: self.load_file('PDF'))
        self.actionPictureNext.triggered.connect(self.next_photo)
        self.actionPicturePrevious.triggered.connect(self.previous_photo)
        self.actionLoadADMPs.triggered.connect(self.load_ADMPs)

        self.radioSelectBusses.toggled.connect(self.load_cboxAxleGroups)
        self.cboxAxleGroups.currentIndexChanged.connect(self.setup_scrollbarPhoto)
        self.chkOnlyUnseen.toggled.connect(self.setup_scrollbarPhoto)
        self.scrollbarPhoto.valueChanged.connect(self.show_photo)
        self.chkAutoLoadADMPs.toggled.connect(self.set_chkAutoLoadADMPs)
        self.btnShowADMPEvent.clicked.connect(lambda: self.load_file('ADMP'))
        self.btnShowCFEvent.clicked.connect(lambda: self.load_file('CF'))
        self.btnShowPhoto.clicked.connect(lambda: self.load_file('photo'))
        
        self.radioIsABus.toggled.connect(lambda: self.set_vehicle_type('bus'))
        self.radioIsATruck.toggled.connect(lambda: self.set_vehicle_type('truck'))
        self.actionChangeVehicleType.triggered.connect(lambda: self.set_vehicle_type('truck' if self.radioIsABus.isChecked() else 'bus'))
        self.edtGroups.returnPressed.connect(self.set_groups)

        self.edtRaised.setValidator(RaisedValidator(window=self))
        self.edtRaised.returnPressed.connect(self.set_raised)
        self.edtRaised.textChanged.connect(self.check_raised)
            
        self.actionWrongLane.triggered.connect(lambda: self.toggle_checkbox(self.chkWrongLane))
        self.actionWrongVehicle.triggered.connect(lambda: self.toggle_checkbox(self.chkWrongVehicle))
        self.actionOffLane.triggered.connect(lambda: self.toggle_checkbox(self.chkOffLane))
        self.actionTruncatedFront.triggered.connect(lambda: self.toggle_checkbox(self.chkTruncatedFront))
        self.actionTruncatedBack.triggered.connect(lambda: self.toggle_checkbox(self.chkTruncatedBack))
        self.actionVehicleHalved.triggered.connect(lambda: self.toggle_checkbox(self.chkVehicleHalved))
        self.actionCrosstalk.triggered.connect(lambda: self.toggle_checkbox(self.chkCrosstalk))
        self.actionGhostAxle.triggered.connect(lambda: self.toggle_checkbox(self.chkGhostAxle))
        self.actionInconsistentData.triggered.connect(lambda: self.toggle_checkbox(self.chkInconsistentData))
        self.actionCannotLabel.triggered.connect(lambda: self.toggle_checkbox(self.chkCannotLabel))
        
        self.chkWrongLane.stateChanged.connect(lambda: self.set_error(self.chkWrongLane, 'wrong_lane'))
        self.chkWrongVehicle.stateChanged.connect(lambda: self.set_error(self.chkWrongVehicle, 'wrong_vehicle'))
        self.chkOffLane.stateChanged.connect(lambda: self.set_error(self.chkOffLane, 'off_lane'))
        self.chkTruncatedFront.stateChanged.connect(lambda: self.set_error(self.chkTruncatedFront, 'truncated_front'))
        self.chkTruncatedBack.stateChanged.connect(lambda: self.set_error(self.chkTruncatedBack, 'truncated_back'))
        self.chkVehicleHalved.stateChanged.connect(lambda: self.set_error(self.chkVehicleHalved, 'vehicle_halved'))
        self.chkCrosstalk.stateChanged.connect(lambda: self.set_error(self.chkCrosstalk, 'crosstalk'))
        self.chkGhostAxle.stateChanged.connect(lambda: self.set_error(self.chkGhostAxle, 'ghost_axle'))
        self.chkInconsistentData.stateChanged.connect(lambda: self.set_error(self.chkInconsistentData, 'inconsistent_data'))
        self.chkCannotLabel.stateChanged.connect(lambda: self.set_error(self.chkCannotLabel, 'cannot_label'))
        
    def about(self):
        QMessageBox.about(
            self,
            "About BrAId photo labeller",
            "<p>A simple utility to check and manually label AI labelled photos</p>"
            "<p>Jan Kalin &lt;jan.kalin@zag.si&gt;</p>"
            "<p>v1.1, 27. March 2024</p>"
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
            <tr><td><kbd>D</kbd></td><td>Load ADMPs</td></tr>
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td><kbd>B</kbd></td><td>Set vehicle type to <tt>bus</tt></td></tr>
            <tr><td><kbd>T</kbd></td><td>Set vehicle type to <tt>truck</tt></td></tr>
            <tr><td><kbd>C</kbd></td><td>Toggle vehicle type: <tt>bus &lt;--&gt; truck</tt></tr>
            <tr><td><kbd>L</kbd></td><td>Wrong Lane</td></tr>
            <tr><td><kbd>V</kbd></td><td>Wrong Vehicle</td></tr>
            <tr><td><kbd>O</kbd></td><td>Off Lane</td></tr>
            <tr><td><kbd>F</kbd></td><td>Truncated Front</td></tr>
            <tr><td><kbd>B</kbd></td><td>Truncated Back</td></tr>
            <tr><td><kbd>H</kbd></td><td>Vehicle Split</td></tr>
            <tr><td><kbd>R</kbd></td><td>Crosstalk</td></tr>
            <tr><td><kbd>G</kbd></td><td>Ghost Axle</td></tr>
            <tr><td><kbd>I</kbd></td><td>Inconsistent data</td></tr>
            <tr><td><kbd>N</kbd></td><td>Cannot Label</td></tr>
            </table>
            """
        )
                
    def metadata_file_error(self, err):
        beep()
        print("="*75)
        print(f"File {err}\n"
              f"could not be written after waiting for {args.timeout}s.\n\n"
              
"""This can mean that someone else has been writing to the file for some time
or that you have lost connection to the network drive.

In any case, your most recent change has not been saved, so it is recommended,
that you stop working now and investigate the cause of problems!""")
        print("="*75, "\n")
        beep()
        self.groupboxLabel.setTitle("Label: FILESYSTEM PROBLEMS!")
    
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
                self.selected = [x for x in self.rvs_batches[self.vehicle_type()][self.axle_groups()]
                                 if not self.chkOnlyUnseen.isChecked() or not load_metadata(x, metadata_filename, seen_by=True)]
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
                    self.groupboxPhoto.setTitle(f"Photo 0/{self.scrollbarPhoto.maximum() + 1}"
                                                + (f" ({len(rvs_batches[self.vehicle_type()][self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else ""))
                else:
                    self.groupboxPhoto.setTitle("Photo")
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
                self.metadata = load_metadata(self.rv, metadata_filename)
                try:
                    self.last_seen_by = self.metadata['seen_by']
                except:
                    self.last_seen_by = None
                self.metadata['seen_by'] = (datetime.datetime.now().timestamp(), getpass.getuser())
                try:
                    save_metadata(self.rv, self.metadata, metadata_filename, timeout=args.timeout)
                except RuntimeError as err:
                    self.metadata_file_error(err)
                self.show_metadata()
                try:
                    changed = ", CHANGED" if self.metadata['changed_by'] else ", ORIGINAL"
                except:
                    pass
                self.groupboxPhoto.setTitle(f"Photo {self.scrollbarPhoto.sliderPosition() + 1}/{self.scrollbarPhoto.maximum() + 1}"
                                            + (f" ({len(rvs_batches[self.vehicle_type()][self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else "")
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
                    self.chkCrosstalk.setCheckState(self.metadata['errors']['crosstalk'])
                except:
                    self.chkCrosstalk.setCheckState(False)
                try:
                    self.chkGhostAxle.setCheckState(self.metadata['errors']['ghost_axle'])
                except:
                    self.chkGhostAxle.setCheckState(False)
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
                ylim = {}
                for lane, chs in enumerate([['11admp', '11diff'], ['21admp', '21diff']]):
                    for ch in chs:
                        if ch in df.columns:
                            plot[lane].plot(df.index, df[ch], label=f"{ch[-4:]}_{ch[0]}")
                            ylim[lane] = plot[lane].get_ylim()
                for idx, vehicle in enumerate(event.detected_vehicles):
                    (ymin, ymax) = ylim[vehicle.lane]
                    plot[vehicle.lane].vlines([datetime.timedelta(seconds=x.t0/512) + vehicle.event_timestamp for x in vehicle.axle],
                                              ymin, ymin + (ymax - ymin)/10, color='k')
                plot[0].vlines(self.rv['vehicle_timestamp'], ylim[0][0] + (ylim[0][1] - ylim[0][0])/10, ylim[0][1], color='g')
                plot[lane].xaxis.set_major_formatter(self.formatter)
        finally:
            self.fig.canvas.draw_idle()
            QApplication.restoreOverrideCursor()
            
    def load_file(self, region):
        """Loads event and calls external viewer"""
        if self.rv == None and not region == 'PDF':
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if region in ['CF', 'ADMP']:
                fs = (FS(args.siwim_cf_data_root, args.siwim_site, args.siwim_cf_rpindex, args.siwim_cf_module) if region == 'CF'
                      else FS(args.siwim_admp_data_root, args.siwim_site, args.siwim_admp_rpindex, args.siwim_admp_module))
                filename = eventpath(fs, self.rv, v2e)
            elif region == 'photo':
                filename = pngpath(args.photo_root, self.rv)
            elif region == 'PDF': 
                filename = os.path.join(SCRIPT_DIR, 'doc', 'lbp.pdf')
            else:
                raise ValueError(f"Invalid region: {region}")
            shutil.copy(filename, tempfile.gettempdir())
            os.system("start " + os.path.join(tempfile.gettempdir(), os.path.basename(filename)))
        finally:
            QApplication.restoreOverrideCursor()

    def save_changed_metadata(self):
        """Common code for all changes of metadata"""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.metadata['changed_by'] = (datetime.datetime.now().timestamp(), getpass.getuser())
            try:
                save_metadata(self.rv, self.metadata, metadata_filename, args.timeout)
            except RuntimeError as err:
                self.metadata_file_error(err)
            self.show_metadata()
        finally:
            QApplication.restoreOverrideCursor()
        
    def set_vehicle_type(self, vehicle_type):
        """Sets vehicle type"""
        if self.updating_metadata or self.rv == None or self.metadata == None:
            return
        self.metadata['vehicle_type'] = vehicle_type
        self.save_changed_metadata()
        
    def set_groups(self):
        """Sets axle groups"""
        if self.updating_metadata or self.rv == None:
            return
        self.metadata['axle_groups'] = self.edtGroups.text()
        self.save_changed_metadata()
                  
    def groups_from_raised(self, raised, groups):
        """Calculates groups from raised"""
        if not len(raised):
            return groups
        groups = np.array(str2groups(groups))
        parts = raised.split(",")
        for pos in [int(x) for x in parts]:
            if pos < 1 or pos > len(groups):
                raise ValueError(f"Position cannot be less than 1 or greater than {len(groups)}: {pos}")
            groups[pos-1] += 1
        return groups2str(tuple(groups))
    
    def check_raised(self):
        sender = self.sender()
        validator = sender.validator()
        state = validator.validate(sender.text(), 0)[0]
        if state == QValidator.Acceptable:
            color = '#ffffff' # white
            self.edtGroups.setText(self.groups_from_raised(sender.text(), self.rv['axle_groups']))
        elif state == QValidator.Intermediate:
            color = '#fff79a' # yellow
            self.edtGroups.setText(self.groups_from_raised("", self.rv['axle_groups']))
        else:
            color = '#f6989d' # red
        sender.setStyleSheet('QLineEdit { background-color: %s }' % color)        

    def set_raised(self):
        """Sets raised axles"""
        if self.updating_metadata or self.rv == None:
            return
        self.metadata['raised_axles'] = self.edtRaised.text()
        self.set_groups()
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

win.load_data(rvs_batches)

win.show()
sys.exit(app.exec())



