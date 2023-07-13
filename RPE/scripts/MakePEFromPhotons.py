import os
import sys,getopt,string
from os.path import expandvars
import subprocess
import threading
import time
import copy
import math
import numpy as np
from functools import reduce

from os.path import expandvars, exists, isdir, isfile
from icecube import icetray, dataclasses, clsim, photonics_service, simclasses
from icecube.mDOM_WOM_simulation.traysegments import mdom, degg
from icecube.mDOM_WOM_simulation.traysegments.mDOMMakeHitsFromPhotons import mDOMMakeHitsFromPhotons
from icecube.mDOM_WOM_simulation.traysegments.DEggMakeHitsFromPhotons import DEggMakeHitsFromPhotons
from icecube.simprod import ipmodule
from icecube.icetray import I3Units, logging
logging.set_level_for_unit('I3PhotonToMCPEConverterForDOMs',
                           logging.I3LogLevel.LOG_TRACE)#logging.I3LogLevel.LOG_TRACE)
from icecube.dataclasses import I3OMGeo
from icecube.gen2_sim.utils import iceprod_wrapper

def sensor_area(sensor):
    """
    Return the sensor's effective area averaged over all angles and wavelengths
    between 300 and 600 nm (Cherenkov-weighted)
    """
    if sensor == I3OMGeo.OMType.PDOM:
        return 29.2*I3Units.cm2
    elif sensor == I3OMGeo.OMType.DEgg:
        return 43.3*I3Units.cm2
    elif sensor == I3OMGeo.OMType.mDOM:
        return 65.4*I3Units.cm2
    else:
        raise ValueError("Unsupported sensor '%s'" % sensor)

@icetray.traysegment
def CleanupSlicedMCTree(tray, name, MCPESeriesName='I3MCPESeriesMap', PhotonSeriesMapName=None, KeepSlicedMCTree=False, InputMCTree='I3MCTree'):
    sliceRemoverAdditionalParams = dict()
    if PhotonSeriesMapName is not None:
        sliceRemoverAdditionalParams["InputPhotonSeriesMapName"] = PhotonSeriesMapName
        sliceRemoverAdditionalParams["OutputPhotonSeriesMapName"] = PhotonSeriesMapName
    # re-assign the output hits from the sliced tree to the original tree
    tray.AddModule("I3MuonSliceRemoverAndPulseRelabeler",
        InputMCTreeName = InputMCTree+"_sliced",
        OldMCTreeName = InputMCTree,
        InputMCPESeriesMapName = MCPESeriesName,
        OutputMCPESeriesMapName = MCPESeriesName,
        **sliceRemoverAdditionalParams
        )
    if not KeepSlicedMCTree:
        tray.AddModule("Delete", name+"_cleanup_clsim_sliced_MCTree",
            Keys = [InputMCTree+"_sliced"])

@icetray.traysegment
def MakePEFromPhotons(
    tray, name, GCDFile,
    Sensors=[I3OMGeo.OMType.IceCube,
             I3OMGeo.OMType.PDOM,
             I3OMGeo.OMType.mDOM,
             I3OMGeo.OMType.DEgg,],
    PhotonSeriesName="I3PhotonSeriesMap",
    DOMOversizeFactor=1.,
    EfficiencyScales=[1.0, 1.0, 2.2, 1.5],
    RandomService=None,
    IceModelLocation='$I3_SRC/ice-models/resources/models/ICEMODEL/',
    IceModel="spice_bfr-v2",
    HoleIceParameterization = expandvars("$I3_SRC/ice-models/resources/models/ANGSENS/angsens/as.nominal"),
    HoleIceParameterizationGen2 = "",
    KeepPhotonSeries = True
    ):
    """
    :param EfficiencyScale: scale QE so that the average photon effective area
    of the sensor is equivalent to this multiple of the pDOM area
    """
    from icecube import simclasses
    from icecube.clsim.traysegments import I3CLSimMakeHitsFromPhotons
    from icecube.gen2_sim.utils import split_photons, ModuleToString

    tray.Add("I3GeometryDecomposer", If=lambda frame: "I3OMGeoMap" not in frame)

    # Break the photons up now to make life easier
    tray.Add(split_photons,
             Input = PhotonSeriesName,
             Sensors = Sensors,
             Streams = [icetray.I3Frame.DAQ],
             KeepPhotonSeries = KeepPhotonSeries)

    photonList = []

    randomService = tray.context['I3RandomService'] if RandomService is None else RandomService

    if randomService is None :
        assert tray.context['I3RandomService'] is not None, "Both `randomService` argument and random sercice in IceTray `context` are `None`"
        randomService = tray.context['I3RandomService']

    for i, Sensor in enumerate(Sensors):
        currentPhotonSeriesName = PhotonSeriesName + ModuleToString(Sensor)
        currentMCPESeriesName = currentPhotonSeriesName.replace("Photon", "MCPE")
        photonList.append(currentPhotonSeriesName)

        EfficiencyScale, rqe = EfficiencyScales[i], 1.0
        if not Sensor == I3OMGeo.OMType.IceCube:
            rqe = EfficiencyScale*sensor_area(I3OMGeo.OMType.PDOM)/sensor_area(Sensor)

        # TODO: add a PE converter based on the value of `Sensor`
        # be sure to scale mDOM QE *up* by (mDOM radius/DOM radius)**2
        # to account for the fact that photons were captured on a smaller area
        assert Sensor in [I3OMGeo.OMType.IceCube, I3OMGeo.OMType.PDOM, I3OMGeo.OMType.mDOM, I3OMGeo.OMType.DEgg], "Unknown sensor! {}".format(sensor)
        icetray.logging.log_info("Will calculate PEs for {} with photocathode area equivalent to {}x pDOM ({}x {})".format(Sensor, EfficiencyScale, rqe, Sensor))

        HoleIceParameterization= expandvars(HoleIceParameterization)
        HoleIceParameterizationGen2 = expandvars(HoleIceParameterizationGen2)
        if HoleIceParameterizationGen2 == "":
            print("No separate hole ice for Gen2, using IceCube one. Warning applicable to pDOM/DEgg Gen2 only")
            HoleIceParameterizationGen2 = HoleIceParameterization

        '''
        if Sensor == I3OMGeo.OMType.PDOM:
            tray.Add(I3CLSimMakeHitsFromPhotons, name + "_PEconverterForPDOMs",
                     PhotonSeriesName        = currentPhotonSeriesName,
                     MCPESeriesName          = currentMCPESeriesName,
                     RandomService           = randomService,
                     DOMOversizeFactor       = DOMOversizeFactor,
                     UnshadowedFraction      = rqe,
                     HoleIceParameterization = HoleIceParameterizationGen2,
                     GCDFile                 = GCDFile,
                     IceModelLocation        = expandvars(
                         os.path.join(IceModelLocation, IceModel)),
                     IgnoreSubdetectors      = ['IceTop', 'HEX']
            )
            tray.Add(CleanupSlicedMCTree,
                     MCPESeriesName = currentMCPESeriesName,
                     KeepSlicedMCTree=True, If=lambda frame:frame.Has('I3MCTree_sliced'))

        elif Sensor == I3OMGeo.OMType.mDOM:
            # in case of Gen2 mDOMs I3Calibration needs to be reduced, otherwise it's
            # too big to hold in memory
            tray.Add(trim_calibration, Streams=[icetray.I3Frame.Calibration])
            tray.Add(mDOMMakeHitsFromPhotons, name + "_PEconverterForMDOMs",
                     InputPhotonSeriesMapName = currentPhotonSeriesName,
                     DOMOversizeFactor        = DOMOversizeFactor,
                     EfficiencyScale          = rqe,
                     OutputMCHitSeriesMapName = currentMCPESeriesName,
                     RandomService            = randomService)
            tray.Add(CleanupSlicedMCTree,
                     MCPESeriesName = currentMCPESeriesName,
                     KeepSlicedMCTree=True, If=lambda frame:frame.Has('I3MCTree_sliced'))

        '''

        if Sensor == I3OMGeo.OMType.DEgg:
            tray.Add(DEggMakeHitsFromPhotons, name + "_PEconverterForDEggs",
                     PhotonSeriesName        = currentPhotonSeriesName,
                     MCPESeriesName          = currentMCPESeriesName,
                     RandomService           = randomService,
                     DOMOversizeFactor       = DOMOversizeFactor,
                     UnshadowedFraction      = rqe,
                     HoleIceParameterization = HoleIceParameterizationGen2
            )
            tray.Add(CleanupSlicedMCTree,
                     MCPESeriesName = currentMCPESeriesName,
                     KeepSlicedMCTree=True, If=lambda frame:frame.Has('I3MCTree_sliced'))

        '''
        elif Sensor == I3OMGeo.OMType.IceCube:
            tray.Add(I3CLSimMakeHitsFromPhotons, name + "_PEconverterForDOMS",
                     PhotonSeriesName        = currentPhotonSeriesName,
                     MCPESeriesName          = currentMCPESeriesName,
                     RandomService           = randomService,
                     DOMOversizeFactor       = DOMOversizeFactor,
                     UnshadowedFraction      = 0.99,
                     HoleIceParameterization = HoleIceParameterization,
                     GCDFile                 = GCDFile,
                     IceModelLocation        = expandvars(
                         os.path.join(IceModelLocation, IceModel)),
                     IgnoreSubdetectors      = ['IceTop', 'HEX']
            )
            tray.Add(CleanupSlicedMCTree,
                     MCPESeriesName = currentMCPESeriesName,
                     KeepSlicedMCTree=True, If=lambda frame:frame.Has('I3MCTree_sliced'))
            '''

            # TODO: Need to switch to the CLSim ExtensionCylinder branch or merge it back into
            # trunk in order to handle WOMs

    # Clean up the photons before we move on
    tray.Add("Delete", Keys = photonList)
    tray.Add("Delete", Keys = ['I3MCTree_sliced',], If=lambda frame:frame.Has('I3MCTree_sliced'))
