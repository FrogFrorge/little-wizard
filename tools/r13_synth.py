"""Round 13: a small DSP toolkit for the game's sound design and music (numpy + scipy).

Everything is 48 kHz float; mono arrays are 1-D, stereo arrays are (n, 2).
Building blocks: oscillators (band-limited saw / square by polyBLEP, FM, additive
bells, Karplus-Strong plucks), noise colours, static and time-varying filters,
envelopes, a synthetic-impulse convolution reverb, saturation, a compressor and
a limiter, a canvas to lay sounds out in time, WAV output and spectrogram
pictures for checking the sounds by eye.
"""
import wave
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d

SR = 48000
RNG = np.random.default_rng(1313)


def seed(n):
    global RNG
    RNG = np.random.default_rng(n)


def ns(d):
    return max(1, int(round(d * SR)))


def secs(d):
    return np.arange(ns(d)) / SR


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, float) - 69.0) / 12.0)


def db(v):
    return 10.0 ** (v / 20.0)


# ------------------------------------------------------------------ curves
def line(d, a, b):
    return np.linspace(a, b, ns(d))


def expo(d, a, b):
    """Exponential glide from a to b (both > 0)."""
    return a * (b / a) ** np.linspace(0.0, 1.0, ns(d))


def pts(d, points, kind='lin'):
    """Piecewise curve through (time, value) points; kind 'exp' interpolates in log."""
    t = secs(d)
    tt = np.array([p[0] for p in points], float)
    vv = np.array([p[1] for p in points], float)
    if kind == 'exp':
        return np.exp(np.interp(t, tt, np.log(np.maximum(vv, 1e-9))))
    return np.interp(t, tt, vv)


def env_ad(d, a=0.005, decay=0.2, curve=1.0):
    """Attack then exponential decay (time constant decay)."""
    t = secs(d)
    e = np.exp(-np.maximum(t - a, 0) / max(decay, 1e-4))
    e *= np.minimum(t / max(a, 1e-5), 1.0) ** curve
    return e


def env_adsr(d, a=0.01, dec=0.1, s=0.7, r=0.2):
    t = secs(d)
    e = np.where(t < a, t / max(a, 1e-5), s + (1 - s) * np.exp(-(t - a) / max(dec, 1e-4)))
    rel = np.clip((d - t) / max(r, 1e-4), 0, 1)
    return e * rel


def swell(d, power=2.0):
    """0 -> 1 rising curve (for risers)."""
    return np.linspace(0, 1, ns(d)) ** power


def fade(x, fi=0.002, fo=0.01):
    x = np.array(x, float, copy=True)
    n = len(x)
    a, b = min(ns(fi), n), min(ns(fo), n)
    w = np.ones(n)
    if a > 1:
        w[:a] = np.linspace(0, 1, a)
    if b > 1:
        w[-b:] *= np.linspace(1, 0, b)
    return x * (w if x.ndim == 1 else w[:, None])


# ------------------------------------------------------------------ oscillators
def _freq(f, d):
    n = ns(d)
    return np.full(n, float(f)) if np.isscalar(f) else np.asarray(f, float)[:n]


def phase(f, d, ph0=0.0):
    """Cycles (not radians) for a frequency curve."""
    fr = _freq(f, d)
    return ph0 + np.cumsum(fr) / SR, fr


def sine(f, d, ph0=0.0):
    p, _ = phase(f, d, ph0)
    return np.sin(2 * np.pi * p)


def _blep(t, dt):
    """polyBLEP residual for a unit step at t (fractional phase) with increment dt."""
    r = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    r[a] = x + x - x * x - 1.0
    b = t > 1.0 - dt
    x = (t[b] - 1.0) / dt[b]
    r[b] = x * x + x + x + 1.0
    return r


def saw(f, d, ph0=0.0):
    p, fr = phase(f, d, ph0)
    t = p % 1.0
    dt = np.clip(np.abs(fr) / SR, 1e-6, 0.5)
    return 2.0 * t - 1.0 - _blep(t, dt)


def square(f, d, pw=0.5, ph0=0.0):
    p, fr = phase(f, d, ph0)
    dt = np.clip(np.abs(fr) / SR, 1e-6, 0.5)
    t1 = p % 1.0
    t2 = (p + (1.0 - pw)) % 1.0
    s1 = 2.0 * t1 - 1.0 - _blep(t1, dt)
    s2 = 2.0 * t2 - 1.0 - _blep(t2, dt)
    return 0.5 * (s1 - s2)


def tri(f, d, ph0=0.0):
    p, _ = phase(f, d, ph0)
    t = p % 1.0
    return 4.0 * np.abs(t - 0.5) - 1.0


def supersaw(f, d, voices=5, detune=0.12, mix=1.0):
    """Detuned saws (detune in semitones across the stack)."""
    out = np.zeros(ns(d))
    offs = np.linspace(-detune, detune, voices) if voices > 1 else [0.0]
    for k, o in enumerate(offs):
        out += saw(_freq(f, d) * 2 ** (o / 12.0), d, RNG.uniform(0, 1))
    return out / np.sqrt(voices) * mix


def fm(fc, ratio, index, d, fb=0.0):
    """Two-operator FM: carrier fc (curve or scalar), modulator fc*ratio, index (curve or scalar)."""
    p, fr = phase(fc, d)
    pm, _ = phase(fr * ratio, d)
    idx = np.full(len(p), float(index)) if np.isscalar(index) else np.asarray(index, float)[:len(p)]
    mod = np.sin(2 * np.pi * pm)
    if fb:
        mod = np.sin(2 * np.pi * pm + fb * mod)
    return np.sin(2 * np.pi * p + idx * mod)


def bell(f, d, partials=((1, 1, 1.0), (2.76, .45, .55), (5.40, .25, .35), (8.93, .12, .22)), bright=1.0,
         decay=1.2, detune=0.0):
    """Inharmonic additive bell / glass / glockenspiel: (ratio, amp, decay factor)."""
    t = secs(d)
    out = np.zeros(len(t))
    for r, a, k in partials:
        ff = f * r * (1 + detune * RNG.uniform(-1, 1))
        if ff > SR * 0.45:
            continue
        out += a * bright ** (r > 1.5) * np.sin(2 * np.pi * ff * t + RNG.uniform(0, 6.28)) * np.exp(-t / (decay * k))
    # no hard cut where the note's buffer ends: the last 30% fades out
    tail = np.clip((d - t) / max(d * 0.3, 1e-3), 0, 1)
    return out * np.minimum(t / 0.0015, 1) * tail


def pluck(f, d, decay=0.996, bright=0.5, body=None):
    """Karplus-Strong string: noise burst through a delay line with a one-zero lowpass."""
    n = ns(d)
    period = max(2, int(round(SR / f)))
    burst = RNG.uniform(-1, 1, period)
    if bright < 1:
        burst = signal.lfilter([1 - bright], [1, -bright], burst)
    # y[n] = x[n] + decay * (y[n-P] + y[n-P-1]) / 2  -> an IIR with a long denominator
    a = np.zeros(period + 2)
    a[0] = 1.0
    a[period] = -decay * 0.5
    a[period + 1] = -decay * 0.5
    x = np.zeros(n)
    x[:period] = burst
    y = signal.lfilter([1.0], a, x)
    if body is not None:
        y = bandpass(y, body[0], body[1])
    y *= np.clip((n - np.arange(n)) / max(n * 0.25, 1), 0, 1)
    return y / (np.max(np.abs(y)) + 1e-9)


# ------------------------------------------------------------------ noise
def white(d):
    return RNG.standard_normal(ns(d))


def pink(d):
    n = ns(d)
    x = RNG.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[1:] /= np.sqrt(f[1:])
    X[0] = 0
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-12)


def brown(d):
    x = np.cumsum(RNG.standard_normal(ns(d)))
    x = hp(x, 20.0)
    return x / (np.std(x) + 1e-12)


def crackle(d, rate, decay=0.003, lo=1500, hi=9000, rate_curve=None):
    """Sparse random clicks (fire crackles, ice ticks, sparks); rate in clicks / s."""
    n = ns(d)
    r = np.full(n, rate) if rate_curve is None else rate_curve[:n] * rate
    hits = RNG.random(n) < r / SR
    x = np.zeros(n)
    x[hits] = RNG.uniform(0.3, 1.0, hits.sum()) * RNG.choice([-1, 1], hits.sum())
    # each click is a tiny decaying noise burst (not a bare pulse): grainier, less 'tick'
    k = np.exp(-np.arange(ns(decay * 6)) / (decay * SR)) * RNG.standard_normal(ns(decay * 6))
    y = signal.fftconvolve(x, k)[:n]
    return bandpass(y, lo, hi)


# ------------------------------------------------------------------ filters
def _sos(kind, f, order=2):
    if kind in ('lowpass', 'highpass'):
        f = float(np.clip(f, 10, SR * 0.49))
    else:
        f = [float(np.clip(f[0], 10, SR * 0.48)), float(np.clip(f[1], 12, SR * 0.49))]
    return signal.butter(order, f, btype=kind, fs=SR, output='sos')


def _apply(x, sos):
    if x.ndim == 1:
        return signal.sosfilt(sos, x)
    return np.stack([signal.sosfilt(sos, x[:, i]) for i in range(x.shape[1])], axis=1)


def lp(x, f, order=2):
    return _apply(x, _sos('lowpass', f, order))


def hp(x, f, order=2):
    return _apply(x, _sos('highpass', f, order))


def bandpass(x, lo, hi, order=2):
    return _apply(x, _sos('bandpass', (lo, hi), order))


def peak_eq(x, f0, gain_db, q=1.0):
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    if x.ndim == 1:
        return signal.lfilter(b, a, x)
    return np.stack([signal.lfilter(b, a, x[:, i]) for i in range(x.shape[1])], axis=1)


def _biquad(mode, f0, q):
    w = 2 * np.pi * np.clip(f0, 10, SR * 0.45) / SR
    c, s = np.cos(w), np.sin(w)
    al = s / (2 * q)
    if mode == 'lp':
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    elif mode == 'hp':
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    elif mode == 'bp':
        b = [al, 0.0, -al]
    else:  # notch
        b = [1.0, -2 * c, 1.0]
    a = [1 + al, -2 * c, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def sweep(x, fc, q=0.707, mode='lp', block=64):
    """Time-varying resonant biquad: fc is a per-sample curve (or scalar)."""
    x = np.asarray(x, float)
    mono = x.ndim == 1
    xs = x[:, None] if mono else x
    n = len(xs)
    fcs = np.full(n, float(fc)) if np.isscalar(fc) else np.resize(np.asarray(fc, float), n)
    qs = np.full(n, float(q)) if np.isscalar(q) else np.resize(np.asarray(q, float), n)
    out = np.zeros_like(xs)
    zi = [np.zeros(2) for _ in range(xs.shape[1])]
    for i in range(0, n, block):
        j = min(n, i + block)
        b, a = _biquad(mode, fcs[i:j].mean(), qs[i:j].mean())
        for ch in range(xs.shape[1]):
            out[i:j, ch], zi[ch] = signal.lfilter(b, a, xs[i:j, ch], zi=zi[ch])
    return out[:, 0] if mono else out


# ------------------------------------------------------------------ space
_IR_CACHE = {}


def reverb_ir(rt=1.6, predelay=0.012, damp=5500.0, size=1.0, early=10, width=1.0, key=None):
    """Synthetic stereo impulse response: sparse early reflections + a band-split
    exponentially decaying noise tail (lows ring longer than highs)."""
    ck = key or (rt, predelay, damp, size, early, width)
    if ck in _IR_CACHE:
        return _IR_CACHE[ck]
    d = rt * 1.2 + predelay + 0.05
    n = ns(d)
    t = np.arange(n) / SR
    rng = np.random.default_rng(hash(ck) % (2 ** 32))
    ir = np.zeros((n, 2))
    for k in range(early):
        at = predelay + rng.uniform(0.003, 0.06 * size)
        i = int(at * SR)
        if i < n:
            g = rng.uniform(0.25, 0.7) * np.exp(-at * 8)
            p = rng.uniform(-1, 1) * width
            ir[i, 0] += g * np.sqrt((1 - p) / 2)
            ir[i, 1] += g * np.sqrt((1 + p) / 2)
    tail = np.zeros((n, 2))
    for lo, hi, rt_k in ((20, 400, 1.25), (400, 3000, 1.0), (3000, 16000, 0.55)):
        for ch in range(2):
            z = rng.standard_normal(n)
            z = signal.sosfilt(signal.butter(2, [lo, min(hi, SR * 0.45)], btype='bandpass', fs=SR, output='sos'), z)
            tail[:, ch] += z * np.exp(-6.9 * np.maximum(t - predelay, 0) / (rt * rt_k))
    # decorrelate L/R slightly less for a stable centre
    mid = tail.mean(1, keepdims=True)
    tail = mid + (tail - mid) * width
    tail[: int(predelay * SR)] = 0
    tail *= np.minimum(np.maximum(t - predelay, 0) / 0.02, 1)[:, None]
    tail = lp(tail, damp, 1)
    ir += tail * 0.12
    ir /= np.sqrt(np.sum(ir ** 2) / 2) + 1e-12
    _IR_CACHE[ck] = ir
    return ir


def reverb(x, wet=0.25, rt=1.6, predelay=0.012, damp=5500.0, size=1.0, width=1.0, dry=1.0, hp_send=150.0):
    """Convolution reverb; returns stereo of length len(x) + tail."""
    x2 = st(x)
    ir = reverb_ir(rt, predelay, damp, size, 10, width)
    send = hp(x2, hp_send, 1) if hp_send else x2
    tail = np.stack([signal.fftconvolve(send[:, c], ir[:, c]) for c in range(2)], axis=1)
    out = np.zeros_like(tail)
    out[:len(x2)] += x2 * dry
    out += tail * wet
    return out


def delay(x, time=0.25, fb=0.35, wet=0.3, pingpong=True, damp=4000.0, taps=6):
    x2 = st(x)
    dn = ns(time)
    n = len(x2) + dn * taps
    out = np.zeros((n, 2))
    out[:len(x2)] += x2
    tap = x2.copy()
    for k in range(1, taps + 1):
        tap = lp(tap, damp, 1) * fb
        if pingpong:
            tap = tap[:, ::-1]
        out[k * dn:k * dn + len(tap)] += tap * (wet / max(fb, 1e-3))
    return out


# ------------------------------------------------------------------ stereo / layout
def st(x, pan=0.0):
    """Mono -> stereo with equal-power pan (stereo passes through)."""
    x = np.asarray(x, float)
    if x.ndim == 2:
        return x
    p = np.clip(pan, -1, 1)
    if np.isscalar(p) or np.ndim(p) == 0:
        return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], axis=1)
    p = np.resize(np.asarray(p, float), len(x))
    return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], axis=1)


def widen(x, ms=12.0, amount=0.5):
    x2 = st(x)
    k = ns(ms / 1000)
    side = np.zeros_like(x2[:, 0])
    side[k:] = x2[:-k, 0] - x2[:-k, 1] if k < len(x2) else 0
    mid = x2.mean(1)
    dly = np.concatenate([np.zeros(k), mid[:-k]]) if k < len(mid) else mid
    return np.stack([x2[:, 0] + amount * (mid - dly) * 0.5, x2[:, 1] - amount * (mid - dly) * 0.5], axis=1)


def rev(x):
    return np.asarray(x)[::-1].copy()


def stretch(x, rate):
    """Resample (pitch + speed) by rate (curve or scalar)."""
    x = np.asarray(x, float)
    n = len(x)
    if np.isscalar(rate):
        idx = np.arange(0, n - 1, rate)
    else:
        r = np.resize(np.asarray(rate, float), n)
        idx = np.cumsum(r)
        idx = idx[idx < n - 1]
    if x.ndim == 1:
        return np.interp(idx, np.arange(n), x)
    return np.stack([np.interp(idx, np.arange(n), x[:, c]) for c in range(x.shape[1])], axis=1)


class Canvas:
    """A growing stereo buffer: put(x, at seconds, gain, pan)."""

    def __init__(self, d=1.0):
        self.buf = np.zeros((ns(d), 2))

    def put(self, x, at=0.0, gain=1.0, pan=0.0):
        x2 = st(x, pan) * gain
        i = int(round(at * SR))
        if i < 0:
            x2 = x2[-i:]
            i = 0
        end = i + len(x2)
        if end > len(self.buf):
            self.buf = np.concatenate([self.buf, np.zeros((end - len(self.buf), 2))])
        self.buf[i:end] += x2
        return self

    def out(self):
        return self.buf


# ------------------------------------------------------------------ dynamics / colour
def sat(x, drive=2.0):
    return np.tanh(drive * x) / np.tanh(drive)


def fold(x, amt=1.5):
    return np.sin(np.pi / 2 * amt * x)


def crush(x, bits=8, down=1):
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    if down > 1:
        y = np.repeat(y[::down], down, axis=0)[:len(x)]
    return y


def env_follow(x, attack=0.002, release=0.08):
    a = np.abs(st(x)).max(1)
    ga = np.exp(-1 / (attack * SR))
    gr = np.exp(-1 / (release * SR))
    # attack/release one-pole via two passes: peak hold then smooth
    held = maximum_filter1d(a, size=max(1, int(attack * SR * 4)))
    return signal.lfilter([1 - gr], [1, -gr], held)


def compress(x, thresh_db=-18, ratio=3.0, attack=0.004, release=0.12, makeup_db=0.0, knee=6.0):
    x2 = st(x)
    e = env_follow(x2, attack, release) + 1e-9
    lev = 20 * np.log10(e)
    over = lev - thresh_db
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    g = 10 ** ((-gr + makeup_db) / 20)
    return x2 * g[:, None]


def limit(x, ceiling=0.95, release=0.06, look=0.002):
    x2 = st(x)
    k = max(1, ns(look))
    pk = maximum_filter1d(np.abs(x2).max(1), size=2 * k + 1)
    g = np.minimum(1.0, ceiling / (pk + 1e-9))
    gr = np.exp(-1 / (release * SR))
    # smooth: instant down, slow up (min-hold then one-pole on 1-g)
    red = 1 - g
    red = maximum_filter1d(red, size=2 * k + 1)
    red = signal.lfilter([1 - gr], [1, -gr], red)
    red = np.maximum(red, 1 - g)
    return np.clip(x2 * (1 - red)[:, None], -ceiling, ceiling)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))) + 1e-12)


def peak(x):
    return float(np.max(np.abs(x)) + 1e-12)


def norm_peak(x, p_db=-1.0):
    return np.asarray(x) * (db(p_db) / peak(x))


def norm_rms(x, r_db=-18.0, ceiling_db=-0.8):
    y = np.asarray(x) * (db(r_db) / rms(x))
    if peak(y) > db(ceiling_db):
        y = limit(y, db(ceiling_db))
    return y


def trim(x, thresh_db=-70, pad=0.02):
    a = np.abs(st(x)).max(1)
    idx = np.where(a > db(thresh_db))[0]
    if len(idx) == 0:
        return x
    end = min(len(a), idx[-1] + ns(pad))
    return x[:end]


# ------------------------------------------------------------------ files / checks
def write_wav(path, x, sr=SR):
    x = np.asarray(x, float)
    x = np.clip(x, -1.0, 1.0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1 if x.ndim == 1 else x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype('<i2').tobytes())


def read_wav(path):
    with wave.open(str(path), 'rb') as w:
        ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), '<i2').astype(float) / 32768
    x = x.reshape(-1, ch)
    return (x[:, 0] if ch == 1 else x), sr


def spectrogram_image(x, title='', width=900, height=300, fmax=16000):
    """A log-frequency spectrogram (PIL image) with the waveform on top."""
    from PIL import Image, ImageDraw
    m = st(x).mean(1)
    f, t, S = signal.spectrogram(m, SR, nperseg=1024, noverlap=896)
    S = 10 * np.log10(S + 1e-12)
    S = np.clip((S - S.max() + 80) / 80, 0, 1)
    fl = np.geomspace(40, fmax, height)
    rows = np.array([np.interp(fl, f, S[:, i]) for i in range(S.shape[1])]).T[::-1]
    cols = np.interp(np.linspace(0, rows.shape[1] - 1, width), np.arange(rows.shape[1]), np.arange(rows.shape[1])).astype(int)
    img = rows[:, cols]
    rgb = np.stack([img ** 0.6, img ** 1.4, (1 - img) * img * 2.5], axis=2).clip(0, 1)
    im = Image.fromarray((rgb * 255).astype(np.uint8))
    wave_h = 70
    canvas = Image.new('RGB', (width, height + wave_h + 22), (18, 18, 24))
    canvas.paste(im, (0, wave_h + 22))
    d = ImageDraw.Draw(canvas)
    env = np.abs(m)
    seg = np.array_split(env, width)
    for i, s in enumerate(seg):
        v = float(s.max()) if len(s) else 0
        d.line([(i, wave_h / 2 + 11 - v * wave_h / 2), (i, wave_h / 2 + 11 + v * wave_h / 2)], fill=(120, 200, 255))
    d.text((6, 4), '%s   %.2f s   peak %.1f dB   rms %.1f dB' % (title, len(m) / SR, 20 * np.log10(peak(m)), 20 * np.log10(rms(m))),
           fill=(240, 240, 240))
    return canvas
