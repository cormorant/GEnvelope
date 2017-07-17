#coding:utf-8
from __future__ import division

import numpy as np
import sigtools


#=== function from signaltools ===
def lfilter(b, a, x, axis=-1, zi=None):
    """ Filter data along one-dimension with an IIR or FIR filter """
    if np.isscalar(a):
        a = [a]
    if zi is None:
        return sigtools._linear_filter(b, a, x, axis)
    else:
        return sigtools._linear_filter(b, a, x, axis, zi)
#===

def _relative_degree(z, p):
    """ Return relative degree of transfer function from zeros and poles """
    degree = len(p) - len(z)
    if degree < 0:
        raise ValueError("Improper transfer function. "
                         "Must have at least as many poles as zeros.")
    else:
        return degree


def _zpkbilinear(z, p, k, fs):
    """ Return digital filter from an analog one using a bilinear transform """
    z = np.atleast_1d(z)
    p = np.atleast_1d(p)
    degree = _relative_degree(z, p)
    fs2 = 2 * fs
    # Bilinear transform the poles and zeros
    z_z = (fs2 + z) / (fs2 - z)
    p_z = (fs2 + p) / (fs2 - p)
    # Any zeros that were at infinity get moved to the Nyquist frequency
    z_z = np.append(z_z, -np.ones(degree))
    # Compensate for gain change
    k_z = k * np.real(np.prod(fs2 - z) / np.prod(fs2 - p))
    return z_z, p_z, k_z


def _zpklp2bp(z, p, k, wo=1.0, bw=1.0):
    """ Transform a lowpass filter prototype to a bandpass filter """
    z = np.atleast_1d(z)
    p = np.atleast_1d(p)
    wo = np.float(wo)
    bw = np.float(bw)

    degree = _relative_degree(z, p)

    # Scale poles and zeros to desired bandwidth
    z_lp = z * bw/2
    p_lp = p * bw/2

    # Square root needs to produce complex result, not NaN
    z_lp = z_lp.astype(complex)
    p_lp = p_lp.astype(complex)

    # Duplicate poles and zeros and shift from baseband to +wo and -wo
    z_bp = np.concatenate((z_lp + np.sqrt(z_lp**2 - wo**2),
                        z_lp - np.sqrt(z_lp**2 - wo**2)))
    p_bp = np.concatenate((p_lp + np.sqrt(p_lp**2 - wo**2),
                        p_lp - np.sqrt(p_lp**2 - wo**2)))

    # Move degree zeros to origin, leaving degree zeros at infinity for BPF
    z_bp = np.append(z_bp, np.zeros(degree))

    # Cancel out gain change from frequency scaling
    k_bp = k * bw**degree

    return z_bp, p_bp, k_bp


def zpk2tf(z, p, k):
    " Return polynomial transfer function representation from zeros and poles "
    z = np.atleast_1d(z)
    k = np.atleast_1d(k)
    if len(z.shape) > 1:
        temp = np.poly(z[0])
        b = np.zeros((z.shape[0], z.shape[1] + 1), temp.dtype.char)
        if len(k) == 1:
            k = [k[0]] * z.shape[0]
        for i in range(z.shape[0]):
            b[i] = k[i] * np.poly(z[i])
    else:
        b = k * np.poly(z)
    a = np.atleast_1d(np.poly(p))
    # Use real output if possible
    if issubclass(b.dtype.type, np.complexfloating):
        # if complex roots are all complex conjugates, the roots are real.
        roots = np.asarray(z, complex)
        pos_roots = np.compress(roots.imag > 0, roots)
        neg_roots = np.conjugate(np.compress(roots.imag < 0, roots))
        if len(pos_roots) == len(neg_roots):
            if np.all(np.sort_complex(neg_roots) ==
                         np.sort_complex(pos_roots)):
                b = b.real.copy()
    if issubclass(a.dtype.type, np.complexfloating):
        # if complex roots are all complex conjugates, the roots are real.
        roots = np.asarray(p, complex)
        pos_roots = np.compress(roots.imag > 0, roots)
        neg_roots = np.conjugate(np.compress(roots.imag < 0, roots))
        if len(pos_roots) == len(neg_roots):
            if np.all(np.sort_complex(neg_roots) == np.sort_complex(pos_roots)):
                a = a.real.copy()
    return b, a


def iirfilter(N, Wn, rp=None, rs=None, btype='bandpass', analog=False,
              ftype='butter', output='ba'):
    """ IIR digital and analog filter design given order and critical points """
    ftype, btype, output = [x.lower() for x in (ftype, btype, output)]
    Wn = np.asarray(Wn)
    try:
        btype = band_dict[btype]
    except KeyError:
        raise ValueError("'%s' is an invalid bandtype for filter." % btype)
    
    try:
        typefunc = filter_dict[ftype][0]
    except KeyError:
        raise ValueError("'%s' is not a valid basic IIR filter." % ftype)

    if output not in ['ba', 'zpk']:
        raise ValueError("'%s' is not a valid output form." % output)
    
    if rp is not None and rp < 0:
        raise ValueError("passband ripple (rp) must be positive")

    if rs is not None and rs < 0:
        raise ValueError("stopband attenuation (rs) must be positive")

    # Get analog lowpass prototype
    if typefunc in [buttap]:
        z, p, k = typefunc(N)
    else:
        raise NotImplementedError("'%s' not implemented in iirfilter." % ftype)

    # Pre-warp frequencies for digital filter design
    if not analog:
        if np.any(Wn < 0) or np.any(Wn > 1):
            raise ValueError("Digital filter critical frequencies "
                             "must be 0 <= Wn <= 1")
        fs = 2.0
        warped = 2 * fs * np.tan(np.pi * Wn / fs)
    else:
        warped = Wn

    # transform to bandpass
    try:
        bw = warped[1] - warped[0]
        wo = np.sqrt(warped[0] * warped[1])
    except IndexError:
        raise ValueError('Wn must specify start and stop frequencies')

    z, p, k = _zpklp2bp(z, p, k, wo=wo, bw=bw)

    # Find discrete equivalent if necessary
    if not analog:
        z, p, k = _zpkbilinear(z, p, k, fs=fs)

    # Transform to proper out type (pole-zero, state-space, numer-denom)
    if output == 'zpk':
        return z, p, k
    elif output == 'ba':
        return zpk2tf(z, p, k)


def butter(N, Wn, btype='bandpass', analog=False, output='ba'):
    return iirfilter(N, Wn, btype=btype, analog=analog, output=output,
        ftype='butter')


def buttap(N):
    """ Return zero, pole, gain for analog prototype of an N-order Butterw filter """
    if np.abs(int(N)) != N:#!int?
        raise ValueError("Filter order must be a nonnegative integer")
    z = np.array([])
    m = np.arange(-N+1, N, 2)
    # Middle value is 0 to ensure an exactly real pole
    p = -np.exp(1j * np.pi * m / (2 * N))
    k = 1
    return z, p, k


filter_dict = {
    'butter': [buttap],
    'butterworth': [buttap],
}


band_dict = {
    'band': 'bandpass',
    'bandpass': 'bandpass',
    'pass': 'bandpass',
    'bp': 'bandpass',
}


#mine: filtering etc
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    """ bandpass Butterworth filter """
    nyquist = 0.5 * fs
    Wn = np.array([lowcut, highcut]) / nyquist
    b, a = butter(order, Wn, btype='bandpass')
    #return filtfilt(b, a, data)
    return lfilter(b, a, data)


def get_time(to):
    """ Возвращаем вычисленное время (Ч, М, С) из числа секунд с начала суток """
    hours, remainder = divmod(to, 3600)
    minutes, seconds = divmod(remainder, 60)
    # вернём время
    return hours, minutes, seconds
