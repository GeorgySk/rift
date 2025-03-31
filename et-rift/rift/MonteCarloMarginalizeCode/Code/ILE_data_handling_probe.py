#! /usr/bin/env python
#
# ILE_data_handling_probe.py
#
# Like ILE, but only providing the Qlm and inverse spectrum filters
#

from __future__ import print_function

import sys
import functools
from optparse import OptionParser, OptionGroup

import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot as plt

import numpy
import numpy as np
try:
  import cupy
  xpy_default=cupy
  identity_convert = cupy.asnumpy
except:
  print(' no cupy')
#  import numpy as cupy  # will automatically replace cupy calls with numpy!
  xpy_default=numpy  # just in case, to make replacement clear and to enable override
  identity_convert = lambda x: x  # trivial return itself


import lal
from glue.ligolw import utils, lsctables, table, ligolw
from glue.ligolw.utils import process
import glue.lal

import lalsimutils
import factored_likelihood
import RIFT.integrators.mcsampler as mcsampler
import xmlutils

#from lalinference.bayestar import fits as bfits

__author__ = "Evan Ochsner <evano@gravity.phys.uwm.edu>, Chris Pankow <pankow@gravity.phys.uwm.edu>, R. O'Shaughnessy"

#
# Pinnable parameters -- for command line processing
#
LIKELIHOOD_PINNABLE_PARAMS = ["right_ascension", "declination", "psi", "distance", "phi_orb", "t_ref", "inclination"]

def get_pinned_params(opts):
    """
    Retrieve a dictionary of user pinned parameters and their pin values.
    """
    return dict([(p,v) for p, v in opts.__dict__.items() if p in LIKELIHOOD_PINNABLE_PARAMS and v is not None]) 

def get_unpinned_params(opts, params):
    """
    Retrieve a set of unpinned parameters.
    """
    return params - set([p for p, v in opts.__dict__.items() if p in LIKELIHOOD_PINNABLE_PARAMS and v is not None])

#
# Option parsing
#

optp = OptionParser()
optp.add_option("-c", "--cache-file", default=None, help="LIGO cache file containing all data needed.")
optp.add_option("-C", "--channel-name", action="append", help="instrument=channel-name, e.g. H1=FAKE-STRAIN. Can be given multiple times for different instruments.")
optp.add_option("-p", "--psd-file", action="append", help="instrument=psd-file, e.g. H1=H1_PSD.xml.gz. Can be given multiple times for different instruments.")
optp.add_option("-k", "--skymap-file", help="Use skymap stored in given FITS file.")
optp.add_option("-x", "--coinc-xml", help="gstlal_inspiral XML file containing coincidence information.")
optp.add_option("-I", "--sim-xml", help="XML file containing mass grid to be evaluated")
optp.add_option("-E", "--event", default=0,type=int, help="Event number used for this run")
optp.add_option("--n-events-to-analyze", default=1,type=int, help="Number of events to analyze from this XML")
optp.add_option("--soft-fail-event-range",action='store_true',help='Soft failure (exit 0) if event ID is out of range. This happens in pipelines, if we have pre-built a DAG attempting to analyze more points than we really have')
optp.add_option("-f", "--reference-freq", type=float, default=100.0, help="Waveform reference frequency. Required, default is 100 Hz.")
optp.add_option("--fmin-template", dest='fmin_template', type=float, default=40, help="Waveform starting frequency.  Default is 40 Hz. Also equal to starting frequency for integration") 
optp.add_option("--fmin-ifo", action='append' , help="Minimum frequency for each IFO. Implemented by setting the PSD=0 below this cutoff. Use with care.") 
#optp.add_option("--nr-params",default=None, help="List of specific NR parameters and groups (and masses?) to use for the grid.")
#optp.add_option("--nr-index",type=int,default=-1,help="Index of specific NR simulation to use [integer]. Mass used: mtot= m1+m2")
optp.add_option('--nr-group', default=None,help="If using a *ssingle specific simulation* specified on the command line, provide it here")
optp.add_option('--nr-param', default=None,help="If using a *ssingle specific simulation* specified on the command line, provide it here")
optp.add_option("--nr-lookup",action='store_true', help=" Look up parameters from an NR catalog, instead of using the approximant specified")
optp.add_option("--nr-lookup-group",action='append', help="Restriction on 'group' for NR lookup")
optp.add_option("--nr-hybrid-use",action='store_true',help="Enable use of NR (or ROM!) hybrid, using --approx as the default approximant and with a frequency fmin")
optp.add_option("--nr-hybrid-method",default="taper_add",help="Hybridization method for NR (or ROM!).  Passed through to LALHybrid. pseudo_aligned_from22 will provide ad-hoc higher modes, if the early-time hybridization model only includes the 22 mode")
optp.add_option("--rom-group",default=None)
optp.add_option("--rom-param",default=None)
optp.add_option("--rom-use-basis",default=False,action='store_true',help="Use the ROM basis for inner products.")
optp.add_option("--rom-limit-basis-size-to",default=None,type=int)
optp.add_option("--rom-integrate-intrinsic",default=False,action='store_true',help='Integrate over intrinsic variables. REQUIRES rom_use_basis at present. ONLY integrates in mass ratio as present')
optp.add_option("--nr-perturbative-extraction",default=False,action='store_true')
optp.add_option("--nr-use-provided-strain",default=False,action='store_true')
optp.add_option("--no-memory",default=False,action='store_true', help="At present, turns off m=0 modes. Use with EXTREME caution only if requested by model developer")
optp.add_option("--restricted-mode-list-file",default=None,help="A list of ALL modes to use in likelihood. Incredibly dangerous. Only use when comparing with models which provide restricted mode sets, or otherwise to isolate the effect of subsets of modes on the whole")
optp.add_option("--use-external-EOB",default=False,action='store_true')
optp.add_option("--maximize-only",default=False, action='store_true',help="After integrating, attempts to find the single best fitting point")
optp.add_option("--dump-lnL-time-series",default=False, action='store_true',help="(requires --sim-xml) Dump lnL(t) at the injected parameters")
optp.add_option("-a", "--approximant", default="TaylorT4", help="Waveform family to use for templates. Any approximant implemented in LALSimulation is valid.")
optp.add_option("-A", "--amp-order", type=int, default=0, help="Include amplitude corrections in template waveforms up to this e.g. (e.g. 5 <==> 2.5PN), default is Newtonian order.")
optp.add_option("--l-max", type=int, default=2, help="Include all (l,m) modes with l less than or equal to this value.")
optp.add_option("-s", "--data-start-time", type=float, default=None, help="GPS start time of data segment. If given, must also give --data-end-time. If not given, sane start and end time will automatically be chosen.")
optp.add_option("-e", "--data-end-time", type=float, default=None, help="GPS end time of data segment. If given, must also give --data-start-time. If not given, sane start and end time will automatically be chosen.")
optp.add_option("--data-integration-window-half",default=50*1e-3,type=float,help="Only change this window size if you are an expert. The window for time integration is -/+ this quantity around the event time")
optp.add_option("-F", "--fmax", type=float, help="Upper frequency of signal integration. Default is use PSD's maximum frequency.")
optp.add_option("--srate",default=16384,type=int,help="Sampling rate. Change ONLY IF YOU ARE ABSOLUTELY SURE YOU KNOW WHAT YOU ARE DOING.")
optp.add_option("-t", "--event-time", type=float, help="GPS time of the event --- probably the end time. Required if --coinc-xml not given.")
optp.add_option("-i", "--inv-spec-trunc-time", type=float, default=8., help="Timescale of inverse spectrum truncation in seconds (Default is 8 - give 0 for no truncation)")
optp.add_option("-w", "--window-shape", type=float, default=0, help="Shape of Tukey window to apply to data (default is no windowing)")
optp.add_option("-m", "--time-marginalization", action="store_true", help="Perform marginalization over time via direct numerical integration. Default is false.")
optp.add_option("--vectorized", action="store_true", help="Perform manipulations of lm and timeseries using numpy arrays, not LAL data structures.  (Combine with --gpu to enable GPU use, where available)")
optp.add_option("--gpu", action="store_true", help="Perform manipulations of lm and timeseries using numpy arrays, CONVERTING TO GPU when available. You MUST use this option with --vectorized (otherwise it is a no-op). You MUST have a suitable version of cupy installed, your cuda operational, etc")
optp.add_option("--force-xpy", action="store_true", help="Use the xpy code path.  Use with --vectorized --gpu to use the fallback CPU-based code path. Useful for debugging.")
optp.add_option("-o", "--output-file", help="Save result to this file.")
optp.add_option("-O", "--output-format", default='xml', help="[xml|hdf5]")
optp.add_option("--verbose",action='store_true')
#
# Add the integration options
#
integration_params = OptionGroup(optp, "Integration Parameters", "Control the integration with these options.")
# Default is actually None, but that tells the integrator to go forever or until n_eff is hit.
integration_params.add_option("--interpolate-time", default=False,help="If using time marginalization, compute using a continuously-interpolated array. (Default=false)")
optp.add_option_group(integration_params)

#
# Add the intrinsic parameters
#
intrinsic_params = OptionGroup(optp, "Intrinsic Parameters", "Intrinsic parameters (e.g component mass) to use.")
#intrinsic_params.add_option("--pin-distance-to-sim",action='store_true', help="Pin *distance* value to sim entry. Used to enable source frame reconstruction with NR.")
intrinsic_params.add_option("--mass1", type=float, help="Value of first component mass, in solar masses. Required if not providing coinc tables.")
intrinsic_params.add_option("--mass2", type=float, help="Value of second component mass, in solar masses. Required if not providing coinc tables.")
intrinsic_params.add_option("--eff-lambda", type=float, help="Value of effective tidal parameter. Optional, ignored if not given.")
intrinsic_params.add_option("--deff-lambda", type=float, help="Value of second effective tidal parameter. Optional, ignored if not given")
optp.add_option_group(intrinsic_params)


#
# Add options to integrate over intrinsic parameters.  Same conventions as util_ManualOverlapGrid.py.  
# Parameters have special names, and we adopt priors that use those names.
# NOTE: Only 'q' implemented
#
intrinsic_int_params = OptionGroup(optp, "Intrinsic integrated parameters", "Intrinsic parameters to integrate over. ONLY currently used with ROM version")
intrinsic_int_params.add_option("--parameter",action='append')
intrinsic_int_params.add_option("--parameter-range",action='append',type=str)
intrinsic_int_params.add_option("--adapt-intrinsic",action='store_true')
optp.add_option_group(intrinsic_int_params)


#
# Add the pinnable parameters
#
pinnable = OptionGroup(optp, "Pinnable Parameters", "Specifying these command line options will pin the value of that parameter to the specified value with a probability of unity.")
for pin_param in LIKELIHOOD_PINNABLE_PARAMS:
    option = "--" + pin_param.replace("_", "-")
    pinnable.add_option(option, type=float, help="Pin the value of %s." % pin_param)
optp.add_option_group(pinnable)

opts, args = optp.parse_args()

if opts.gpu and xpy_default is numpy:
    print(" Override --gpu  (not available);  use --force-xpy to require the identical code path is used (with xpy =[np|cupy]")
    opts.gpu=False
    if opts.force_xpy:
        opts.gpu=True



deltaT = None
fSample= opts.srate # change sampling rate
if not(fSample is None):
  deltaT =1./fSample


# Load in restricted mode set, if available
restricted_mode_list=None
if not(opts.restricted_mode_list_file is None):
    modes =numpy.loadtxt(opts.restricted_mode_list_file,dtype=int) # columns are l m.  Must contain all. Only integers obviously
    restricted_mode_list = [ (l,m) for l,m in modes]
    print(" RESTRICTED MODE LIST target :", restricted_mode_list)

intrinsic_param_names = opts.parameter
valid_intrinsic_param_names = ['q']
if intrinsic_param_names:
 for param in intrinsic_param_names:
    
    # Check if in the valid list
    if not(param in valid_intrinsic_param_names):
            print(' Invalid param ', param, ' not in ', valid_intrinsic_param_names)
            sys.exit(0)
    param_ranges = []
    if len(intrinsic_param_names) == len(opts.parameter_range):
        param_ranges = numpy.array(map(eval, opts.parameter_range))
        # Rescale mass-dependent ranges to SI units
        for p in ['mc', 'm1', 'm2', 'mtot']:
          if p in intrinsic_param_names:
            indx = intrinsic_param_names.index(p)
            param_ranges[indx]= numpy.array(param_ranges[indx])* lal.MSUN_SI



# Check both or neither of --data-start/end-time given
if opts.data_start_time is None and opts.data_end_time is not None:
    raise ValueError("You must provide both or neither of --data-start-time and --data-end-time.")
if opts.data_end_time is None and opts.data_start_time is not None:
    raise ValueError("You must provide both or neither of --data-start-time and --data-end-time.")

#
# Import NR grid
#
NR_template_group=None
NR_template_param=None
if opts.nr_group and opts.nr_param:
    import NRWaveformCatalogManager3 as nrwf
    NR_template_group = opts.nr_group
    if nrwf.internal_ParametersAreExpressions[NR_template_group]:
        NR_template_param = eval(opts.nr_param)
    else:
        NR_template_param = opts.nr_param


#
# Hardcoded variables
#
template_min_freq = opts.fmin_template # minimum frequency of template
#t_ref_wind = 50e-3 # Interpolate in a window +/- this width about event time. 
t_ref_wind = opts.data_integration_window_half
T_safety = 2. # Safety buffer (in sec) for wraparound corruption

#
# Inverse spectrum truncation control
#
T_spec = opts.inv_spec_trunc_time
if T_spec == 0.: # Do not do inverse spectrum truncation
    inv_spec_trunc_Q = False
    T_safety += 8. # Add a bit more safety buffer in this case
else:
    inv_spec_trunc_Q = True



if opts.event_time is not None:
    event_time = glue.lal.LIGOTimeGPS(opts.event_time)
    print("Event time from command line: %s" % str(event_time))
else:
    print(" Error! ")
    sys.exit(0)

#
# Template descriptors
#

fiducial_epoch = lal.LIGOTimeGPS()
fiducial_epoch = event_time.seconds + 1e-9*event_time.nanoseconds   # no more direct access to gpsSeconds

# Struct to hold template parameters
P_list = None
if opts.sim_xml:
    print("====Loading injection XML:", opts.sim_xml, opts.event, " =======")
    P_list = lalsimutils.xml_to_ChooseWaveformParams_array(str(opts.sim_xml))
    if  len(P_list) < opts.event+opts.n_events_to_analyze:
        print(" Event list of range; soft exit")
        sys.exit(0)
    P_list = P_list[opts.event:(opts.event+opts.n_events_to_analyze)]
    for P in P_list:
        P.radec =False  # do NOT propagate the epoch later
        P.fref = opts.reference_freq
        P.fmin = template_min_freq
        P.tref = fiducial_epoch  # the XML table
        m1 = P.m1/lal.MSUN_SI
        m2 =P.m2/lal.MSUN_SI
        lambda1, lambda2 = P.lambda1,P.lambda2
        P.dist = factored_likelihood.distMpcRef * 1.e6 * lal.PC_SI   # use *nonstandard* distance
        P.phi=0.0
        P.psi=0.0
        P.incl = 0.0       # only works for aligned spins. Be careful.
        P.fref = opts.reference_freq
        if opts.approximant != "TaylorT4": # not default setting
            P.approx = lalsimutils.lalsim.GetApproximantFromString(opts.approximant)  # allow user to override the approx setting. Important for NR followup, where no approx set in sim_xml!

    P = P_list[0]  # Load in the physical parameters of the injection.  


# User requested bounds for data segment
if not (opts.data_start_time == None) and  not (opts.data_end_time == None):
    start_time =  opts.data_start_time
    end_time =  opts.data_end_time
    print("Fetching data segment with start=", start_time)
    print("                             end=", end_time)

# Automatically choose data segment bounds so region of interest isn't corrupted
# FIXME: Use estimate, instead of painful full waveform generation call here.
else:
    approxTmp = P.approx
    T_tmplt = lalsimutils.estimateWaveformDuration(P) + 4  # Much more robust than the previous (slow, prone-to-crash approach)
#     if (m1+m2)<30:
#         P.approx = lalsimutils.lalsim.TaylorT4  # should not impact length much.  IMPORTANT because EOB calls will fail at the default sampling rate
#         htmplt = lalsimutils.hoft(P)   # Horribly wasteful waveform gneeration solely to estimate duration.  Will also crash if spins are used.
#         P.approx = approxTmp
#         T_tmplt = - float(htmplt.epoch)    # ASSUMES time returned by hlm is a RELATIVE time that does not add tref. P.radec=False !
#         print fiducial_epoch, event_time, htmplt.epoch
#     else:
#         print " Using estimate for waveform length in a high mass regime: beware!"
#         T_tmplt = lalsimutils.estimateWaveformDuration(P) + 4
    T_seg = T_tmplt + T_spec + T_safety # Amount before and after event time
#    if opts.use_external_EOB:
#        T_seg *=2   # extra safety factor
    start_time = float(event_time) - T_seg
    end_time = float(event_time) + T_seg
    print("Fetching data segment with start=", start_time)
    print("                             end=", end_time)
    print("\t\tEvent time is: ", float(event_time))
    print("\t\tT_seg is: ", T_seg)

#
# Load in data and PSDs
#
data_dict, psd_dict = {}, {}

for inst, chan in map(lambda c: c.split("="), opts.channel_name):
    print("Reading channel %s from cache %s" % (inst+":"+chan, opts.cache_file))
    data_dict[inst] = lalsimutils.frame_data_to_non_herm_hoff(opts.cache_file,
            inst+":"+chan, start=start_time, stop=end_time,
            window_shape=opts.window_shape,deltaT=deltaT)
    print("Frequency binning: %f, length %d" % (data_dict[inst].deltaF,
            data_dict[inst].data.length))

flow_ifo_dict = {}
if opts.fmin_ifo:
 for inst, freq_str in map(lambda c: c.split("="), opts.fmin_ifo):
    freq_low_here = float(freq_str)
    print("Reading low frequency cutoff for instrument %s from %s" % (inst, freq_str), freq_low_here)
    flow_ifo_dict[inst] = freq_low_here

for inst, psdf in map(lambda c: c.split("="), opts.psd_file):
    print("Reading PSD for instrument %s from %s" % (inst, psdf))
    psd_dict[inst] = lalsimutils.get_psd_series_from_xmldoc(psdf, inst)

    deltaF = data_dict[inst].deltaF
    psd_dict[inst] = lalsimutils.resample_psd_series(psd_dict[inst], deltaF)
    print("PSD deltaF after interpolation %f" % psd_dict[inst].deltaF)

    # implement cutoff.  
    if inst in flow_ifo_dict.keys():
        if isinstance(psd_dict[inst], lal.REAL8FrequencySeries):
            psd_fvals = psd_dict[inst].f0 + deltaF*numpy.arange(psd_dict[inst].data.length)
            psd_dict[inst].data.data[ psd_fvals < flow_ifo_dict[inst]] = 0 # 
        else:
            print('FAIL')
            sys.exit(0)
#        elif isinstance(psd_dict[inst], pylal.xlal.datatypes.real8frequencyseries.REAL8FrequencySeries):  # for backward compatibility
#            psd_fvals = psd_dict[inst].f0 + deltaF*numpy.arange(len(psd_dict[inst].data))
#            psd_dict[inst].data[psd_fvals < ifo_dict[inst]] =0


    assert psd_dict[inst].deltaF == deltaF

    # Highest freq. at which PSD is defined
    # if isinstance(psd_dict[inst],
    #         pylal.xlal.datatypes.real8frequencyseries.REAL8FrequencySeries):
    #     fmax = psd_dict[inst].f0 + deltaF * (len(psd_dict[inst].data) - 1)
    if isinstance(psd_dict[inst], lal.REAL8FrequencySeries):
        fmax = psd_dict[inst].f0 + deltaF * (psd_dict[inst].data.length - 1)

    # Assert upper limit of IP integral does not go past where PSD defined
    assert opts.fmax is None or opts.fmax<= fmax
    # Allow us to target a smaller upper limit than provided by the PSD. Important for numerical PSDs that turn over at high frequency
    if opts.fmax and opts.fmax < fmax:
        fmax = opts.fmax # fmax is now the upper freq. of IP integral

# Ensure data and PSDs keyed to same detectors
if sorted(psd_dict.keys()) != sorted(data_dict.keys()):
    print("Got a different set of instruments based on data and PSDs provided.", file=sys.stderr)

# Ensure waveform has same sample rate, padded length as data
#
# N.B. This assumes all detector data has same sample rate, length
#
# data_dict holds 2-sided FrequencySeries, so their length is the same as
# that of the original TimeSeries that was FFT'd = Nsamples
# Also, deltaF = 1/T, with T = the duration (in sec) of the original TimeSeries
# Therefore 1/(data.length*deltaF) = T/Nsamples = deltaT
P.deltaT = 1./ (data_dict[data_dict.keys()[0]].data.length * deltaF)
P.deltaF = deltaF
for Psig in P_list:
  Psig.deltaT = P.deltaT
  Psig.deltaf = P.deltaF






def analyze_event(P_list, indx_event, data_dict, psd_dict, fmax, opts,inv_spec_trunc_Q=inv_spec_trunc_Q, T_spec=T_spec):
    nEvals=0
    P = P_list[indx_event]
    # Precompute
    t_window = 0.15
    rholms_intp, cross_terms, cross_terms_V,  rholms, rest=factored_likelihood.PrecomputeLikelihoodTerms(
            fiducial_epoch, t_window, P, data_dict, psd_dict, opts.l_max, fmax,
            False, inv_spec_trunc_Q, T_spec,
            NR_group=NR_template_group,NR_param=NR_template_param,
            use_external_EOB=opts.use_external_EOB,nr_lookup=opts.nr_lookup,nr_lookup_valid_groups=opts.nr_lookup_group,perturbative_extraction=opts.nr_perturbative_extraction,use_provided_strain=opts.nr_use_provided_strain,hybrid_use=opts.nr_hybrid_use,hybrid_method=opts.nr_hybrid_method,ROM_group=opts.rom_group,ROM_param=opts.rom_param,ROM_use_basis=opts.rom_use_basis,verbose=opts.verbose,quiet=not opts.verbose,ROM_limit_basis_size=opts.rom_limit_basis_size_to,no_memory=opts.no_memory,skip_interpolation=opts.vectorized)


    # Only allocate the FFT plans ONCE
    ifo0 = psd_dict.keys()[0]
    npts = data_dict[ifo0].data.length
    print(" Allocating FFT forward, reverse plans ", npts)
    fwdplan = lal.CreateForwardREAL8FFTPlan(npts, 0)
    revplan = lal.CreateReverseREAL8FFTPlan(npts, 0)

    for ifo in psd_dict:
        # Plot PSDs
        plt.figure(99) # PSD figure)
        fvals = psd_dict[ifo].f0 + np.arange(psd_dict[ifo].data.length)*psd_dict[ifo].deltaF
        plt.plot(fvals,np.log10(np.sqrt(psd_dict[ifo].data.data)),label=ifo)
        plt.figure(88)
        plt.plot(fvals, fvals**(-14./6.) /psd_dict[ifo].data.data)
        plt.figure(1)

        # Plot inverse spectrum filters
        #     - see lalsimutils code for inv_spec_trunc_Q , copied verbatim
        plt.figure(98)
        IP_here = lalsimutils.ComplexOverlap(P.fmin, fmax, 1./2/P.deltaT, P.deltaF, psd_dict[ifo], False,
                                             inv_spec_trunc_Q, T_spec)
        WFD = lal.CreateCOMPLEX16FrequencySeries('FD root inv. spec.',
                                                 lal.LIGOTimeGPS(0.), 0., IP_here.deltaF,
                                                 lal.DimensionlessUnit, IP_here.len1side)
        WTD = lal.CreateREAL8TimeSeries('TD root inv. spec.',
                    lal.LIGOTimeGPS(0.), 0., IP_here.deltaT,
                    lal.DimensionlessUnit, IP_here.len2side)
        print(ifo, IP_here.len2side)
#        if not(fwdplan is None):
        WFD.data.data[:] = np.sqrt(IP_here.weights) # W_FD is 1/sqrt(S_n(f))
        WFD.data.data[0] = WFD.data.data[-1] = 0. # zero 0, f_Nyq bins
        lal.REAL8FreqTimeFFT(WTD, WFD, revplan) # IFFT to TD
        tvals = IP_here.deltaT*np.arange(IP_here.len2side)
        plt.plot(tvals, np.log10(np.abs(WTD.data.data)),label=ifo)

        # Plot Q's
        plt.figure(1);
        plt.clf()
        for mode in rholms[ifo]:
            Q_here = rholms[ifo][mode]
            tvals = lalsimutils.evaluate_tvals(Q_here) - P.tref
            plt.plot(tvals, np.abs(Q_here.data.data),label=ifo+str(mode[0])+","+str(mode[1]))
        plt.legend();
        plt.xlabel("t (s)"); plt.xlim(-0.1,0.1); plt.xlabel("$Q_{lm}$")
        plt.title(ifo)
        plt.savefig(ifo+ "_Q.png")
        
    plt.figure(99); plt.legend(); plt.xlabel("f(Hz)"); plt.ylabel(r'$\sqrt{S_h}$'); plt.ylim(-24,-21)
    plt.savefig("PSD_plots.png")
    plt.xlim(5,800)
    plt.savefig("PSD_plots_detail.png")
    plt.xlim(10,400); plt.ylim(-23.5,-22)
    plt.savefig("PSD_plots_detail_fine.png")
    plt.figure(98); plt.legend(); plt.xlabel("t (s)")
    plt.savefig("PSD_inv_plots.png")
    plt.figure(88); plt.legend(); plt.xlabel("f (Hz)"); plt.ylabel(r'$(S_h f^{15/6})^{-1}$')
    plt.savefig("PSD_weight_f.png")

lnL_sofar = -np.inf
no_adapt_sky = False
for indx in numpy.arange(len(P_list)):
  res = analyze_event(P_list, indx, data_dict, psd_dict, fmax, opts)
