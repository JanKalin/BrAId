##############################################################################
# This is an example pre lib for driver
##############################################################################

from swm import filesys

##############################################################################
# Loads images for all vehicles in event
##############################################################################

def pre(swu, fs):
    """Finds and loads images for all vehicles in event"""
    
    # Need own FS() with a different module directory
    myfs = filesys.FS(fs.data_root, fs.site, fs.rpindex, 'camera')
    
    # Loop over vehicles
    for veh in swu.data().weighed_vehicles:
        photos = myfs.vehicle_photos(veh.timestamp)
        if photos:
            swu.map['data'].append(photos)
            
    # Done
    return swu