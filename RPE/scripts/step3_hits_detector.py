 ##!/usr/bin/env python

'''
Upgrade MC step3 - detector simulation

This is configured with low energy (Upgrade/DeepCore) events in mind
'''


from optparse import OptionParser
import os, sys
from os.path import expandvars
from copy import deepcopy

from icecube import dataio, dataclasses, icetray, phys_services, simclasses, sim_services, DOMLauncher, DomTools, trigger_sim
from icecube.icetray import I3Units
from icecube.dataclasses import I3OMGeo
from I3Tray import *
from icecube.oscNext.tools.file_transfer import gridftp_fileio

import numpy as np

icetray.logging.set_level(icetray.logging.I3LogLevel.LOG_INFO)


#
# Get args
#

usage = "usage: %prog [options]"
parser = OptionParser(usage)
# File IO args...
parser.add_option("-o", "--outfile",
                  dest="OUTFILE", help="Give Output Directory")
parser.add_option("-i", "--infile",
                  dest="INFILE", help="Read input from INFILE (.i3{.gz} format)")
parser.add_option("-r", "--runnumber", type="int",
                  dest="RUNNUMBER", help="The run number for this simulation, is used as seed for random generator")
parser.add_option("-l", "--filenr",type="int",
                  dest="FILENR", help="File number, stream of I3SPRNGRandomService")
parser.add_option("-g", "--gcdfile", default=os.getenv('GCDfile'),
                  dest="GCDFILE", help="Read in GCD file")
# Noise related args...
parser.add_option("-b", "--mdomglass", default="vitrovex",
                  dest="GLASS", help="mDOM Glass")
parser.add_option("-n", "--interpmt_noise", default=False,
                  dest="pregeneratedmDOM", action="store_true",
                  help="Run the implementation of the new inter-pmt mDOM noise?")
parser.add_option("--interpmt_noise_file", default=None,
                  dest="pregeneratedmDOMNoiseFile", type="str",
                  help="The file containing noise pulses to sample from when using pregenerated noise files")
parser.add_option("--usemDOMwavedeformsimulation", default=False,
                  dest="usemDOMwavedeformsimulation", action="store_true",
                  help="Run the more sophisticated mDOM wavedeform simulation?")
parser.add_option("--noise-only", default=False,
                  dest="NOISEONLY", action="store_true",
                  help="Only generate noise (used as the first step in noise-only MC production")
parser.add_option("--nonoise", default=False,
                  dest="NONOISE", action="store_true",
                  help="Turn off noise")
# Readout placeholder args...
parser.add_option("--no_time_smearing", default=False,
                  dest="NOTIMESMEARING", action="store_true",
                  help="Apply reco pulse time smearing")
parser.add_option("--pulse_bin_width", default=2.0, type=float,
                  dest="BINWIDTH", help="Pulse bin width for combining PEs")
# Ice and detector args...
#parser.add_option("-m","--icemodel", default="spice_lea",
#                   dest="ICEMODEL",help="Ice model (spice_mie, spice_lea, etc)")
parser.add_option("-a", "--holeice",  default=None, dest="HOLEICE",
                  help="Pick the hole ice parameterization, corresponds to a file name path relative to $I3_SRC/ice-models/resources/models/")
parser.add_option("-e","--efficiency", default=None, action='append',
                  dest="EFFICIENCY",help="Module Efficiencies")
# Other
parser.add_option("--nevents",type="int",default=None, # Only for noise-only events
                  dest="NEVENTS", help="Number of noise frames to create")
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

# Check arg compatibility
if options.NOISEONLY :
  assert not options.NONOISE, "Cannot choose both 'no noise and 'only noise'"
  assert options.INFILE is None, "Cannot specifiy an input file in noise-only mode"
  assert options.NEVENTS is not None, "Must specify number of events for noise-only mode"
  #assert options.ICEMODEL is None
  assert options.HOLEICE is None
  assert options.EFFICIENCY is None
  print("Generating noise-only MC...")
else :
  assert options.INFILE is not None, "Must provide an input file"
  assert options.NEVENTS is None, "Cannot specify number of events unless in noise-only mode"
  #assert options.ICEMODEL is not None
  assert options.HOLEICE is not None
  assert options.EFFICIENCY is not None

# Reporting
print("Settings :")
print("  Run number : %i" % options.RUNNUMBER)
print("  File number : %i" % options.FILENR)
print("  GCD file : %s" % options.GCDFILE)

if not options.NOISEONLY :
    #print("  Ice model : %s" % options.ICEMODEL)
    print("  Hole ice model : %s" % options.HOLEICE)
    print("  Efficiencies : %s" % options.EFFICIENCY)

#TODO more...
if options.GRIDFTP :
    print("  Using GridFTP")
if options.TMPDIR :
    print("  Tmp dir : %s" % options.TMPDIR)


#
# IceTray
#

@gridftp_fileio
def step_3_icetray(gcd_file, input_file, output_file, run_number) :
    '''
    The step3 icetray job
    Using a decorator to add gridftp file I/O support
    '''
    #
    # Start up
    #

    # Create tray
    tray = I3Tray()

    # RNG seeding
    seed = run_number #options.RUNNUMBER
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

    # Create driver
    if options.NOISEONLY :
        # Empty frame source
        tray.AddModule("I3InfiniteSource", "source", Stream=icetray.I3Frame.DAQ, prefix=gcd_file)
    else :
        # Input file reader
        tray.AddModule('I3Reader', 'reader', FilenameList=[gcd_file, input_file])


    #
    # Get sensor definitions
    #

    ##########
    # Need to determine which to use from GCD file. For now, use everything
    # except WOMs, which we don't have properly implemented.
    ##########
    from icecube.gen2_sim.utils import ModuleToString, FindModuleTypes
    Sensors, EfficiencyScales, MCPEs = FindModuleTypes(gcd_file)

    if not options.EFFICIENCY is None:
        EfficiencyScales *= np.array(options.EFFICIENCY).astype(float)

    print("GCD file contains modules with these sensor types:")
    for i, Sensor in enumerate(Sensors):
        print('\t ', ModuleToString(Sensor, Prefix=''), '(EfficiencyScale:', EfficiencyScales[i], ')')

    ##########
    # Determine whether we have to redo the painfully slow BadDomList calculation
    # or if we already have an existing BDL that we can use.
    ##########
    from icecube.gen2_sim.utils import HasBadDomList
    RedoBadDomList = not HasBadDomList(gcd_file)
    print('Redo BadDomList:', RedoBadDomList)


    #
    # Process input photons
    #

    # No input photons in noise-only mode
    if not options.NOISEONLY :

        # Remove any late photons
        from icecube.gen2_sim.utils import RemoveLatePhotons
        tray.AddModule(
            RemoveLatePhotons,
            "RemovePhotons",
            InputPhotonSeries = "I3PhotonSeriesMap",
            TimeLimit = 1E5, # ns
        )

        # Convert MCPE to photons
        from icecube.gen2_sim.segments.clsim import MakePEFromPhotons
        #from MakePEFromPhotons import MakePEFromPhotons
        tray.Add(
            MakePEFromPhotons,
            Sensors=Sensors,
            GCDFile=gcd_file,
            # MCTreeName="I3MCTree_sliced", # Removed during sync with gen2-optical-sim
            PhotonSeriesName="I3PhotonSeriesMap",
            DOMOversizeFactor=1.,#TODO same as step2?
            EfficiencyScales=EfficiencyScales,
            RandomService=randomService,
            HoleIceParameterization = expandvars("$I3_SRC/ice-models/resources/models/" + options.HOLEICE),
            HoleIceParameterizationGen2 =  expandvars("$I3_SRC/ice-models/resources/models/" + options.HOLEICE), # Doesn't support hole ice currently
            UseDefaultRPEValue = True
        )


    #
    # Detector sim
    #

    # For noise-only MC, need an empty MCPE series and also noise weights
    if options.NOISEONLY :

        def empty_mcpes(frame):
            frame['I3MCTree'] = dataclasses.I3MCTree()
            for Sensor in Sensors:
                frame['I3MCPESeriesMap' + ModuleToString(Sensor)] = simclasses.I3MCPESeriesMap() #TODO This is a different name to the noise PE object for regular detector MC

        tray.AddModule(empty_mcpes, 'AddEmptyMCPEs', Streams=[icetray.I3Frame.DAQ])

        from icecube.gen2_sim.utils import NoiseWeight
        FrameLivetime = 100 * I3Units.millisecond
        tray.AddModule(NoiseWeight, "AddNoiseWeight", NEvents=options.NEVENTS, FrameLivetime=FrameLivetime)


    # Configure detector sim
    # Differs based on whether generating noise-only events, or adding noise to physics evnts
    DetectorSim_kw = dict(
        GCDFile=gcd_file,
        RandomService=randomService,
        RunID = options.RUNNUMBER,
        InputMCPESeriesMaps = MCPEs,
        Sensors = Sensors,
        mDOMGlass = options.GLASS,
        pregeneratedmDOM = options.pregeneratedmDOM,
        pregeneratedmDOMNoiseFile = options.pregeneratedmDOMNoiseFile,
        IncludeNoise=not options.NONOISE,
        TimeSmearing=not options.NOTIMESMEARING,
        PulseBinWidth=options.BINWIDTH,
        usemDOMwavedeformsimulation=options.usemDOMwavedeformsimulation,
    )

    if options.NOISEONLY :
        # Explicitly don't want this since all frames have 0 physics mcpes
        DetectorSim_kw["ZeroHitFilter"] = False
        # Set these specially in this case to get long noise events suitable for triggering
        DetectorSim_kw["VuvuzelaStartTime"] = 0.*I3Units.microsecond
        DetectorSim_kw["VuvuzelaEndTime"] = FrameLivetime
    else :
        DetectorSim_kw["KeepMCHits"] = True # Preserve the MCPE objects (noise and signal)
        DetectorSim_kw["ZeroHitFilter"] = True # removing events with 0 MCPEs
        DetectorSim_kw["FilterMode"] = False #TODO ? Was False by default but was changed to True?


    # Run detector sim
    from icecube.gen2_sim.segments.DetectorSim import DetectorSim
    tray.Add(DetectorSim, **DetectorSim_kw)


    # Run calibration
    from icecube.gen2_sim.segments.Calibration import Calibration
    tray.Add(Calibration, 'run_calib_wavedeform', RedoBadDomList=RedoBadDomList)


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

for run in range(0, 100):
    step_3_icetray(
        gridftp=options.GRIDFTP,
        gcd_file=options.GCDFILE,
        output_file= options.OUTFILE + "simple_track_posChanged_step3_"+str(run)+".i3.gz",  #options.OUTFILE,
        input_file=options.INFILE,
        tmp_dir=options.TMPDIR,
        run_number = run
        )
