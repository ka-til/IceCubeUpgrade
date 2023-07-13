#!/usr/bin/env python3

from icecube import dataclasses, dataio, icetray

'''
Creating a new GCD file with changed relative efficiencies

'''
def get_args():

    import argparse

    parser = argparse.ArgumentParser(description='Changing efficiencies in GCD')
    parser.add_argument('-i', '--input-file',  type=str, default='/mnt/c/Users/akank/IceCube_Software/i3/icetray/scripts/init_tests_021423/GCD//GeoCalibDetectorStatus_ICUpgrade.v58.mixed.V0.i3.bz2',
                        help='Write output to OUTFILE (.i3{.gz} format)')
    parser.add_argument('-o', '--output-file',  type=str, default='simple_track.i3.gz',
                        help='Write output to OUTFILE (.i3{.gz} format)')
    '''
    parser.add_argument('-s1', '--string-1',     type=int, default = 86,
                        help='string where efficiency is changed')
    parser.add_argument('-s2', '--string-2',     type=int, default = 87,
                        help='string where efficiency is changed')
    '''

    parser.add_argument('-rde', '--relative-dom-eff',   type=float, default=3.0,
                        help='What is the energy of muon in GeV')
    parser.add_argument('-s', '--string-list', nargs='+', help='list of strings to change efficiencies of')
    parser.add_argument('-p', '--pmt-list', nargs='+', help='list of pmts to change efficiencies of')

    args = parser.parse_args()

    return args

args = get_args()

gcd_infile = dataio.I3File(args.input_file)
gcd_outfile = dataio.I3File(args.output_file , 'w')

#strings = [args.string_1, args.string_2]

if args.string_list:
    strings = [int(item) for item in args.string_list]
    print("Strings that are changed:", strings)

if args.pmt_list:
    pmts = [int(item) for item in args.pmt_list]
    print("PMTs that are changed:", pmts)

print("Relative dom efficiency is:", args.relative_dom_eff)

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
                #print(domcal[omkey])
                """
                Changing RDE of entire strings for now.
                """
                if omkey[0] in strings:
                    if omkey[2] in pmts:
                    #print(domcal[omkey].relative_dom_eff)
                        domcal[omkey].relative_dom_eff = args.relative_dom_eff
                #break
            else:
                oKey = geometry.omgeo.get(omkey)
                #print(oKey.omtype)

        frame["I3Calibration"].dom_cal = domcal

    if "I3DetectorStatus" in frame:
        detectorStatus = frame["I3DetectorStatus"]

    gcd_outfile.push(frame)

gcd_outfile.close()
