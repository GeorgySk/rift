
import numpy as np
import lal
import sys

from scipy.optimize import leastsq, brentq
from scipy.linalg import eig, inv
from scipy.interpolate import interp1d

from .. import lalsimutils

rosDebug=True
#from matplotlib import pyplot as plt

def FisherProject(mtx,indx_list_preserve):
    """
    FisherProject(mtx, indx_list_preserve)
    returns mtxAA - mtxAB*(mtxBB^(-1))*mtxBA
    calculated using matrix algebra
    """
    indx_list_drop = np.array(list(set(np.arange(len(mtx)))-set(indx_list_preserve)))
#    print indx_list_preserve, indx_list_drop
    mtxAA = np.matrix(mtx[indx_list_preserve].T[indx_list_preserve])
    mtxBB = np.matrix(mtx[indx_list_drop].T[indx_list_drop])
    mtxAB = np.matrix(mtx[indx_list_preserve].T[indx_list_drop]).T
    # if rosDebug:
    #     print " upper matrix \n", mtxAA, mtxAA.shape
    #     print "lower matrix \n",mtxBB,  mtxBB.shape
    #     print " cross matrix \n", mtxAB,mtxAB.shape
    #     print "returned matrix\n ", mtxOut, mtxOut.shape
    mtxAB*mtxBB
    mtxOut = mtxAA - mtxAB*inv(mtxBB)*(mtxAB.T)
    return mtxOut

# EFFECTIVE FISHER (temporary copy  - should just import from Evan)
#
def effectiveFisher(residual_func, *flat_grids):
    """
    Fit a quadratic to the ambiguity function tabulated on a grid.
    Inputs:
        - a pointer to a function to compute residuals, e.g.
          z(x1, ..., xN) - fit
          for N-dimensions, this is called 'residualsNd'
        - N+1 flat arrays of length K. N arrays for each on N parameters,
          plus 1 array of values of the overlap
    Returns:
        - flat array of upper-triangular elements of the effective Fisher matrix

    Example:
    x1s = [x1_1, ..., x1_K]
    x2s = [x2_1, ..., x2_K]
    ...
    xNs = [xN_1, ..., xN_K]

    gamma = effectiveFisher(residualsNd, x1s, x2s, ..., xNs, rhos)
    gamma
        [g_11, g_12, ..., g_1N, g_22, ..., g_2N, g_33, ..., g_3N, ..., g_NN]
    """
    x0 = np.ones(len(flat_grids))
    fitgamma = leastsq(residual_func, x0=x0, args=tuple(flat_grids))
    return array_to_symmetric_matrix(fitgamma[0])

def residuals2d(gamma, y, x1, x2):
    g11 = gamma[0]
    g12 = gamma[1]
    g22 = gamma[2]
    return y - (1. - g11*x1*x1/2. - g12*x1*x2 - g22*x2*x2/2.)



def array_to_symmetric_matrix(gamma):
    """
    Given a flat array of length N*(N+1)/2 consisting of
    the upper right triangle of a symmetric matrix,
    return an NxN numpy array of the symmetric matrix

    Example:
        gamma = [1, 2, 3, 4, 5, 6]
        array_to_symmetric_matrix(gamma)
            array([[1,2,3],
                   [2,4,5],
                   [3,5,6]])
    """
    length = len(gamma)
    if length==3: # 2x2 matrix
        g11 = gamma[0]
        g12 = gamma[1]
        g22 = gamma[2]
        return np.array([[g11,g12],[g12,g22]])
    if length==6: # 3x3 matrix
        g11 = gamma[0]
        g12 = gamma[1]
        g13 = gamma[2]
        g22 = gamma[3]
        g23 = gamma[4]
        g33 = gamma[5]
        return np.array([[g11,g12,g13],[g12,g22,g23],[g13,g23,g33]])
    if length==10: # 4x4 matrix
        g11 = gamma[0]
        g12 = gamma[1]
        g13 = gamma[2]
        g14 = gamma[3]
        g22 = gamma[4]
        g23 = gamma[5]
        g24 = gamma[6]
        g33 = gamma[7]
        g34 = gamma[8]
        g44 = gamma[9]
        return np.array([[g11,g12,g13,g14],[g12,g22,g23,g24],
            [g13,g23,g33,g34],[g14,g24,g34,g44]])
    if length==15: # 5x5 matrix
        g11 = gamma[0]
        g12 = gamma[1]
        g13 = gamma[2]
        g14 = gamma[3]
        g15 = gamma[4]
        g22 = gamma[5]
        g23 = gamma[6]
        g24 = gamma[7]
        g25 = gamma[8]
        g33 = gamma[9]
        g34 = gamma[10]
        g35 = gamma[11]
        g44 = gamma[12]
        g45 = gamma[13]
        g55 = gamma[14]
        return np.array([[g11,g12,g13,g14,g15],[g12,g22,g23,g24,g25],
            [g13,g23,g33,g34,g35],[g14,g24,g34,g44,g45],[g15,g25,g5,g45,g55]])


# FREQUENCY DOMAIN METHOD
#   - Construct tool to differentiate phase combinations
#     Heavy tool, because it solves ODE for each parameter
#   - Construct tool to weight appropriately (i.e., )


# the tolerances need to scale with the chirp mass, using the correct scaling law
tolerances_relative = { 'mc':1e-3,'mtot': 1e-3}
tolerances_absolute = {'tref':1e-3, 'phiref':0.2, 'chi1': 0.01, 'eta': 0.001, 'theta1': 0.02, 'beta':0.01, 'thetaJN': 0.1 ,'phiJL':0.1}
unit_scale_factors ={'mc': lal.MSUN_SI, 'mtot': lal.MSUN_SI}

def PhaseSequenceLeadingOrder(P):
    """
    Like lalsimutils.PrecessingOrbitModesOfFrequencyApproximate(return_phase=True), but based 
    on leading-order expressions, calculated using V.  
      - *One-sided*.
      - irregular frequency sampling (not identical to what will be generated by that code)
    """
    V, phi, LNvec, E1vec, S1vec, S2vec = PrecessingOrbitOfTime(P)  # Properly handle fref
    freq = np.power(V.data.data,3.)/((P.m1+P.m2)*lsu_G/np.power(lsu_C,3.))/(np.pi)
    tvals = evaluate_tvals(V)  # This seems to be reliably aligned
    PsiF = 3/128./P.extract_parameter('eta') * np.power( freq*np.pi* P.extract_parameter('mc')/lal.MSUN_SI/lalsimutils.MsunInSec, -5./3.)
    alphaF = (2+3.*P.m2/(2*P.m1))*5./32. *(-1./3.)/V.data.data**3   # leading-order power, small spin limit
    betaF = np.ones(len(alphaF))*P.extract_parameter('beta')
    gammaF = alphaF  # small spin limit
    tF = ((P.m1+P.m2)/lal.MSUN_SI* lalsimutils.MsunInSec) * 5./256.* 1./P.extract_parameter('eta')/np.power(V.data.data,8)
    return freq,tF,phi.data.data, alphaF, betaF, gammaF


def PhaseDerivativeSeries(P,p1,skip_fast_derivative=False):
    """
    PhaseDerivativeSeries
    Using the waveform, constructs an array on a *full* range of f values which is nonzero *only for f>0*
    """
    print(" Phase derivatives for ", p1)
    Phere = P.manual_copy()
    fvals,fmax_safe, tF,PhiF,alphaF,betaF,gammaF = lalsimutils.PrecessingOrbitModesOfFrequencyApproximate(Phere,2,return_phases=True)
    # zero out all components except that which satisfy conditions. Easiest way to keep on consistent sample
    Psi2F =2*np.pi*fvals*tF - 2*PhiF
    f_pos_bad = np.logical_not(np.logical_and(fvals > 0, fvals<fmax_safe, fvals > P.fmin))
    Psi2F[f_pos_bad] = 0
    alphaF[f_pos_bad]=0
    betaF[f_pos_bad]=0
    gammaF[f_pos_bad]=0

    # For special parameters (time, alpha0, orbital phase), compute the derivatives *manually* via analytic formulae
    if p1 is 'tref' and not skip_fast_derivative:
        # Psi_m  =2 pi f t - m Phi_orb, so derivative is 2 pi f. Others are indepenent of tref
        dPsi2F = 2*np.pi*(fvals)       # from standard reading of tref in form of psi. strictly, dPsi/dtref = omega (dt/dtref) - m dphiorb/dref = omega.  Note that because  of how 
        dPhi2F = np.zeros(len(fvals))   # because of how the calculation is organized
        dalphaF = np.zeros(len(fvals))
        dgammaF = np.zeros(len(fvals))
        return fvals,fmax_safe, dPsi2F, dPsi2F,dalphaF,dgammaF

    if p1 is 'phiJL' and not skip_fast_derivative:
        # dalpha/dp1 = 1, dgamma/dt = cos beta
        dPsi2F = np.zeros(len(fvals))
        dPhi2F = np.zeros(len(fvals))
        dalphaF = np.ones(len(fvals))
        dgammaF = -np.cos(betaF)  # sign
        return fvals,fmax_safe, dPsi2F,dPhi2F,dalphaF,dgammaF

    if p1 is 'phiref' and not skip_fast_derivative:
        dPsi2F = - 2*np.ones(len(fvals))
        dPhi2F = np.ones(len(fvals))
        dalphaF = np.zeros(len(fvals))
        dgammaF = np.zeros(len(fvals))
        return fvals,fmax_safe, dPsi2F,dPhi2F,dalphaF,dgammaF


    # Compute answer via derivative
    p1val = Phere.extract_param(p1)
    if p1 in tolerances_relative.keys():
        dp1 = p1val*tolerances_relative[p1]
    else:
        dp1 = tolerances_absolute[p1]
    if p1 in unit_scale_factors.keys():
        x_scale = unit_scale_factors[p1]
    else:
        x_scale = 1


    # Offset phases
    Phere.assign_param(p1,p1val+dp1)
    fvals_1,fmax_safe_1, tF_1, PhiF_1,alphaF_1,betaF_1,gammaF_1 = lalsimutils.PrecessingOrbitModesOfFrequencyApproximate(Phere,2,return_phases=True)
    Psi2F_1 =2*np.pi*fvals_1*tF_1 - 2*PhiF_1
    f_pos_bad = np.logical_not(np.logical_and(fvals > 0, fvals<fmax_safe, fvals > P.fmin)) # should be unchanged
    Psi2F_1[f_pos_bad] = 0
    alphaF_1[f_pos_bad]=0
    betaF_1[f_pos_bad]=0
    gammaF_1[f_pos_bad]=0


    # Derivative.  Note the series may have different length, so truncate - usually an issue at end, assuming length does not change
    n = len(fvals)
    n1 = len(fvals_1)
    if (1.*n/n1)<0.99 or 1.*n/n1 >1.01:
        print("  Catastrophic length change when computing phase derivative ")
        sys.exit(0)
    

    # Derivative of *psi* means we have to form psi first
    # Derivative is *corrected for units* here
    dPsi2F     = (Psi2F_1 -Psi2F)/(dp1/x_scale)
    dPhiF       = (PhiF_1 -PhiF)/(dp1/x_scale)
    dalphaF    = (alphaF_1 - alphaF)/(dp1/x_scale)
    dgammaF  = (gammaF_1 - gammaF)/(dp1/x_scale)

    return fvals,fmax_safe*0.98, dPsi2F,dPhiF, dalphaF,dgammaF  # give a little leeway on frequency




def NumericalFisherMatrixElement(P, p1, p2, psd, max_t=False, **kwargs):
    """
    NumericalFisherMatrixElement
    Full, no-approximations use of <d h | d h>

    NOT RELIABLE -- requires OBSCENELY small step to make deltas of phase resolved.
    """

    Phere = P.manual_copy()
    hf0  = lalsimutils.complex_hoff(Phere)
    if max_t:
        IP = lalsimutils.CreateCompatibleComplexOverlap(hf0, **kwargs)
    else:
        IP = lalsimutils.CreateCompatibleComplexIP(hf0,**kwargs)
    

    # Derivative by p1
    p1val = Phere.extract_param(p1)
    if p1 in tolerances_relative.keys():
        dp1 = p1val*tolerances_relative[p1]
    else:
        dp1 = tolerances_absolute[p1]
    Phere.assign_param(p1,p1val+dp1)
    hf_dp1 = lalsimutils.complex_hoff(Phere)
    Phere.assign_param(p1,p1val)
    hf_dp1.data.data = (hf_dp1.data.data - hf0.data.data)/dp1


    # Derivative by p2
    p2val = Phere.extract_param(p2)
    if p2 in tolerances_relative.keys():
        dp2 = p2val*tolerances_relative[p2]
    else:
        dp2 = tolerances_absolute[p2]
    Phere.assign_param(p2,p2val+dp2)
    hf_dp2 = lalsimutils.complex_hoff(Phere)
    Phere.assign_param(p2,p2val)
    hf_dp2.data.data = (hf_dp2.data.data - hf0.data.data)/dp2


    return IP.ip(hf_dp1,hf_dp2)/IP.norm(hf0)**2


def EffectiveFisherMatrixElement(P,p1,p2,psd,max_t=True,**kwargs):
    if p1 is p2:
        dat =  OverlapVersusChangingParameter(P,p1,psd,max_t=max_t,**kwargs)
        xvals, yvals = dat[:,0], dat[:,1]
        z = np.polyfit(xvals,yvals,2)
        return -0.5*z[0]*np.sign( xvals[-1]-xvals[0])   # coefficient of quadratic
    else:
        print(" Off-diagonal elements not yet implemented")
        sys.exit(0)


def ApproximatePrecessingFisherMatrixElement(P, p1,p2,psd,return_intermediate=False,phase_deriv_cache=None,break_out_beta=False,**kwargs):
    rho2Net = 0
    gammaNet= 0
    gammaIntermediate = {}
    rho2Intermediate = {}

    # Precompute all the derivatives I will need - saves some recomputation.  
    # Alternatively, top-level user computes all derivatives once and for all
    if not phase_deriv_cache:
        phase_deriv_cache={}
        phase_deriv_cache[p1] =  PhaseDerivativeSeries(P,p1)
        if not (p1 is p2):
            phase_deriv_cache[p2] =  PhaseDerivativeSeries(P,p2)
    
    for m in [-2,-1,0,1,2]:
        for s in [-1,1]:
            rhoms2, gammaPart = ApproximatePrecessingFisherMatrixElementFactor(P,p1,p2,m,s,psd,phase_deriv_cache=phase_deriv_cache,break_out_beta=break_out_beta,**kwargs)
            if not break_out_beta:
                # adding up these quantities makes NO SENSE if we break up how gamma is computed into parts with different alpha dependence
                rho2Net +=rhoms2
                gammaNet += gammaPart
            gammaIntermediate[(m,s)]=gammaPart
            rho2Intermediate[(m,s)]=rhoms2
#            print " Integral parts ", m,s, rhoms2, gammaPart
#    print " Net amplitude for source ", np.sqrt(rho2Net)
    if return_intermediate:
        return rho2Intermediate, gammaIntermediate  # return the components going into the sum
    else:
        return gammaNet/rho2Net  # return normalized coefficient for this direction, to check overall result


def ApproximatePrecessingFisherMatrixElementFactor(P, p1,p2,m,s,psd,phase_deriv_cache=None,omit_geometric_factor=False,break_out_beta=False,**kwargs):
    """
    ApproximatePrecessingFisherMatrixElementFactor computes the weighted integral appearing in the sum, and the SNR weight.

    Ideally this calculation should CACHE existing phase derivatives (eg. by top-level user)
    Arguments:
       - phase_deriv_cache        : derivative of dphase/d\lambda for different parameters
       - omit_geometric_factor  : 
    """

    # Create basic infrastructure for IP. This requires VERY DENSE sampling...try to avoid
    # hF0 = lalsimutils.complex_hoff(P)
    # IP = lalsimutils.CreateCompatibleComplexIP(hF0,psd=psd,**kwargs)
    # dPsi2F_func =  interp1d(fvals,dPsi2F, fill_value=0, bounds_error=False)
    # dalphaF_func= interp

#    print " called  on ", p1,p2, m, s

    # This geometric stuff is all in common. I should make one call to generate Sh once and for all
    beta_0 = P.extract_param('beta')
    thetaJN_0 = P.extract_param('thetaJN')
    mc_s = P.extract_param('mc')/lal.MSUN_SI *lalsimutils.MsunInSec
    d_s  = P.extract_param('dist')/lal.C_SI  # distance in seconds

    if omit_geometric_factor:
        geometric_factor=1
    else:
        geometric_factor = np.abs(lal.SpinWeightedSphericalHarmonic(thetaJN_0,0,-2,2,int(m)) * lal.WignerDMatrix(2,m,s,0,beta_0,0))**2
    if np.abs(geometric_factor) < 1e-5:
        return 0,0  # saves lots of time

    # Create phase derivatives. Interpolate onto grid?  OR use lower-density sampling
    if phase_deriv_cache:
        if not (p1 in phase_deriv_cache.keys()):
            phase_deriv_cache[p1] =  PhaseDerivativeSeries(P,p1)
        else:
            fvals,fmax_safe, dPsi2F,dPhiF, dalphaF,dgammaF = phase_deriv_cache[p1]            
        if not (p2 in phase_deriv_cache.keys()):
            phase_deriv_cache[p2] =  PhaseDerivativeSeries(P,p2)
        else:
            fvals,fmax_safe, dPsi2F_2,dPhiF_2, dalphaF_2,dgammaF_2 =phase_deriv_cache[p2]            
    else:
        fvals,fmax_safe, dPsi2F,dPhiF, dalphaF,dgammaF = PhaseDerivativeSeries(P,p1)
        fvals,fmax_safe, dPsi2F_2,dPhiF_2, dalphaF_2,dgammaF_2 = PhaseDerivativeSeries(P,p2)

    dropme = np.logical_or(fvals <P.fmin, fvals>0.98*fmax_safe)

    Shvals = np.array(map(psd, np.abs(fvals)))
    Shvals[np.isnan(Shvals)]=float('inf')
    phase_weights =  4* (np.pi*mc_s*mc_s)**2/(3*d_s*d_s) *np.power((np.pi*mc_s*np.maximum(np.abs(fvals),P.fmin/2)),-7./3.)/Shvals  # hopefully one-sided. Note the P.fmin removes nans 
    phase_weights[np.isnan(phase_weights)]=0
    phase_weights[dropme] =0

    dalphaF[dropme] = 0
    dPsi2F[dropme] = 0
    dgammaF[dropme]=0

    dalphaF_2[dropme] = 0
    dPsi2F_2[dropme] = 0
    dgammaF_2[dropme]=0

    rhoms2 = np.sum(phase_weights*P.deltaF)*geometric_factor

    if (beta_0) < 1e-2:  # Pathological, cannot calculate alpha or gamma
        ret_weights = P.deltaF*phase_weights*geometric_factor*( dPsi2F)*(dPsi2F_2)
        ret = np.sum(ret_weights)
    else:
        if not break_out_beta:
            ret_weights = P.deltaF*phase_weights*geometric_factor*( dPsi2F- 2 *dgammaF + m*s*dalphaF)*(dPsi2F_2 - 2*dgammaF_2+m*s*dalphaF_2)
            ret = np.sum(ret_weights)
        else:
            # Warming: this uses the explicit assumption \gamma - -alpha cos beta
            # Warning: you probably never want this unless geometric_factor=1
            if not omit_geometric_factor:
                print(" You are extracting a breakdown of the fisher matrix versus beta, but are not fixing  the geometric factor...are you sure?")
            ret_00 = np.sum(P.deltaF*phase_weights*geometric_factor*( dPsi2F)*(dPsi2F_2 ))
            ret_01 = np.sum(P.deltaF*phase_weights*geometric_factor*( dPsi2F)*(dalphaF_2 ))
            ret_10 = np.sum(P.deltaF*phase_weights*geometric_factor*( dalphaF)*(dPsi2F_2 ))
            ret_11 = np.sum(P.deltaF*phase_weights*geometric_factor*( dalphaF)*(dalphaF_2))
            print("  -- submatrix ", p1,p2, ret_00, ret_01, ret_10, ret_11)
            return rhoms2,{"00":ret_00, "01":ret_01, "10": ret_10, "11": ret_11}

#    print " Internal fisher element", geometric_factor, rhoms2, ret
    # plt.plot(fvals,ret_weights)
    # plt.ylim(0,np.max(ret_weights))
    # plt.show()
             
    return rhoms2, ret

def OverlapVersusChangingParameter(P,p1,psd,max_t=False,cut_P=0.95,**kwargs):
    """
    Extract <h1|h2>/|h1||h2| as a function of one parameter
    (Intent here is for plotting *or* fitting, to extract diagonal fisher components)
    """
#    if rosDebug:
#        print "Overlap table called with ", kwargs

    Phere = P.manual_copy()
    hf0  = lalsimutils.complex_hoff(Phere)
    if max_t:
        IP = lalsimutils.CreateCompatibleComplexOverlap(hf0, **kwargs)
    else:
        IP = lalsimutils.CreateCompatibleComplexIP(hf0,**kwargs)
    

    
    p1val = Phere.extract_param(p1)
    if p1 in tolerances_relative.keys():
        dp1 = p1val*tolerances_relative[p1]
    else:
        dp1 = tolerances_absolute[p1]
    if p1 in unit_scale_factors.keys():
        x_scale = unit_scale_factors[p1]
    else:
        x_scale = 1

    xvals  = np.linspace(p1val-dp1,p1val+dp1,20)
    dat = []
    for x in xvals:
        Phere.assign_param(p1,x)
#        if not Phere.SoftAlignedQ():
#            Phere.print_params(show_system_frame=True)
        hF= lalsimutils.complex_hoff(Phere)
        z = IP.ip(hf0,hF)/IP.norm(hf0)/IP.norm(hF)
        if z > cut_P:
            dat.append( [x/x_scale,z])  # NORMALIZED

    return np.array(dat)

def OverlapGridVersusChangingParameter(P,p1,p2,psd,max_t=False,cut_P=0.95,**kwargs):
    """
    Extract <h1|h2>/|h1||h2| as a function of one parameter
    (Intent here is for plotting *or* fitting, to extract diagonal fisher components)
    """
#    if rosDebug:
#        print "Overlap table called with ", kwargs

    Phere = P.manual_copy()
    hf0  = lalsimutils.complex_hoff(Phere)
    if max_t:
        IP = lalsimutils.CreateCompatibleComplexOverlap(hf0, **kwargs)
    else:
        IP = lalsimutils.CreateCompatibleComplexIP(hf0,**kwargs)
    
    p1val = Phere.extract_param(p1)
    p2val = Phere.extract_param(p2)
    if p1 in tolerances_relative.keys():
        dp1 = p1val*tolerances_relative[p1]
    else:
        dp1 = tolerances_absolute[p1]
    if p2 in tolerances_relative.keys():
        dp2 = p2val*tolerances_relative[p2]
    else:
        dp2 = tolerances_absolute[p2]

    xvals  = np.linspace(p1val-dp1,p1val+dp1,9)
    yvals  = np.linspace(p2val-dp2,p2val+dp2,9)
    dat =[]
    if p1 in unit_scale_factors.keys():
        x_scale = unit_scale_factors[p1]
    else:
        x_scale = 1
    if p2 in unit_scale_factors.keys():
        y_scale = unit_scale_factors[p2]
    else:
        y_scale = 1
    for x in xvals:
     for y in yvals:
        Phere.assign_param(p1,x)
        Phere.assign_param(p2,y)
#        print (x/x_scale,y/y_scale), (Phere.extract_param(p1)/x_scale, Phere.extract_param(p2)/y_scale)
        hF= lalsimutils.complex_hoff(Phere)
        z = IP.ip(hf0,hF)/IP.norm(hf0)/IP.norm(hF)  # NORMALIZED
        if z> cut_P:
            dat.append([x/x_scale,y/y_scale,z])

    return np.array(dat)
