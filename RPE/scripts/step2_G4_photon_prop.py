##!/usr/bin/env python

'''
Upgrade MC step2 - photon propagation

This is configured with low energy (Upgrade/DeepCore) events in mind
'''

from optparse import OptionParser
import os, sys
from os.path import expandvars

from icecube import dataio, dataclasses, icetray, phys_services, sim_services
from icecube.icetray import I3Units
from I3Tray import *
from icecube.gen2_sim.segments.clsim import MakePhotonsMultiSensor
from icecube.oscNext.tools.file_transfer import gridftp_fileio

import numpy as np


#
# Get args
#

usage = "usage: %prog [options]"
parser = OptionParser(usage)
parser.add_option("-o", "--outfile",default="./test_output.i3",
                  dest="OUTFILE", help="Write output to OUTFILE (.i3{.gz} format)")
parser.add_option("-i", "--infile",default="./test_input.i3",
                  dest="INFILE", help="Read input from INFILE (.i3{.gz} format)")
parser.add_option("-r", "--runnumber", type="int",
                  dest="RUNNUMBER", help="The run number for this simulation, is used as seed for random generator")
parser.add_option("-l", "--filenr",type="int",
                  dest="FILENR", help="File number, stream of I3SPRNGRandomService")
parser.add_option("-g", "--gcdfile", default=os.getenv('GCDfile'),
                  dest="GCDFILE", help="Read in GCD file")
parser.add_option("-m","--icemodel", default="spice_lea",
                  dest="ICEMODEL",help="Ice model (spice_mie, spice_lea, etc)")
parser.add_option("-a", "--holeice",  default="angsens/as.flasher_p1_0.30_p2_-1", dest="HOLEICE", 
                  help="Pick the hole ice parameterization, corresponds to a file name path relative to $I3_SRC/ice-models/resources/models/") 
parser.add_option("-e","--efficiency", type="float",default=1.2, # Using efficiency > 1 as default so we can support systematics sets
                  dest="EFFICIENCY",help="DOM Efficiency ... the same as UnshadowedFraction")
parser.add_option("--oversize", default=1, type=int,
                  dest="OVERSIZE", help="DOM oversize factor to use. Use this carefully!")
parser.add_option("-t", "--gpu", action="store_true",  dest="GPU", default=False ,help="Run on GPUs or CPUs")
parser.add_option("--gridftp", dest = "GRIDFTP", action="store_true", 
                    help="Indicate that grid FTP is being used for file I/O")
parser.add_option("--tmp-dir",default=None, #TODO better default, e.g. default to using this feature
                    dest="TMPDIR", help="Tmp directory for intermediate file writing")

(options,args) = parser.parse_args()

if len(args) != 0:
    crap = "Got undefined options:"
    for a in args:
        crap += a
        crap += " "
        parser.error(crap)

# Warnings
if options.OVERSIZE != 1:
    print("Oversizing enabled with pancake factor {}! Not recommended unless you know what you're doing!".format(options.OVERSIZE))

# Reporting
print("Settings :")
print("  Run number : %i" % options.RUNNUMBER)
print("  File number : %i" % options.FILENR)
print("  GCD file : %s" % options.GCDFILE)
print("  Ice model : %s" % options.ICEMODEL)
print("  Hole ice model : %s" % options.HOLEICE)
print("  Efficiency : %0.3g" % options.EFFICIENCY)
print("  Oversizing : %0.3g" % options.OVERSIZE)
if options.GRIDFTP :
    print("  Using GridFTP")
if options.TMPDIR :
    print("  Tmp dir : %s" % options.TMPDIR)


#
# IceTray
#

@gridftp_fileio
def step_2_icetray(gcd_file, input_file, output_file) :
    '''
    The step2 icetray job
    Using a decorator to add gridftp file I/O support
    '''

    #
    # Start up
    #

    # Create tray
    tray = I3Tray()

    # RNG seeding
    seed = options.RUNNUMBER
    streamnum = options.FILENR
    nstreams =  100000

    # Create RNG
    randomService = phys_services.I3SPRNGRandomService(
        seed=seed,
        nstreams=nstreams,
        streamnum=streamnum,
    )

    # Also RNG servce with same settings #TODO why?
    tray.AddService("I3SPRNGRandomServiceFactory", "sprngrandom")(
            ("Seed", seed),
            ("StreamNum", streamnum),
            ("NStreams", nstreams),
            ("instatefile",""),
            ("outstatefile",""),
    )

    # Input file reader
    tray.AddModule('I3Reader', 'reader', FilenameList=[gcd_file, input_file])


    #
    # Photon propagation
    #

    # Define photon object
    photon_series = "I3PhotonSeriesMap"

    # Photon propagation    
    tray.AddSegment(
        MakePhotonsMultiSensor, 
        "makephotons_multisensor",
        GCDFile=gcd_file,
        UseCPUs=(not options.GPU),
        UseGPUs=options.GPU,
        InputMCTree="I3MCTree",
        OutputMCTreeName=None,
        OutputPhotonSeriesName=photon_series,
        RandomService=randomService,
        IceModelLocation=expandvars("$I3_SRC/ice-models/resources/models/"),
        IceModel=expandvars(options.ICEMODEL), #TODO Merge with arg above?
        HoleIceParameterization=expandvars("$I3_SRC/ice-models/resources/models/%s"%options.HOLEICE), # this one is used only to get the maximum of the curve, no hole ice is applied at this stage
        DisableTilt=False,
        DOMOversizeFactor=options.OVERSIZE,
        UnshadowedFraction=options.EFFICIENCY,
        EfficiencyScale=2.2, #TODO why 2.2? Maybe need to be max value used in step3 (for various sensor types)?
        UseGeant4=False,
        UseI3PropagatorService=False,
        CrossoverEnergyEM=0.1,
        CrossoverEnergyHadron=100.0,
        StopDetectedPhotons=True,    
        IgnoreSubdetectors=['IceTop', 'NotOpticalSensor' ],
        # TotalEnergyToProcess = 0., # Removed when merging with gen2-optical-sim
        # ParallelEvents=1000, # Removed when merging with gen2-optical-sim
    )


    # Filter events that produced no photon hits on sensors
    def BasicPhotonFilter(frame):
        n_photons = 0
        if frame.Has(photon_series):
            n_photons = len(frame.Get(photon_series))
        if n_photons>0:
            return True
        else:
            return False

    tray.AddModule(BasicPhotonFilter, "remove_zero_light", Streams=[icetray.I3Frame.DAQ])


    #
    # Tear down
    #

    # Write output files
    tray.AddModule(
        "I3Writer",
        "writer",
        Filename=output_file,
        Streams=[icetray.I3Frame.Simulation, icetray.I3Frame.TrayInfo, icetray.I3Frame.DAQ],
    )

    # Run
    tray.Execute()
    tray.Finish()


#
# Run
#

step_2_icetray(
    gridftp=options.GRIDFTP,
    gcd_file=options.GCDFILE,
    input_file=options.INFILE,
    output_file=options.OUTFILE,
    tmp_dir=options.TMPDIR,
)
