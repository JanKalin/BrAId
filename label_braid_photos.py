__version__ = "1.12"

### Import stuff

import argparse
import datetime
import getpass
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np

from PIL import Image, ImageEnhance

from PyQt5.QtCore import Qt, QEvent, QSize, QBuffer, QMutex, QObject, QThread
from PyQt5.QtGui import QPixmap, QImage, QWindow, QValidator
from PyQt5.QtWidgets import  QApplication, QMainWindow, QMessageBox

if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.factory import read_file
from swm.filesys import FS
from swm.utils import datetime2ts, str2groups, groups2str

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from locallib import pngpath, eventpath, load_metadata, save_metadata, beep

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Interactively mark BrAId photos", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--photo_root", help="Root for photos", default=r"B:\yolo_photos")
parser.add_argument("--siwim_site", help="SiWIM site", default=r"AC_Sentvid_2012_2")
parser.add_argument("--siwim_admp_data_root", help="Root for SiWIM ADMP data", default=r"S:\sites\original")
parser.add_argument("--siwim_admp_rpindex", help="SiWIM ADMP replay index", default=40)
parser.add_argument("--siwim_admp_module", help="SiWIM ADMP module", default="vehicle_fad")
parser.add_argument("--siwim_cf_data_root", help="Root for SiWIM calcualated data", default=r"T:\sites\original")
parser.add_argument("--siwim_cf_rpindex", help="SiWIM CF replay index", default=1)
parser.add_argument("--siwim_cf_module", help="SiWIM CF module", default="cf")
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--metadata_dir", help="Metadata directory", default=os.path.join(SCRIPT_DIR, 'data') if getpass.getuser() == 'jank' else r"M:\disk_600_konstrukcije\JanK\braid_photo\data")
parser.add_argument("--count", help="Count vehicles", action='store_true')
parser.add_argument("--timeout", help="File write timeout in seconds", type=int, default=10)
parser.add_argument("--batchsize", help="Batch size for better motivation :)", type=int, default=1000)
parser.add_argument("--noseen_by", help="Do not change `seen_by` metadata. Used for checking", action='store_true')
parser.add_argument("--threaded", help="Use thread to load photos in the background. Currenlty inoperative", action='store_true')

try:
    __IPYTHON__
    if True  and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data --photo e:\yolo_photos --noseen".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

# Force no threads
#args.threaded = False

# Index to color and color to index
i2c = ['r', 'g', 'b', 'c', 'y', 'm', 'w']
c2i = {c: i for (i, c) in enumerate(i2c)}

# Filename
metadata_filename = os.path.join(args.metadata_dir, "metadata.hdf5")
metadata_lock = os.path.join(args.metadata_dir, "metadata.lock")

#%% Load data first and make datetime from timestamps
print(f"label_braid_photos v{__version__} starting up...")

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

rvs_list = {}
for rv in rvs_loaded:
    try:
        rvs_list[rv['axle_groups']].append(rv)
    except:
        rvs_list[rv['axle_groups']] = [rv]


#%% Make batches

rvs_batches = {}
maxbatches = 0
for axle_groups in rvs_list:
    batches = len(rvs_list[axle_groups]) // args.batchsize + 1
    maxbatches = max(maxbatches, batches)
    if batches == 1:
        rvs_batches[axle_groups] = rvs_list[axle_groups]
    else:
        for batch in range(batches):
            rvs_batches[f"{axle_groups} [{batch + 1:02}/{batches:02}]"] = rvs_list[axle_groups][batch*args.batchsize:(batch+1)*args.batchsize]   

#%% Image and validator helper functions

def qpixmap_to_pil_image(qpixmap):
    """
    Convert a QPixmap object to a PIL Image object.
    
    Args:
    qpixmap (QPixmap): The QPixmap object to convert.
    
    Returns:
    PIL.Image: The converted PIL Image object.
    """
    qimage = qpixmap.toImage()
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    qimage.save(buffer, "PNG")
    pil_image = Image.open(io.BytesIO(buffer.data()))
    return pil_image

def pil_image_to_qt_pixmap(pil_image):
    """
    Convert a PIL Image object to a QPixmap object.
    
    Args:
    pil_image (PIL.Image): The PIL Image to convert.
    
    Returns:
    QPixmap: The converted QPixmap object.
    """
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes()
    width, height = pil_image.size
    qimage = QImage(data, width, height, QImage.Format_RGBA8888)
    qpixmap = QPixmap.fromImage(qimage)
    return qpixmap


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

#%% Photo loader. See https://realpython.com/python-pyqt-qthread

class PhotoLoader(QObject):
    """Load photos in a separate thread"""
    
    def __init__(self, debug=False, nocache=False):
        """Initialisation"""
        super(PhotoLoader, self).__init__()
        self.mutex = QMutex()
        self.photos = []
        self.debug = debug
        self.nocache = nocache
        self.stopped = False
        
    def clear(self):
        """Clear list"""
        try:
            self.mutex.lock()
            self.photos = []
        finally:
            self.mutex.unlock()
        
    def setup(self, photos):
        """Set the list of photos to load"""
        try:
            self.mutex.lock()
            self.photos = [[x, None] for x in photos]
            self.last_idx = -1
        finally:
            self.mutex.unlock()
            
    def get_photo(self, idx):
        """Get photo from the cache or load it"""
        try:
            self.mutex.lock()
            if self.photos[idx][1] is not None:
                if self.debug: print(f"Loading {idx} from cache")
                return self.photos[idx]
            else:
                self.last_idx = idx
                if self.debug: print(f"Loading {idx} from disk")
                photo = QPixmap(self.photos[idx][0])
                if not self.nocache:
                    self.photos[idx][1] = photo
                return self.photos[idx][0], photo
        finally:
            self.mutex.unlock()
            
    def stop(self):
        self.stopped = True
        
    def loop(self):
        """Thread running over the list and loading files"""
        while not self.stopped:
            # Half a second per loop is OK
            time.sleep(0.50)
            print("Here")
            
            # Fast operations: continue if we don't have photos or we have loaded all photos
            try:
                self.mutex.lock()
                if not self.photos or not len([x for (_, x) in self.photos if x is None]):
                    print("Nothing to do...")
                    continue
                idx = self.last_idx
                len_photos = len(self.photos)
                while True:
                    idx = (idx + 1) % len_photos
                    if self.photos[idx][1] is None:
                        break
                filename = self.photos[idx][0]
            except:
                raise
            finally:
                self.mutex.unlock()
                
            # Slow operation: Load file
            try:
                print(f"Loading {filename}")
                photo = QPixmap(filename)
                if photo.isNull():
                    print(f"{filename} is null")
                    continue
                print(f"Loaded {filename}: {photo}")
            except:
                raise
            
            # Add to the list if the name is the same and the list is still None
            try:
                self.mutex.lock()
                if self.photos[idx] == [filename, None]:
                    self.photos[idx][1] = photo
                    self.last_idx = idx
                    if self.debug: print(f"Saving {idx} to cache")
                else:
                    if self.debug: print(f"Photo {idx} is not needed anymore!")
            except:
                continue
            finally:
                self.mutex.unlock()
        print("Stopped")
        
        
#%% Main window class

from main_window_ui import Ui_MainWindow

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(f"{self.windowTitle()} v{__version__}, user '{getpass.getuser()}'")
        self.connect_signals_slots()

        self.segment = [self.radioRed,
                        self.radioGrn,
                        self.radioBlu,
                        self.radioCyn,
                        self.radioYel,
                        self.radioMag,
                        self.radioWht]
        
        self.figureCanvasADMP = FigureCanvas(Figure(figsize=(5.5, 2)))
        self.layoutGraph.addWidget(self.figureCanvasADMP)
        self.fig = self.figureCanvasADMP.figure
        self.fig.tight_layout()
        self.locator = mdates.AutoDateLocator()
        # self.formatter = mdates.ConciseDateFormatter(self.locator, offset_formats=['', '%Y', '%Y-%m', '%Y-%m-%d', '%Y-%m-%d', '%Y-%m-%d %H:%M'])
        self.formatter = mdates.DateFormatter("")
        
        self.lblLastSeen.setText("")
        self.lblLastChanged.setText("")
        self.updating_metadata = False
        
        QApplication.instance().installEventFilter(self)
        
        self.D_main_groupboxPhoto = (self.geometry().width() - self.groupboxPhoto.geometry().width(), 
                                     self.geometry().height() - self.groupboxPhoto.geometry().height())
        self.D_groupboxPhoto_scrollbarPhoto = (self.groupboxPhoto.geometry().width() - self.scrollbarPhoto.geometry().left(), 
                                               self.groupboxPhoto.geometry().height() - self.scrollbarPhoto.geometry().height())
        self.D_groupboxPhoto_lblPhoto = (self.groupboxPhoto.geometry().width() - self.lblPhoto.geometry().width(), 
                                         self.groupboxPhoto.geometry().height() - self.lblPhoto.geometry().height())
        
        for s in ['NONE', 'Bus', 'Truck']:
            self.cboxExpectedVehicleType.addItem(s)
        
        if args.threaded:
            self.photoloader = PhotoLoader(debug=True, nocache=False)
            self.thread = QThread()
            self.photoloader.moveToThread(self.thread)
            self.thread.started.connect(self.photoloader.loop)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.start()
        
    def eventFilter(self, source, event):
        if type(source) is QWindow and event.type() == QEvent.KeyPress and QApplication.focusWidget() != self.edtComment:
            if event.key() == Qt.Key_D:
                self.load_ADMPs()
                return True
            elif event.key() == Qt.Key_B and not self.radioIsABus.isChecked():
                self.set_vehicle_type('bus')
                return True
            elif event.key() == Qt.Key_T and not self.radioIsATruck.isChecked():
                self.set_vehicle_type('truck')
                return True
            elif event.key() == Qt.Key_O and not self.radioIsOther.isChecked():
                self.set_vehicle_type('other')
                return True
            elif event.key() == Qt.Key_L:
                self.chkWrongLane.setCheckState(0 if self.chkWrongLane.checkState() else 2)
                return True
            elif event.key() == Qt.Key_F:
                self.chkOffLane.setCheckState(0 if self.chkOffLane.checkState() else 2)
                return True
            elif event.key() == Qt.Key_U:
                self.chkPhotoTruncated.setCheckState(0 if self.chkPhotoTruncated.checkState() else 2)
                return True
            elif event.key() == Qt.Key_H:
                self.chkVehicleHalved.setCheckState(0 if self.chkVehicleHalved.checkState() else 2)
                return True
            elif event.key() == Qt.Key_R:
                self.chkCrosstalk.setCheckState(0 if self.chkCrosstalk.checkState() else 2)
                return True
            elif event.key() == Qt.Key_G:
                self.chkGhostAxle.setCheckState(0 if self.chkGhostAxle.checkState() else 2)
                return True
            elif event.key() == Qt.Key_I:
                self.chkInconsistentData.setCheckState(0 if self.chkInconsistentData.checkState() else 2)
                return True
            elif event.key() == Qt.Key_N:
                self.chkCannotLabel.setCheckState(0 if self.chkCannotLabel.checkState() else 2)
                return True
            elif event.key() == Qt.Key_M:
                self.chkMultipleVehicles.setCheckState(0 if self.chkMultipleVehicles.checkState() else 2)
                return True
            elif event.key() == Qt.Key_Z:
                self.chkZoom.setCheckState(0 if self.chkZoom.checkState() else 2)
                self.show_photo()
                return True
            else:
                pass
        elif source == self.lblPhoto and event.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonDblClick]:
            if event.button() == Qt.MiddleButton:
                self.enhanced_pixmap = self.original_pixmap
                self.show_photo()
                return True
            handle_event = False
            if event.button() in [Qt.LeftButton, Qt.RightButton] and event.type() == QEvent.MouseButtonDblClick and event.modifiers() == Qt.NoModifier:
                factor = 2
                function = ImageEnhance.Contrast if event.button() == Qt.LeftButton else ImageEnhance.Brightness
                handle_event = True
            elif event.button() in [Qt.LeftButton, Qt.RightButton] and event.modifiers() in [Qt.NoModifier, Qt.ShiftModifier]:
                factor = 1.25 if event.modifiers() == Qt.NoModifier else 1/1.25
                function = ImageEnhance.Contrast if event.button() == Qt.LeftButton else ImageEnhance.Brightness
                handle_event = True
            if handle_event:
                self.enhanced_pixmap = pil_image_to_qt_pixmap(function(qpixmap_to_pil_image(self.enhanced_pixmap)).enhance(factor))
                self.show_photo()
                return True
        return super().eventFilter(source, event)
    
    def load_data(self, rvs_batches):
        self.rvs_batches = rvs_batches
        self.vehicle_count = {}
        counts = {}
        for key, items in rvs_batches.items():
            groups = key.split()[0]
            count = len(items)
            try:
                counts[groups]['count'] += count
                counts[groups]['keys'].append((key, count))
            except KeyError:
                counts[groups] = {'count': count, 'keys': [(key, count)]}
        order = sorted(counts.items(), key=lambda x: x[1]['count'], reverse=True)
        self.vehicle_count = [y for x in order for y in x[1]['keys']]
        self.load_cboxAxleGroups()  

    def connect_signals_slots(self):
        self.actionAbout.triggered.connect(self.about)
        self.actionShortcuts.triggered.connect(self.shortcuts)
        self.actionUserManual.triggered.connect(lambda: self.load_file('PDF'))
        self.actionPictureNext.triggered.connect(self.next_photo)
        self.actionPicturePrevious.triggered.connect(self.previous_photo)
        self.actionLoadADMPs.triggered.connect(self.load_ADMPs)
        self.cboxAxleGroups.currentIndexChanged.connect(self.setup_scrollbarPhoto)
        self.chkOnlyUnseen.toggled.connect(self.setup_scrollbarPhoto)
        self.scrollbarPhoto.valueChanged.connect(self.load_photo)
        self.chkAutoLoadADMPs.toggled.connect(self.set_chkAutoLoadADMPs)
        self.btnShowADMPEvent.clicked.connect(lambda: self.load_file('ADMP'))
        self.btnShowCFEvent.clicked.connect(lambda: self.load_file('CF'))
        self.btnShowPhoto.clicked.connect(lambda: self.load_file('photo'))
        self.edtJumpToPhoto.returnPressed.connect(self.jump_to_photo)
        self.chkZoom.toggled.connect(self.show_photo)
        self.radioIsABus.toggled.connect(lambda: self.set_vehicle_type('bus'))
        self.radioIsATruck.toggled.connect(lambda: self.set_vehicle_type('truck'))
        self.radioIsOther.toggled.connect(lambda: self.set_vehicle_type('other'))
        self.edtGroups.textEdited.connect(self.set_groups)
        self.edtRaised.setValidator(RaisedValidator(window=self))
        self.edtRaised.textChanged.connect(self.check_raised)
        self.edtComment.returnPressed.connect(self.set_comment)
        self.radioRed.toggled.connect(lambda: self.set_segment(self.radioRed, 'r'))
        self.radioGrn.toggled.connect(lambda: self.set_segment(self.radioGrn, 'g'))
        self.radioBlu.toggled.connect(lambda: self.set_segment(self.radioBlu, 'b'))
        self.radioCyn.toggled.connect(lambda: self.set_segment(self.radioCyn, 'c'))
        self.radioYel.toggled.connect(lambda: self.set_segment(self.radioYel, 'y'))
        self.radioMag.toggled.connect(lambda: self.set_segment(self.radioMag, 'm'))
        self.radioWht.toggled.connect(lambda: self.set_segment(self.radioWht, 'w'))
        self.actionWrongLane.triggered.connect(lambda: self.toggle_checkbox(self.chkWrongLane))
        self.actionOffLane.triggered.connect(lambda: self.toggle_checkbox(self.chkOffLane))
        self.actionPhotoTruncated.triggered.connect(lambda: self.toggle_checkbox(self.chkPhotoTruncated))
        self.actionVehicleSplit.triggered.connect(lambda: self.toggle_checkbox(self.chkVehicleSplit))
        self.actionVehicleJoined.triggered.connect(lambda: self.toggle_checkbox(self.chkVehicleJoined))
        self.actionCrosstalk.triggered.connect(lambda: self.toggle_checkbox(self.chkCrosstalk))
        self.actionGhostAxle.triggered.connect(lambda: self.toggle_checkbox(self.chkGhostAxle))
        self.actionInconsistentData.triggered.connect(lambda: self.toggle_checkbox(self.chkInconsistentData))
        self.actionCannotLabel.triggered.connect(lambda: self.toggle_checkbox(self.chkCannotLabel))
        self.chkWrongLane.stateChanged.connect(lambda: self.set_error(self.chkWrongLane, 'wrong_lane'))
        self.chkOffLane.stateChanged.connect(lambda: self.set_error(self.chkOffLane, 'off_lane'))
        self.chkPhotoTruncated.stateChanged.connect(lambda: self.set_error(self.chkPhotoTruncated, 'photo_truncated'))
        self.chkVehicleSplit.stateChanged.connect(lambda: self.set_error(self.chkVehicleSplit, 'vehicle_split'))
        self.chkVehicleJoined.stateChanged.connect(lambda: self.set_error(self.chkVehicleJoined, 'vehicle_joined'))
        self.chkCrosstalk.stateChanged.connect(lambda: self.set_error(self.chkCrosstalk, 'crosstalk'))
        self.chkGhostAxle.stateChanged.connect(lambda: self.set_error(self.chkGhostAxle, 'ghost_axle'))
        self.chkInconsistentData.stateChanged.connect(lambda: self.set_error(self.chkInconsistentData, 'inconsistent_data'))
        self.chkMultipleVehicles.stateChanged.connect(lambda: self.set_error(self.chkMultipleVehicles, 'multiple_vehicles'))
        self.chkCannotLabel.stateChanged.connect(lambda: self.set_error(self.chkCannotLabel, 'cannot_label'))
        
    def resizeEvent(self, event):
        """Called when main window size changes, resizes groupboxPhoto and
        contents"""
        if event.oldSize() == QSize(-1, -1):
            return
        
        geometry = self.groupboxPhoto.geometry()
        geometry.setWidth(event.size().width() - self.D_main_groupboxPhoto[0])
        geometry.setHeight(event.size().height() - self.D_main_groupboxPhoto[1])
        self.groupboxPhoto.setGeometry(geometry)
        
        geometry = self.scrollbarPhoto.geometry()
        geometry.moveLeft(self.groupboxPhoto.geometry().width() - self.D_groupboxPhoto_scrollbarPhoto[0])
        geometry.setHeight(self.groupboxPhoto.geometry().height() - self.D_groupboxPhoto_scrollbarPhoto[1])
        self.scrollbarPhoto.setGeometry(geometry)
        
        geometry = self.lblPhoto.geometry()
        geometry.setWidth(self.groupboxPhoto.geometry().width() - self.D_groupboxPhoto_lblPhoto[0])
        geometry.setHeight(self.groupboxPhoto.geometry().height() - self.D_groupboxPhoto_lblPhoto[1])
        self.lblPhoto.setGeometry(geometry)
        
        if self.rv != None:
            self.show_photo()

    def about(self):
        QMessageBox.about(
            self,
            "About BrAId photo labeller",
            "<p>A simple utility to check and manually label AI labelled photos</p>"
            "<p>Jan Kalin &lt;jan.kalin@zag.si&gt;</p>"
            "<p>v1.5, 14. May 2024</p>"
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
            <tr><td><kbd>Z</kbd></td><td>Zoom in/out of the box</td></tr>
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td><kbd>B</kbd></td><td>Set vehicle type to <tt>bus</tt></td></tr>
            <tr><td><kbd>T</kbd></td><td>Set vehicle type to <tt>truck</tt></td></tr>
            <tr><td><kbd>O</kbd></td><td>Set vehicle type to <tt>other</tt></td></tr>
            <tr><td><kbd>L</kbd></td><td>Wrong Lane</td></tr>
            <tr><td><kbd>V</kbd></td><td>Wrong Vehicle</td></tr>
            <tr><td><kbd>F</kbd></td><td>Off Lane</td></tr>
            <tr><td><kbd>U</kbd></td><td>Photo Truncated</td></tr>
            <tr><td><kbd>S</kbd></td><td>Vehicle Split in Half</td></tr>
            <tr><td><kbd>J</kbd></td><td>Two Vehicles Joined</td></tr>
            <tr><td><kbd>R</kbd></td><td>Crosstalk</td></tr>
            <tr><td><kbd>G</kbd></td><td>Ghost Axle</td></tr>
            <tr><td><kbd>I</kbd></td><td>Inconsistent data</td></tr>
            <tr><td><kbd>M</kbd></td><td>Multiple vehicles</td></tr>
            <tr><td><kbd>N</kbd></td><td>Cannot Label</td></tr>
            </table>
            """
        )
                
    def is_locked(self):
        """Checks if the metadata file is locked and displays message if it is"""
        if os.path.isfile(metadata_lock):
            QMessageBox.critical(
                self,
                "metadata.hdf5 is locked",
                "<p>Sorry, the metadata.hdf5 file, containing labels, is currently locked by the administrator"
                " for maintenance or upgrade.</p><p>Unfortunately you will not be able to label photos"
                " and the last change made for this photo will not be written."
                " Please check email for further details and expected time of unlocking.</p>"
                "<p>Jan Kalin &lt;jan.kalin@zag.si&gt;</p>"
            )
            return True
        return False
    
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
    
    def axle_groups(self):
        """Returns axle groups, read from combo box"""
        if not self.cboxAxleGroups.currentIndex():
            return None
        else:
            return self.vehicle_count[self.cboxAxleGroups.currentIndex() - 1][0]
        
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
        self.cboxAxleGroups.addItems([f"{groups} ({count})" for groups, count in self.vehicle_count])

    def setup_scrollbarPhoto(self):
        """Sets up scroll bar for photo selection and shows the first photo"""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.selected = [x for x in self.rvs_batches[self.axle_groups()]]
                                 # if not self.chkOnlyUnseen.isChecked() or not load_metadata(x, metadata_filename, seen_by=True)]
                self.scrollbarPhoto.setMaximum(len(self.selected) - 1)
                self.scrollbarPhoto.setValue(0)
                if args.threaded: 
                    self.photoloader.setup(pngpath(args.photo_root, x) for x in self.selected)
            except:
                self.scrollbarPhoto.setMaximum(0)
                self.scrollbarPhoto.setValue(0)
        finally:
            QApplication.restoreOverrideCursor()
        self.load_photo()

    def previous_photo(self):
        """Shows previous photo"""
        self.scrollbarPhoto.setValue(self.scrollbarPhoto.sliderPosition() - 1)        
        
    def next_photo(self):
        """Shows next photo"""
        self.scrollbarPhoto.setValue(self.scrollbarPhoto.sliderPosition() + 1)
        
    def jump_to_photo(self):
        """Jumps to photo"""
        if not self.axle_groups() or self.scrollbarPhoto.sliderPosition() == -1:
            return
        try:
            idx = int(self.edtJumpToPhoto.text()) - 1
            self.scrollbarPhoto.setValue(idx)
        except:
            beep()
            return
        
        
    def load_photo(self):
        """Shows photo, loads metadata, updates 'seen_by' and perhaps loads ADMPs"""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if not self.axle_groups() or self.scrollbarPhoto.sliderPosition() == -1:
                self.lblPhoto.clear()
                self.rv = None
                self.metadata = None
                if self.scrollbarPhoto.sliderPosition() == -1:
                    self.groupboxPhoto.setTitle(f"Photo 0/{self.scrollbarPhoto.maximum() + 1}"
                                                + (f" ({len(rvs_batches[self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else ""))
                else:
                    self.groupboxPhoto.setTitle("Photo")
            else:
                if self.is_locked():
                    win.cboxAxleGroups.setCurrentIndex(0);
                    return
                self.rv = self.selected[self.scrollbarPhoto.sliderPosition()]
                try:
                    if args.threaded:
                        filename, self.original_pixmap = self.photoloader.get_photo(self.scrollbarPhoto.sliderPosition())
                    else:
                        filename = pngpath(args.photo_root, self.rv)
                        self.original_pixmap = QPixmap(filename)
                        if self.original_pixmap.isNull():
                            raise RuntimeError
                except:
                    print(f"Cannot load photo {filename}")
                    beep()
                    self.metadata = None
                    return
                if int(self.edtAutoContrast.text()) or int(self.edtAutoBrightness.text()):
                    enhanced_pixmap = self.original_pixmap
                    if int(self.edtAutoContrast.text()):
                        enhanced_pixmap = pil_image_to_qt_pixmap(ImageEnhance.Contrast(qpixmap_to_pil_image(enhanced_pixmap)).enhance(1+int(self.edtAutoContrast.text())/100))
                    if int(self.edtAutoBrightness.text()):
                        enhanced_pixmap = pil_image_to_qt_pixmap(ImageEnhance.Brightness(qpixmap_to_pil_image(enhanced_pixmap)).enhance(1+int(self.edtAutoBrightness.text())/100))
                    self.enhanced_pixmap = enhanced_pixmap
                else:
                    self.enhanced_pixmap = self.original_pixmap
                self.metadata = load_metadata(self.rv, metadata_filename)
                self.show_photo()
                try:
                    self.last_seen_by = self.metadata['seen_by']
                except:
                    self.last_seen_by = None
                if not args.noseen_by:
                    self.metadata['seen_by'] = (datetime.datetime.now().timestamp(), getpass.getuser())
                    try:
                        save_metadata(self.rv, self.metadata, metadata_filename, timeout=args.timeout)
                    except RuntimeError as err:
                        self.metadata_file_error(err)
                changed = ", ORIGINAL"
                try:
                    if self.metadata['changed_by']:
                        changed = ", CHANGED"
                except:
                    pass
                self.groupboxPhoto.setTitle(f"Photo {self.scrollbarPhoto.sliderPosition() + 1}/{self.scrollbarPhoto.maximum() + 1}"
                                            + (f" ({len(rvs_batches[self.axle_groups()]) - len(self.selected)} already seen)" if self.chkOnlyUnseen.isChecked() else "")
                                            + f", veh. ts: {datetime2ts(self.rv['vehicle_timestamp'], excel=True)}"
                                            + f", photo id: {self.rv['photo_id']}"
                                            + f", photo ts: {datetime2ts(self.rv['photo_timestamp'], excel=True)}"
                                            + f"{changed}")
            self.load_ADMPs(force_clear=not self.chkAutoLoadADMPs.isChecked())
            self.show_metadata()
        except:
            raise
        finally:
            QApplication.restoreOverrideCursor()
            
    def show_photo(self):
        """Shows zoomed or unzoomed photo"""
        to_show = self.enhanced_pixmap
        if self.chkZoom.isChecked():
            try:
                color = self.metadata['segment']
            except:
                color = 'r'
            for segment in self.rv['segments']:
                if segment['box']['color'] == color:
                    to_show = self.enhanced_pixmap.copy(segment['box']['x'], segment['box']['y'], segment['box']['width'], segment['box']['height'])
                    break
        self.lblPhoto.setPixmap(to_show.scaled(self.lblPhoto.geometry().width(), self.lblPhoto.geometry().height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    
    
    def show_metadata(self):
        """Shows metadata in the 'Label' group box
        First sets self.updating_metadata = True to prevent any loops and stuff
        """
        def frmt(t):
            return t.strftime('%a, %d. %b %Y at %H:%M:%S')
        
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
                self.lblLastSeen.setText(f"Seen: {at} '{by}'")
                try:
                    at = frmt(datetime.datetime.fromtimestamp(self.metadata['changed_by'][0]))
                    by = self.metadata['changed_by'][1]
                    self.lblLastChanged.setText(f"Chng: {at} '{by}'")
                except (KeyError, IndexError, TypeError):
                    self.lblLastChanged.setText("")
                
                # Axle groups and raised
                try:
                    self.edtGroups.setText(self.metadata['axle_groups'])
                except:
                    self.edtGroups.setText(self.rv['axle_groups'])
                try:
                    self.edtRaised.setText(self.metadata['raised_axles'])
                except:
                    self.edtRaised.setText("")
                    
                # Selected
                try:
                    segment = self.metadata['segment']
                except:
                    segment = 'r'
                colors = [x['box']['color'] for x in self.rv['segments']]
                for idx in range(len(self.segment)):
                    self.segment[idx].setVisible(i2c[idx] in colors)
                    self.segment[idx].setChecked(i2c[idx] == segment)
                    
                #  Vehicle type
                self.set_vehicle_type_radio_button()
                
                # Comment
                try:
                    self.edtComment.setText(self.metadata['comment'])
                except:
                    self.edtComment.setText("")
                    
                # Errors
                try:
                    self.chkWrongLane.setCheckState(self.metadata['errors']['wrong_lane'])
                except:
                    self.chkWrongLane.setCheckState(False)
                try:
                    self.chkOffLane.setCheckState(self.metadata['errors']['off_lane'])
                except:
                    self.chkOffLane.setCheckState(False)
                try:
                    self.chkPhotoTruncated.setCheckState(self.metadata['errors']['photo_truncated'])
                except:
                    self.chkPhotoTruncated.setCheckState(False)
                try:
                    self.chkCrosstalk.setCheckState(self.metadata['errors']['crosstalk'])
                except:
                    self.chkCrosstalk.setCheckState(False)
                try:
                    self.chkGhostAxle.setCheckState(self.metadata['errors']['ghost_axle'])
                except:
                    self.chkGhostAxle.setCheckState(False)
                try:
                    self.chkVehicleSplit.setCheckState(self.metadata['errors']['vehicle_split'])
                except:
                    self.chkVehicleSplit.setCheckState(False)
                try:
                    self.chkVehicleJoined.setCheckState(self.metadata['errors']['vehicle_joined'])
                except:
                    self.chkVehicleJoined.setCheckState(False)
                try:
                    self.chkCannotLabel.setCheckState(self.metadata['errors']['cannot_label'])
                except:
                    self.chkCannotLabel.setCheckState(False)
                try:
                    self.chkInconsistentData.setCheckState(self.metadata['errors']['inconsistent_data'])
                except:
                    self.chkInconsistentData.setCheckState(False)
                try:
                    self.chkMultipleVehicles.setCheckState(self.metadata['errors']['multiple_vehicles'])
                except:
                    self.chkMultipleVehicles.setCheckState(False)
                try:
                    self.lblReconstructed.setStyleSheet("background-color: rgb(0, 255, 0);" if self.metadata['errors']['reconstructed'] else "")
                except:
                    self.lblReconstructed.setStyleSheet("")
                try:
                    self.lblFixed.setStyleSheet("background-color: rgb(0, 255, 0);" if self.metadata['errors']['fixed'] else "")
                except:
                    self.lblFixed.setStyleSheet("")
                    
        finally:
            self.updating_metadata = False
            self.setFocus()
            
    def set_vehicle_type_radio_button(self):
        """Sets vehicle type radio button"""
        try:
            segment = self.metadata['segment']
            raise
        except:
            try:
                segment = self.rv['segment']
            except:
                segment = 'r'
        try:
            vehicle_type = self.metadata['vehicle_type']
        except:
            vehicle_type = self.rv['segments'][c2i[segment]]['type']
        if vehicle_type == 'bus' and not self.radioIsABus.isChecked():
            self.radioIsABus.setChecked(True)
        elif vehicle_type == 'truck' and not self.radioIsATruck.isChecked():
            self.radioIsATruck.setChecked(True)
            if self.cboxExpectedVehicleType.currentText() not in ['NONE', 'Truck']:
                self.radioIsATruck.setStyleSheet("background-color: rgb(255, 49, 49);")
        elif vehicle_type == 'other' and not self.radioIsOther.isChecked():
            self.radioIsOther.setChecked(True)
        for radio in [self.radioIsABus, self.radioIsATruck, self.radioIsOther]:
            radio.setStyleSheet("")
        if vehicle_type == 'bus' and self.cboxExpectedVehicleType.currentText() not in ['NONE', 'Bus']:
            self.radioIsABus.setStyleSheet("color: rgb(255, 255, 255); background-color: rgb(255, 49, 49);")
        if vehicle_type == 'truck' and self.cboxExpectedVehicleType.currentText() not in ['NONE', 'Truck']:
            self.radioIsATruck.setStyleSheet("color: rgb(255, 255, 255); background-color: rgb(255, 49, 49);")
        
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
                            plot[lane].plot(df.index, df[ch])
                            ylim[lane] = plot[lane].get_ylim()
                axle_distance = None
                for idx, vehicle in enumerate(event.detected_vehicles):
                    (ymin, ymax) = ylim[vehicle.lane]
                    plot[vehicle.lane].vlines([datetime.timedelta(seconds=x.t0/512) + vehicle.event_timestamp for x in vehicle.axle],
                                              ymin, ymin + (ymax - ymin)/10, color='k')
                    if vehicle.timestamp == self.rv['vehicle_timestamp']:
                        axle_distance = vehicle.axle_distance
                plot[0].vlines(self.rv['vehicle_timestamp'], ylim[0][0] + (ylim[0][1] - ylim[0][0])/10, ylim[0][1], color='g')
                if axle_distance is not None:
                    plot[0].text(plot[0].get_xlim()[1], plot[0].get_ylim()[1], "\n".join([f"$A_{i+1}$: {x:5.2f}m" for (i, x) in enumerate(axle_distance)]),
                                 ha='right', va='top')
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
            if self.is_locked():
                return
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
        """Checks if the raised is OK and sets groups if it is"""
        sender = self.sender()
        validator = sender.validator()
        state = validator.validate(sender.text(), 0)[0]
        if state == QValidator.Acceptable:
            color = '#ffffff' # white
            if not(self.updating_metadata or self.rv == None):
                self.edtGroups.setText(self.groups_from_raised(sender.text(), self.rv['axle_groups']))
                self.metadata['raised_axles'] = self.edtRaised.text()
                self.metadata['axle_groups'] = self.edtGroups.text()
                self.save_changed_metadata()
        elif state == QValidator.Intermediate:
            color = '#fff79a' # yellow
            if not(self.updating_metadata or self.rv == None):
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
        
    def set_segment(self, radio, color):
        """Sets segment"""
        if self.updating_metadata or self.rv == None:
            return
        self.metadata['segment'] = color
        self.save_changed_metadata()
        self.updating_metadata = True
        self.set_vehicle_type_radio_button()
        self.updating_metadata = False
        if self.chkZoom.isChecked():
            self.show_photo()

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
    
    def set_comment(self):
        if self.updating_metadata or self.rv == None:
            return
        self.metadata['comment'] = self.edtComment.text()
        self.save_changed_metadata()
        self.setFocus()
        


# Load window
app = QApplication(sys.argv)
win = Window()
win.load_data(rvs_batches)

# DEBUG
if getpass.getuser() == 'jank':
    win.cboxAxleGroups.setCurrentIndex(win.cboxAxleGroups.count() - 46)

# Run main loop
print("Good lick (ref.: 'Allo 'Allo)")
win.show()
result = app.exec()

# Done
if args.threaded:
    win.photoloader.stop()
print("Bye")
sys.exit(result)
