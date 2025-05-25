##############################################################################
# This is an example pre lib for driver
##############################################################################

import os

from swm import filesys, txt, utils

##############################################################################
# This example does four things:
# - Sets the usr['braid']['siwim'] field of each vehicle to the number of axles
#   detected by SiWIM and usr['braid']['ai'] to the same number
# - Uses FS() to directly write events in a different output directory
# - Writes the vehicle and event timestamp in one continuous file
# - Writes timestamps of photos in TXT file with timestamp of event
##############################################################################

def post(swu, fs):
    
    # Sets numbers of axles
    for veh in swu.data().weighed_vehicles:
        veh.usr['braid'] = {'siwim': str(len(veh.axle)), 'ai': str(len(veh.axle))}
    
    # Writes vehicle and event timestamps and photo timestamps
    vehicle_event_tss = txt.Txt()
    vehicle_event_tss.filename = "vehicle_event_tss.txt"
    photo_tss = txt.Txt()
    
    # Iterates over data. First element is the event and other are photos
    for idx, obj in enumerate(swu.map['data']):
        if not idx:
            event = obj
            photo_tss.tmstmp = event.tmstmp
            for veh in obj.weighed_vehicles:
                vehicle_event_tss.contents.append(f"{utils.datetime2ts(veh.timestamp)}\t{utils.datetime2ts(veh.event_timestamp)}")
        else:
            photo_tss.contents.append(os.path.splitext(obj.object_filename())[0])

    # Add to appropriate maps
    swu.map['append_lines'] = [vehicle_event_tss]
    swu.map['write_lines'] = [photo_tss]
    
    # Own FS with a different output directory - write event
    myfs = filesys.FS(fs.data_root, fs.site, fs.rpindex, 'mydir', use_pathlib=True)
    swu.data().write_file(mkdir=True, fs=myfs)

    # Done
    return swu
    
