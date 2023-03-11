from icecube import dataclasses, dataio, icetray, simclasses
from icecube.icetray import I3Units
import matplotlib.pyplot as plt
import numpy as np
import argparse, matplotlib
from glob import glob
import csv
from itertools import zip_longest

def csv_effective_time(generator,step, dataset):
    '''
    
    Looping over files od each type to get nu flux events, oneWeights, energies and zeniths 
    (energy and zenith required for atmospheric flux)
    
    120XXX - NuE
    121XXX - NuEBar
    140XXX - NuMu
    141XXX - NuMuBar
    160XXX - NuTau
    161XXX - NuTauBar
    
    '''
    
    FILE_DIR = "/data/sim/IceCubeUpgrade/" + str(generator) + "/step" + str(step) + "/" + str(dataset)
    
    print(FILE_DIR)
    
    filelist = sorted(glob(FILE_DIR + "/upgrade_" + str(generator) + "_step" + str(step) + "_" + str(dataset) + "_*.i3.zst"))
    print('File list length:', len(filelist))
    assert filelist #ensuring the filelist is not empty
    
    flux_events = []
    one_weights = []
    energies = []
    zeniths = []
    muon_weights = []

    for filename in filelist:
        
    # open the i3 files with the dataio interface
        infile = dataio.I3File(filename)
        print("Reading " + filename)
        
        # loop over the frames in the file
        while infile.more():
            # get the frame
            frame = infile.pop_frame()
                
            if frame.Stop == frame.DAQ:
                #get one weight from each Q frame
                muon_weight = frame["MuonWeight"].value
                muon_weights.append(muon_weight/(500*2000000))
    print('MuonWeights length:', len(muon_weights))
    return muon_weights
  
  
muon_weights = np.nan_to_num(np.array(csv_effective_time('muongun', 1, 131028)), nan=0)

print((sum(muon_weights**2)/sum(muon_weights)))
