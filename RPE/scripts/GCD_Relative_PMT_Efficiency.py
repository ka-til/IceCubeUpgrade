#!/usr/bin/env python3

from icecube import dataclasses, dataio, icetray
import pickle
import random
import numpy as np

'''
Creating a new GCD file with changed relative efficiencies

'''
def get_args():

    import argparse

    parser = argparse.ArgumentParser(description='Changing efficiencies in GCD')
    parser.add_argument('-i', '--input-file',  type=str, default='/mnt/c/Users/akank/IceCube_Software/i3/icetray/scripts/init_tests_021423/GCD/GeoCalibDetectorStatus_ICUpgrade.v58.mixed.V0.i3.bz2',
                        help='Write output to OUTFILE (.i3{.gz} format)')
    parser.add_argument('-o', '--output-file',  type=str, default='test_GCD.i3.gz',
                        help='Write output to OUTFILE (.i3{.gz} format)')
    parser.add_argument('-d', '--data-file', type=str, default='/mnt/c/Users/akank/IceCube_Software/i3/icetray/scripts/DOM_Eff/data/full_result_cache_combined.pckl',
                        help='mDOM data file to sample relative pmt efficiencies from')

    args = parser.parse_args()

    return args

args = get_args()

gcd_infile = dataio.I3File(args.input_file)
gcd_outfile = dataio.I3File(args.output_file , 'w')

'''
Getting information from .pickle file.
'''
with open(args.data_file, 'rb') as f:
    data = pickle.load(f)

pde_375 = data['pde_375nm']
pde_375 = pde_375.astype(float)

#removing NaN entries
pde_375 = pde_375[~np.isnan(pde_375)]

#calculate standard deviation
std_375 = np.std(pde_375)

#multiplying all vales by a constant will result in the standard deviation being multiplied by the constant.
pde_375 = pde_375*1/np.mean(pde_375) #want standard deviation that is 4.2% of the mean. 

mean_375 = np.mean(pde_375)

sample = pde_375+(1.0 - mean_375) #shifting the mean to 1.0

'''
Updating the calibration frame
'''

while gcd_infile.more():
    frame = gcd_infile.pop_frame()
    if "I3Geometry" in frame:
        geometry = frame["I3Geometry"]

    if "I3Calibration" in frame:
        calibration = frame["I3Calibration"]
        calibrationData = calibration.dom_cal
        domcal = dataclasses.Map_OMKey_I3DOMCalibration()
        for omkey in geometry.omgeo.keys():
            if omkey in calibrationData.keys():
                domcal[omkey] = calibrationData[omkey]

                """
                Changing RDE
                """

                if calibrationData[omkey].relative_dom_eff == 1.35:
                    domcal[omkey].relative_dom_eff = calibrationData[omkey].relative_dom_eff #not changing HQE DOMs for now.
                else:
                    domcal[omkey].relative_dom_eff = random.choice(sample)

        frame["I3Calibration"].dom_cal = domcal

    if "I3DetectorStatus" in frame:
        detectorStatus = frame["I3DetectorStatus"]

    gcd_outfile.push(frame)

gcd_outfile.close()
