__version__ = "1.0.0"
##############################################################################
# This is an example SiWIM-Pi plugin script. Make a copy in another directory
# and expand it for your needs.
#
# All logging is done to logs folder into a file with date as the filename.
# To use logging in another file simply import logging and use it the same as
# here. It is thread safe.
#
# Logging options are (in this order of importance) debug, info, warning,
# error and critical. Where logging starts is controlled by "level" parameter
# of logging configuration; For example, If level is "logging.INFO", all
# levels before info are ignored.
#
# If error logging of specific sections is desired to a different file, some
# modifications will have to be made.
#
# All log output is also written to SWM that's returned. If an unhandled
# Python error occurs, the SWU is empty except for the log message
#
# See also documentation `wrapper.pdf` and `siwim_pi.pdf`
##############################################################################

import importlib
import logging
import os
import sys
import time
import traceback

# Get script dir - not the same as CWD.
# All paths need to be relative to this and you MUST NOT do a chdir()

sdir = os.path.split(os.path.realpath(__file__))[0]
sys.path.append(sdir)
sys.path.append(os.path.split(sdir)[0])

# Configure logging

os.makedirs(os.path.join(sdir, 'logs'), exist_ok=True)
logging.basicConfig(filename=os.path.join(sdir, 'logs', f"{time.strftime('%Y-%m-%d')}.log"), level=logging.DEBUG,
                    format='%(asctime)s.%(msecs)03d; %(levelname)s; %(message)s', datefmt='%Y-%m-%d; %H:%M:%S')

# Import SWM

from swm.__init__ import __version__ as __swm_version__
from swm import constants, factory, event, txt

###############################################################################
# Global variables - set when reading CONF files
###############################################################################

# Conf loaded, True by default, so that the script does not acually need any
# confs. Set to False if there's an error when parsing an eventual CONF
_conf_loaded = True

# Dynamic lib for this plugin. It can be supplied at the initialisation of the
# plugin, e.g., to save site-specific reclassification rules
_dyn_module = None

# Extra CONFs, for instance, for vehicle_classes.conf
_kwargs = {}

###############################################################################
# Returns the additional CONFs needed by this plugin
###############################################################################

my_conf_files = [constants.VEHICLE_CLASSES_CONF]

def conf_files(module_name):
    result = txt.Txt()
    result.contents = my_conf_files
    return result.write_blob()

###############################################################################
# Return version on the first run
###############################################################################

_returned_version = False

def return_version(swu):
    global _returned_version
    if _returned_version:
        return
    swu.log('LM_INFO', f"Versions: {os.path.split(os.path.realpath(sdir))[1]} v{__version__}, swm v{__swm_version__}, objects v{constants.OBJECT_VERSION}", False)
    _returned_version = True

###############################################################################
# Process conf
###############################################################################

def process_args_conf(item):
    """Parse CONF. Should throw a ValueError for incorrect/missing stuff""" 
    global _conf_loaded
    _conf_loaded = False

    # Parse conf here

    # And we're done
    _conf_loaded = True
    
###############################################################################
# Possible auxilary functions
###############################################################################



###############################################################################
# The function process_swu() is the entry point and should exist in the entry
# script, as it's the one called by E by default, unless exlicitly overriden in
# CONF file
###############################################################################

def process_swu(module_name, data, wrapper=False):
    """This function reads data, possibly parses and loads parameters and
    other files
    
    Then it processes the data in the SWU and returns a processed SWU
    """
        
    try:
        # Get module name
        module_name, thread, instance = module_name.decode('utf-8').split(':')
           
        # Read SWU and perhaps set version
        swu = factory.read_blob(data)
        return_version(swu)
        
        # Load CONF files
        try:
            for item in swu.map['conf']:
                # Default script CONF
                if item.object_filename() == f"{module_name}_args.conf":
                    process_args_conf(item)
                
                # Additional CONFs
                if item.object_filename() in my_conf_files:
                    try:
                        # Process and/or load CONF here, e.g., say:
                        # ```
                        # global _kwargs
                        # _kwargs.update(classes=vehicle_classes.VehicleClasses(item.conf()))
                        # ```
                        pass
                    except:
                        raise ValueError(f"Invalid {item.object_filename()} contents")
                
                # Dynamic library
                if item.object_filename() == f"{module_name}.py":
                    try:
                        os.makedirs(os.path.join(sdir, "lib"), exist_ok=True)
                        dynamic_module_name = f"{module_name}_{thread}_{instance}_DYNAMIC_MODULE"
                        with open(os.path.join(sdir, "lib", f"{dynamic_module_name}.py"), 'w') as f:
                            f.write('\n'.join(item.contents))
                        global _dyn_module
                        _dyn_module = importlib.import_module(f"lib.{dynamic_module_name}")
                        swu.log('LM_INFO', "Loaded dynamic module", False)
                    except Exception as e:
                        swu.log('LM_ERROR', str(e), True)
                        return swu.value(wrapper)
        except KeyError:
            pass
        except ValueError as e:
            swu.log('LM_ERROR', str(e), True)
            return swu.value(wrapper)
        
        # Just return if we don't have data or if it's not an event
        if not swu.data() or swu.data().class_name() != event.Event.Class_Name():
            return swu.value(wrapper)
        
        # If conf has not been loaded, it's an error
        if not _conf_loaded:
            swu.log('LM_ERROR', f"{module_name}_args.conf not loaded", True)
            return swu.value(wrapper)

        #######################################################################
        # Process data here
        #######################################################################
        
        # And we're done
        return swu.value(wrapper)
   
    # Any non-caught error that occurs during processing is logged as critical.
    except Exception:
        message = " ".join(traceback.format_exc().split('\n'))
        logging.critical(message)
        errswu = factory.SWU()
        errswu.log('LM_CRITICAL', f"Unhandled error in Python scripts: {message}", True)
        return_version(errswu)
        return errswu.value(wrapper)

