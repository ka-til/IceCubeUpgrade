#!/usr/bin/env python3
"""
Injecting a muon in the detector
"""

import os,sys
from os.path import expandvars
import argparse

import I3Tray
from I3Tray import I3Units, I3Tray
from icecube import icetray, dataio, phys_services, dataclasses

from math import pi, sqrt, sin, cos
import random

def Generator(frame, muonEnergy=10*I3Units.TeV):
    print('Generating a new frame')
    p = dataclasses.I3Particle()
    p.energy =  muonEnergy*I3Units.GeV #50*I3Units.TeV #random.uniform(10*I3Units.TeV, 1*I3Units.PeV)
    p.pos = dataclasses.I3Position(0,0,0)
    #p.shape = dataclasses.I3Particle.ParticleShape.Track

    # sample on a cylinder
    #theta = random.uniform(0., 2*pi)
    #r = sqrt(random.uniform(0, 300*I3Units.m * 300*I3Units.m))

    #x = r * sin(theta)
    #y = r * cos(theta)
    #z = random.uniform(-300*I3Units.m, 300*I3Units.m)

    zenith = pi #random.uniform(0., pi)
    azimuth = 0 #random.uniform(0., 2*pi)
    p.dir = dataclasses.I3Direction(zenith, azimuth)
    #p.pos = dataclasses.I3Position(x,y,z)
    #p.length = 900 * I3Units.m
    p.type = dataclasses.I3Particle.ParticleType.MuMinus
    p.location_type = dataclasses.I3Particle.LocationType.InIce
    p.time = 0. * I3Units.ns

    tree = dataclasses.I3MCTree()
    tree.add_primary(p)

    frame["I3MCTree"] = tree

def get_args():
    parser = argparse.ArgumentParser(description='Simple Track Simulation')
    parser.add_argument('-o', '--output-file',  type=str, default='simple_track.i3.gz',
                        help='Write output to OUTFILE (.i3{.gz} format)')
    parser.add_argument('-n', '--n-events',     type=int, default = 1,
                        help='Number of events to generate')
    parser.add_argument('-e', '--energy',   type=float, default=10*I3Units.TeV,
                        help='What is the energy of muon in GeV')

    args = parser.parse_args()

    return args

def run_tray(args):

    print(args.energy, args.output_file)

    print("running tray")

    '''
    Random serice has fixed parameters for now. All frames will be the same
    '''
    randomService = phys_services.I3SPRNGRandomService(
          seed = 10000,
          nstreams = 50000,
          streamnum = 1)

    tray = I3Tray()

    tray.Add("I3InfiniteSource", Stream = icetray.I3Frame.DAQ)

    tray.Add(Generator,
            muonEnergy=args.energy,
            Streams=[icetray.I3Frame.DAQ])

    print('I am useless and did not work')

    """
    Propagating muon using PROPOSAL
    """

    from icecube import PROPOSAL, sim_services

    print("Running Proposal")

    propagators = sim_services.I3ParticleTypePropagatorServiceMap()

    print("Starting to run propagtor. Is the config file the issue?")

    Propagator = PROPOSAL.I3PropagatorServicePROPOSAL(
              config_file='$I3_BUILD/genie-reader/resources/scripts/PROPOSAL-config/config-genie-reader.json') #configfile)

    print("Ran propagator config file is not the issue")

    propagators[dataclasses.I3Particle.ParticleType.MuMinus] = Propagator

    tray.AddModule('I3PropagatorModule', 'muminus_propagator',
                PropagatorServices=propagators,
                RandomService=randomService,
                InputMCTreeName="I3MCTree",
                OutputMCTreeName="I3MCTree")

    tray.Add("I3Writer", filename = args.output_file)

    tray.AddModule("TrashCan", "the can")

    tray.Execute(args.n_events)
    print('Finish Executing')
    tray.Finish()

def main():
    args = get_args()
    run_tray(args)

if __name__=='__main__':
    main()
