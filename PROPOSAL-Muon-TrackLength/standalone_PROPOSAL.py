import os, argparse
import numpy as np
from I3Tray import I3Units, I3Tray, load
from icecube import icetray, dataclasses, dataio, phys_services, genie_reader
from icecube.sim_services.propagation import get_propagators
from pprint import pformat
from icecube.dataclasses import I3Particle, I3Position, I3Time
from icecube.icetray import i3logging
from step_1_toy import create_primary, basic_mc_boilerplate, STREAMS

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input-file",type=str, default='/data/icecube/akatil/files_from_cobalt/oscNext_bare_lepton_toy_step2_pass2_purged_clsim.139003.000000.i3.zst')
parser.add_argument("-o", "--output-file",type=str, required=True)
parser.add_argument("-g", "--gcd-file",type=str, default='/cvmfs/icecube.opensciencegrid.org/data/GCD/GeoCalibDetectorStatus_AVG_55697-57531_PASS2_SPE_withScaledNoise.i3.gz')
parser.add_argument("-f", "--file-num",type=int, required=True)
parser.add_argument("-d", "--dataset-num",type=int, required=True)
parser.add_argument("-c", "--config-file", type=str,  required=True)
parser.add_argument("-mctree", "--mctree-name", type=str, required=True)
parser.add_argument("--seed",type=int,required=False,default=None)
parser.add_argument("--streamnum",type=int,required=False,default=None)
args = parser.parse_args()

tray = I3Tray()

'''
random_service = basic_mc_boilerplate(
        tray=tray,
        dataset_num=args.dataset_num,
        file_num=args.file_num,
        seed=args.seed,
        streamnum=args.streamnum,
    )
'''

random_service = phys_services.I3SPRNGRandomService(
        seed=args.dataset_num,
        nstreams=10000,
        streamnum=args.file_num,
    )

tray.context['I3RandomService'] = random_service
'''
random_service = phys_services.I3SPRNGRandomService(
      seed = 10000,
      nstreams = 50000,
      streamnum = 1)
'''
tray.AddModule('I3Reader', 'reader', FilenameList=[args.gcd_file, args.input_file])

from icecube import PROPOSAL, sim_services
propagators = sim_services.I3ParticleTypePropagatorServiceMap()
Propagator = PROPOSAL.I3PropagatorServicePROPOSAL(config_file=args.config_file)
propagators[I3Particle.ParticleType.MuMinus] = Propagator
i3logging.log_info("Using new PROPOSAL version (e.g. from combo/trunk)!")
tray.AddModule('I3PropagatorModule', 'muon_propagator',
                PropagatorServices=propagators,
                RandomService=random_service,
                InputMCTreeName="I3MCTree",
                OutputMCTreeName=args.mctree_name)

# Report propagators
print("Propagators :")
for particle, propagator in propagators.items() :
    print("  %s : %s" % (particle, propagator))

def print_progress(frame):
    print("Writing frame to output file...")
    return True

tray.AddModule(print_progress, 'print_progress')
tray.AddModule('I3Writer', 'writer', Streams=STREAMS, filename=args.output_file)
tray.Execute()
tray.Finish()
