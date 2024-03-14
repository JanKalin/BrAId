# -*- coding: utf-8 -*-
"""
Created on Thu Mar  7 11:29:25 2024

@author: jank
"""

import os
import sys 

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.filesys import FS
from swm.factory import read_file
from swm.utils import Progress

fs = FS(r"s:\sites\original", "AC_Sentvid_2012_2", 0, "camera")
with open(fs.fullname("noon"), 'r') as f:
    noons = [x.strip().replace("/", "\\", -1) for x in f.readlines()]
    
#%% Find first files past noon and write them

try:
    __IPYTHON__
except:
    progress = Progress("Processing {} events... {{}}% ".format(len(noons)), len(noons))
    
for noon in noons:
    try:
        __IPYTHON__
    except:
        progress.step()
        
    dirr = os.path.join(noon, "*.vehiclephotos")
    try:
        file = fs.multiglob(dirr)[0]
    except:
        print(f"No files in {dirr}")
    
    photo = read_file(file)
    for idx, img in enumerate(photo.photos):
        img.image().save(os.path.join(SCRIPT_DIR, "photos", os.path.splitext(os.path.basename(file))[0] + f"_{idx+1}.jpg"))
