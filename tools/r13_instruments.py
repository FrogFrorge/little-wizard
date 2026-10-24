"""Round 13: synthesized instruments for the music and the musical stingers.

Each note function returns a mono float array: note(midi, seconds, velocity 0..1).
Drums take (velocity) and return their natural length.  All built on r13_synth.
"""
import numpy as np

import r13_synth as S
from r13_synth import SR, secs, ns, mtof


def _adsr(d, a, dec, s, r):
    return S.env_adsr(d, a, dec, s, r)


def _vib(d, rate=5.5, depth=0.12, delay=0.25):
    """Vibrato as a frequency ratio curve (depth in semitones), fading in after delay."""
    t = secs(d)
    fade_in = np.clip((t - delay) / 0.3, 0, 1)
    return 2 ** (depth * fade_in * np.sin(2 * np.pi * rate * t + S.RNG.uniform(0, 6.28)) / 12)


# ------------------------------------------------------------------ pitched
def brass(m, d, vel=0.8, bright=1.0):
    f = mtof(m)
    t = secs(d)
    scoop = 2 ** (-0.35 * np.exp(-t / 0.035) / 12)
    fr = f * scoop * _vib(d, 5.2, 0.10, 0.35)
    x = S.saw(fr * 2 ** (0.06 / 12), d) + S.saw(fr * 2 ** (-0.06 / 12), d) + 0.5 * S.saw(fr * 0.5, d)
    cut = 350 + (900 + 3800 * vel * bright) * np.exp(-t / 0.18) + 900 * vel * bright
    x = S.sweep(x, cut, 0.9, 'lp')
    breath = S.bandpass(S.white(d), f * 1.5, min(f * 6, 9000)) * 0.08 * np.exp(-t / 0.06)
    return (x * 0.35 + breath) * _adsr(d, 0.025, 0.25, 0.75, 0.12) * vel


def strings(m, d, vel=0.7, bright=1.0):
    f = mtof(m)
    fr = f * _vib(d, 5.6, 0.11, 0.3)
    x = S.supersaw(fr, d, voices=6, detune=0.09)
    x = S.lp(x, 1800 + 2200 * bright * vel, 2)
    x = S.hp(x, 90, 1)
    return x * 0.32 * _adsr(d, 0.12, 0.3, 0.85, 0.28) * (0.4 + 0.6 * vel)


def pad(m, d, vel=0.6, bright=0.6):
    f = mtof(m)
    x = S.supersaw(f, d, voices=7, detune=0.16) + 0.6 * S.sine(f * 0.5, d)
    x = S.sweep(x, 700 + 1600 * bright * (0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * secs(d))), 0.8, 'lp')
    return x * 0.22 * _adsr(d, 0.35, 0.5, 0.9, 0.6) * vel


def pizz(m, d, vel=0.8):
    f = mtof(m)
    y = S.pluck(f, min(d + 0.4, 1.4), decay=0.990, bright=0.35, body=(max(80, f * 0.7), min(9000, f * 9)))
    return y[:ns(d + 0.4)] * vel * 0.8


def harp(m, d, vel=0.8):
    f = mtof(m)
    y = S.pluck(f, min(d + 1.2, 3.0), decay=0.9975, bright=0.55, body=(max(60, f * 0.6), min(12000, f * 14)))
    return y * vel * 0.7


def celesta(m, d, vel=0.8):
    f = mtof(m)
    y = S.bell(f, min(d + 1.0, 2.5), partials=((1, 1, 1.0), (2.0, 0.18, 0.5), (4.0, .22, 0.3), (6.2, .05, 0.15)), decay=0.9)
    return y * vel * 0.55


def glock(m, d, vel=0.8):
    f = mtof(m)
    y = S.bell(f, min(d + 1.4, 3.0), decay=1.3)
    return y * vel * 0.4


def musicbox(m, d, vel=0.8):
    f = mtof(m)
    y = S.bell(f, min(d + 0.8, 2.0), partials=((1, 1, 1.0), (3.0, 0.25, 0.4), (5.9, 0.12, 0.2), (8.2, .05, .12)), decay=0.6)
    return y * vel * 0.5


def flute(m, d, vel=0.7):
    f = mtof(m)
    fr = f * _vib(d, 5.0, 0.18, 0.18)
    x = S.sine(fr, d) + 0.22 * S.sine(fr * 2, d) + 0.06 * S.sine(fr * 3, d)
    breath = S.bandpass(S.white(d), f * 0.8, min(f * 3.0, 12000)) * 0.12
    e = _adsr(d, 0.045, 0.2, 0.85, 0.08)
    chiff = S.bandpass(S.white(d), 2000, 7000) * np.exp(-secs(d) / 0.025) * 0.15
    return (x * 0.5 + breath * e + chiff) * e * vel


def lead(m, d, vel=0.8, pw=0.3, cutoff=3200):
    f = mtof(m)
    fr = f * _vib(d, 6.0, 0.12, 0.2)
    x = S.square(fr, d, pw) * 0.6 + S.saw(fr * 1.003, d) * 0.4
    x = S.lp(x, cutoff, 2)
    return x * 0.3 * _adsr(d, 0.008, 0.2, 0.7, 0.06) * vel


def synthpluck(m, d, vel=0.8, bright=1.0):
    f = mtof(m)
    t = secs(d + 0.25)
    x = S.saw(f, d + 0.25) + S.saw(f * 1.006, d + 0.25)
    x = S.sweep(x, 300 + 5500 * bright * vel * np.exp(-t / 0.09), 1.2, 'lp')
    return x * 0.3 * S.env_ad(d + 0.25, 0.003, 0.22) * vel


def bass(m, d, vel=0.8, bright=0.5):
    f = mtof(m)
    t = secs(d)
    x = S.saw(f, d) * 0.6 + S.square(f * 1.002, d, 0.5) * 0.4
    x = S.sweep(x, 160 + (500 + 1500 * bright) * vel * np.exp(-t / 0.12), 1.1, 'lp')
    sub = S.sine(f, d) * 0.7
    return (x * 0.5 + sub) * _adsr(d, 0.004, 0.18, 0.8, 0.05) * vel * 0.6


def pick_bass(m, d, vel=0.8):
    f = mtof(m)
    y = S.pluck(f, d + 0.2, decay=0.997, bright=0.25)
    return (y * 0.6 + S.sine(f, d + 0.2) * S.env_ad(d + 0.2, 0.004, 0.35) * 0.6) * vel * 0.7


def choir(m, d, vel=0.6, vowel='a'):
    """Soft 'aah' pad: saws through two formant band-passes."""
    f = mtof(m)
    fr = f * _vib(d, 5.0, 0.08, 0.2)
    x = S.supersaw(fr, d, voices=4, detune=0.12)
    f1, f2 = {'a': (800, 1150), 'o': (500, 900), 'u': (350, 700)}[vowel]
    y = S.bandpass(x, f1 * 0.8, f1 * 1.25) + 0.7 * S.bandpass(x, f2 * 0.85, f2 * 1.2) + 0.15 * S.bandpass(x, 2500, 3500)
    return y * 0.5 * _adsr(d, 0.25, 0.4, 0.9, 0.4) * vel


# ------------------------------------------------------------------ drums
def kick(vel=1.0, tune=1.0, length=0.45):
    d = length
    t = secs(d)
    f = 45 * tune + 110 * tune * np.exp(-t / 0.035)
    body = S.sine(f, d) * S.env_ad(d, 0.0008, 0.16)
    click = S.hp(S.white(d), 2500) * np.exp(-t / 0.0025) * 0.35
    return S.sat(body + click, 1.6) * vel * 0.9


def snare(vel=1.0, tone=185, length=0.32, snap=1.0):
    d = length
    t = secs(d)
    body = (S.sine(tone * (1 + 0.6 * np.exp(-t / 0.01)), d) * 0.6 + S.sine(tone * 1.7, d) * 0.25) * np.exp(-t / 0.05)
    wires = S.bandpass(S.white(d), 1800, 9000) * np.exp(-t / (0.09 * snap)) * 0.9
    crack = S.hp(S.white(d), 3000) * np.exp(-t / 0.004) * 0.5
    return S.sat(body + wires + crack, 1.3) * vel * 0.6


def clap(vel=1.0):
    d = 0.35
    t = secs(d)
    n = S.bandpass(S.white(d), 900, 6000)
    e = np.zeros(len(t))
    for k, at in enumerate((0.0, 0.011, 0.022, 0.031)):
        e += np.where(t >= at, np.exp(-(t - at) / (0.008 if k < 3 else 0.11)), 0) * (0.8 if k < 3 else 1.0)
    return n * e * vel * 0.5


def hat(vel=1.0, open_=False):
    d = 0.5 if open_ else 0.09
    t = secs(d)
    metal = sum(S.square(f, d, 0.5) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
    x = S.hp(metal * 0.3 + S.white(d) * 0.6, 7000, 2)
    return x * np.exp(-t / (0.16 if open_ else 0.022)) * vel * 0.35


def shaker(vel=1.0):
    d = 0.12
    t = secs(d)
    return S.bandpass(S.white(d), 4000, 12000) * np.sin(np.pi * np.clip(t / 0.09, 0, 1)) ** 1.5 * vel * 0.3


def crash(vel=1.0, length=2.2):
    d = length
    t = secs(d)
    metal = sum(S.square(f, d, 0.5) for f in (299.0, 453.0, 621.0, 811.0, 1003.0, 1437.0)) * 0.15
    x = S.hp(metal + S.white(d) * 0.8, 3500, 2)
    return x * (np.exp(-t / 0.7) * 0.8 + np.exp(-t / 0.06) * 0.6) * vel * 0.35


def tom(m=45, vel=1.0):
    d = 0.6
    t = secs(d)
    f = mtof(m) * (1 + 0.5 * np.exp(-t / 0.03))
    x = S.sine(f, d) * np.exp(-t / 0.18) + S.sine(f * 1.6, d) * np.exp(-t / 0.08) * 0.3
    x += S.bandpass(S.white(d), 300, 3000) * np.exp(-t / 0.01) * 0.3
    return S.sat(x, 1.4) * vel * 0.7


def taiko(f=70.0, vel=1.0, length=1.2, slap=0.5):
    d = length
    t = secs(d)
    modes = ((1.0, 1.0, 0.30), (1.59, 0.45, 0.16), (2.14, 0.30, 0.11), (2.30, 0.22, 0.09), (2.65, 0.15, 0.07))
    x = np.zeros(len(t))
    for r, a, dec in modes:
        x += a * S.sine(f * r * (1 + 0.12 * np.exp(-t / 0.02)), d) * np.exp(-t / dec)
    x += slap * S.bandpass(S.white(d), 600, 3500) * np.exp(-t / 0.012)
    x += 0.25 * S.lp(S.white(d), 300) * np.exp(-t / 0.05)
    return S.sat(x * 0.8, 1.8) * vel


def timpani(m=43, vel=1.0, length=1.6):
    d = length
    t = secs(d)
    f = mtof(m)
    x = (S.sine(f, d) * np.exp(-t / 0.6) + 0.5 * S.sine(f * 1.5, d) * np.exp(-t / 0.35)
         + 0.3 * S.sine(f * 1.98, d) * np.exp(-t / 0.25) + 0.2 * S.sine(f * 2.44, d) * np.exp(-t / 0.18))
    x += S.bandpass(S.white(d), 200, 2000) * np.exp(-t / 0.015) * 0.4
    return S.sat(x * 0.6, 1.3) * vel


def timpani_roll(m=43, d=1.0, vel=1.0):
    out = np.zeros(ns(d + 1.6))
    n = int(d * 18)
    for k in range(n):
        a = timpani(m, (0.5 + 0.5 * k / max(n - 1, 1)) * vel * 0.5, 1.6)
        i = int(k / 18 * SR)
        out[i:i + len(a)] += a
    return out


def reverse_cymbal(d=1.2, vel=1.0):
    return S.rev(crash(vel, d + 0.2))[-ns(d):]
