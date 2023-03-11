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
    assert filelist #ensuring the filelist is not empty

    flux_events = []
    one_weights = []
    energies = []
    zeniths = []

    for filename in filelist:

    # open the i3 files with the dataio interface
        infile = dataio.I3File(filename)
        print("Reading " + filename)
        
        # loop over the frames in the file
        while infile.more():
            # get the frame
            frame = infile.pop_frame()

            # if this is an S-Frame
            if frame.Stop == frame.Simulation:
                # get n_flux_events from frame
                n_flux_events = frame["I3GenieInfo"].n_flux_events
                flux_events.append(n_flux_events)

            if frame.Stop == frame.DAQ:
                #get one weight from each Q frame

                mctree = frame["I3MCTree"]
                primary = mctree[0]
                energy = primary.energy
                zenith = primary.dir.zenith
                oneweight = frame["I3MCWeightDict"]["OneWeight"]
                one_weights.append(oneweight)
                energies.append(energy)
                zeniths.append(zenith)

    '''
    Creating a csv file
    '''

    print("CREATING A CSV FILE NOW!")

    # Set a default value to use for missing values
    default_value = ''

    # Create a CSV file with four columns
    with open('/home/akatil/effective_livetime/data/'+str(dataset)+'.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['flux_events', 'one_weights', 'nu_energy', 'nu_zenith'])  # Write the column headers
        for flux_event, one_weight, nu_e, nu_z in zip_longest(flux_events, one_weights, energies, zeniths, fillvalue=default_value):
            writer.writerow([flux_event, one_weight, nu_e, nu_z])  # Write each row

datasets = [120028, 140028, 160028, 121028, 141028, 161028]

for data in datasets:
    print('DATASET:', data)
    csv_effective_time('genie', 1, data)
