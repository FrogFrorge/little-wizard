"""Round 13: every sound effect of 小小魔法師, redesigned (original synthesis, no samples).

python r13_sfx.py [name ...]   -> audio-r13/sfx/<Name>.wav, audio-r13/sfx-manifest.json,
                                  audio-r13/sheets/*.png (spectrograms for checking by eye)

The asset names are the game's (/Game/Audio/Wizard/<Group>/<Name>) so the import
replaces them in place; new ones: UltStart_<Wizard> (each wizard's ultimate wind-up,
0.8 s of build-up timed to the launch) and UltCutIn (the portrait cut-in).

Character of the set: bright, cute and punchy (a chibi wizard duel), with weight on
the hits.  The ultimates are the cinematic moments.
"""
import json
import sys
from pathlib import Path

import numpy as np

import r13_synth as S
import r13_instruments as I
from r13_synth import SR, secs, ns, Canvas, st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'audio-r13' / 'sfx'
SHEETS = ROOT / 'audio-r13' / 'sheets'
WINDUP = 0.8          # BP_WizardCharacter: Delay 0.8 between the wind-up and LaunchElementUltimate
REGISTRY = {}


def sound(name, group='SFX', kind='cast', loudness=-17.0, loop=False, volume=1.0, note=''):
    """kind -> UE concurrency / attenuation group; loudness = target RMS dBFS."""
    def deco(fn):
        REGISTRY[name] = dict(fn=fn, group=group, kind=kind, loudness=loudness, loop=loop, volume=volume, note=note)
        return fn
    return deco


# ===================================================================== building blocks
def noise(color, d):
    return {'white': S.white, 'pink': S.pink, 'brown': S.brown}[color](d)


def whoosh(d, f0=300, f1=2400, f2=700, q=1.6, peak=0.55, pan=(-0.5, 0.5), color='pink', power=1.3):
    n = noise(color, d)
    fc = S.pts(d, [(0, f0), (d * peak, f1), (d, f2)], 'exp')
    y = S.sweep(n, fc, q, 'bp')
    e = S.pts(d, [(0, 0), (d * peak, 1), (d, 0)]) ** power
    return st(y * e, S.line(d, pan[0], pan[1]))


def thump(d=0.35, f0=120, f1=40, decay=0.11, click=0.3, drive=1.6):
    t = secs(d)
    f = f1 + (f0 - f1) * np.exp(-t / 0.045)
    y = S.sine(f, d) * S.env_ad(d, 0.0008, decay)
    y += click * S.hp(S.white(d), 2500) * np.exp(-t / 0.003)
    return S.sat(y, drive)


def boom(d=1.6, f0=70, f1=26, decay=0.55, drive=2.0):
    t = secs(d)
    f = f1 + (f0 - f1) * np.exp(-t / 0.12)
    y = S.sine(f, d) * S.env_ad(d, 0.004, decay)
    y += 0.5 * S.lp(S.brown(d), 120) * S.env_ad(d, 0.002, decay * 0.6)
    return S.sat(y, drive)


def fireburst(d=0.5, f0=500, f1=2600, f2=700, crackle_rate=90):
    t = secs(d)
    body = S.sweep(S.pink(d), S.pts(d, [(0, f0), (0.05, f1), (d, f2)], 'exp'), 0.8, 'bp')
    flutter = 0.7 + 0.3 * np.sin(2 * np.pi * (14 + 10 * t) * t)
    e = S.pts(d, [(0, 0), (0.012, 1), (d, 0)]) ** 1.4
    cr = S.crackle(d, crackle_rate, 0.0025, 1800, 9000, rate_curve=np.exp(-t / (d * 0.5)))
    return body * flutter * e * 1.2 + cr * 0.8


def roar(d, c0=300, c1=4000, flutter=(10, 28), power=1.6):
    t = secs(d)
    x = S.sweep(S.brown(d) * 0.7 + S.pink(d) * 0.3, S.expo(d, c0, c1), 0.9, 'lp')
    fl = np.cumsum(np.interp(t, [0, d], flutter)) / SR
    am = 0.72 + 0.28 * np.sin(2 * np.pi * fl)
    return x * am * S.swell(d, power)


def glass(d, rate, f_lo=2200, f_hi=7000, decay=(0.08, 0.35), rate_curve=None, seed=None):
    """A spray of tiny glass / ice bells at random times."""
    if seed is not None:
        S.seed(seed)
    out = np.zeros(ns(d) + ns(0.6))
    n = ns(d)
    r = np.full(n, rate) if rate_curve is None else rate_curve * rate
    times = np.where(S.RNG.random(n) < r / SR)[0]
    for i in times:
        f = np.exp(S.RNG.uniform(np.log(f_lo), np.log(f_hi)))
        dec = S.RNG.uniform(*decay)
        b = S.bell(f, dec * 3, partials=((1, 1, 1), (2.32, .4, .6), (4.25, .2, .35)), decay=dec) * S.RNG.uniform(0.2, 1.0)
        out[i:i + len(b)] += b[:len(out) - i]
    return out


def crystal_chord(freqs, d=1.6, decay=0.9, shimmer=0.004):
    out = np.zeros(ns(d))
    for f in freqs:
        for k in range(3):
            out += S.bell(f * (1 + S.RNG.uniform(-shimmer, shimmer)), d,
                          partials=((1, 1, 1), (2.76, .35, .5), (5.4, .18, .3), (8.93, .08, .2)), decay=decay) / 3
    return out


def zap(d=0.12, f0=3200, f1=160, drive=4.0):
    t = secs(d)
    f = f1 + (f0 - f1) * np.exp(-t / (d * 0.18))
    y = S.saw(f, d) * 0.6 + S.square(f * 0.5, d, 0.3) * 0.4
    y = S.sat(y, drive) * S.env_ad(d, 0.0005, d * 0.35)
    return S.hp(y, 120)


def buzz(d, f=110, am=13, drive=3.0):
    t = secs(d)
    y = S.square(f, d, 0.35) + S.saw(f * 2.01, d) * 0.5
    y *= 0.55 + 0.45 * np.sin(2 * np.pi * am * t + 0.4 * np.sin(2 * np.pi * 3.1 * t)) ** 2
    return S.bandpass(S.sat(y, drive), 90, 6000)


def spark_crack(d=0.25):
    t = secs(d)
    crack = S.hp(S.white(d), 2500) * np.exp(-t / 0.006) * 1.2
    body = S.bandpass(S.white(d), 600, 5000) * np.exp(-t / 0.035) * 0.6
    z = np.zeros(len(t))
    zz = zap(0.1, 4500, 300)[:len(t)]
    z[:len(zz)] = zz
    return crack + body + z * 0.5


def thunder(d=2.6, crack=1.0):
    t = secs(d)
    c = S.hp(S.white(d), 1800) * np.exp(-t / 0.012) * crack
    c += S.bandpass(S.white(d), 400, 4000) * np.exp(-t / 0.08) * 0.5
    fl = S.lp(S.white(d), 4.0)
    fl /= np.max(np.abs(fl)) + 1e-9
    rumble = S.lp(S.brown(d), 260) * np.exp(-t / 0.8) * (0.6 + 0.4 * fl)
    return c + rumble * 1.1


def riser_tone(d, f0, f1, kind='saw', vib=(5, 12), q=3.0, cut=(400, 5000)):
    t = secs(d)
    fr = S.expo(d, f0, f1) * 2 ** (0.25 * np.sin(2 * np.pi * np.cumsum(np.interp(t, [0, d], vib)) / SR) / 12)
    x = (S.saw(fr, d) + S.saw(fr * 1.008, d)) if kind == 'saw' else S.square(fr, d, 0.3)
    return S.sweep(x, S.expo(d, *cut), q, 'lp') * S.swell(d, 1.8)


def reverse_swell(x, d):
    """The reversed reverb tail of a sound, d seconds long, peaking at its end."""
    w = S.reverb(x, wet=1.0, rt=d * 1.4, dry=0.0)
    r = S.rev(w)
    return r[-ns(d):] if len(r) >= ns(d) else r


def auto_pan(x, rate_curve):
    t = np.arange(len(x)) / SR
    ph = np.cumsum(np.resize(rate_curve, len(x))) / SR
    return st(x, 0.85 * np.sin(2 * np.pi * ph))


def put_at(c, x, at, gain=1.0, pan=0.0):
    c.put(x, at, gain, pan)


def space(x, wet=0.22, rt=1.3, predelay=0.012, damp=6500, width=1.0):
    return S.reverb(x, wet=wet, rt=rt, predelay=predelay, damp=damp, width=width)


def loopify(x, d, xfade=0.35):
    """Seamless loop: render d + xfade seconds, fold the extra onto the start."""
    x2 = st(x)
    n, k = ns(d), ns(xfade)
    out = x2[:n].copy()
    w = np.linspace(0, 1, k)[:, None]
    out[:k] = x2[:k] * w + x2[n:n + k] * (1 - w)
    return out


# ===================================================================== ULTIMATE WIND-UPS (per wizard)
@sound('UltStart_Blaise', kind='ultimate', loudness=-14.5, note='火男 布萊茲：太鼓連擊＋點火＋烈焰咆哮的蓄力，0.8 秒時在發射前收束')
def ult_blaise():
    S.seed(101)
    c = Canvas(1.8)
    # the pose: a taiko flam and a burst of flame
    put_at(c, I.taiko(60, 1.0, 1.4, 0.7), 0.000, 1.0, -0.05)
    put_at(c, I.taiko(74, 0.75, 1.1, 0.6), 0.095, 0.75, 0.1)
    put_at(c, fireburst(0.55, 450, 2800, 650, 120), 0.0, 0.75, -0.15)
    put_at(c, thump(0.5, 140, 45, 0.16, 0.5, 2.2), 0.0, 0.55)
    # gathering power: a roar that opens up, a growling synth, crackles thickening
    d = WINDUP - 0.12
    put_at(c, roar(d, 260, 4200, (9, 30), 1.5), 0.12, 0.65)
    gr_f = S.expo(d, 55, 116)
    growl = S.sweep(S.sat(S.saw(gr_f, d) + S.saw(gr_f * 1.012, d) + 0.5 * S.square(gr_f * 0.5, d), 2.5),
                    S.expo(d, 180, 2600), 2.2, 'lp') * S.swell(d, 2.0)
    put_at(c, growl, 0.12, 0.42)
    put_at(c, S.crackle(d, 160, 0.002, 2000, 9500, rate_curve=S.swell(d, 1.2)), 0.12, 0.55, 0.2)
    # an accelerating drum roll into the release
    for k, at in enumerate((0.30, 0.43, 0.53, 0.60, 0.655, 0.70, 0.735, 0.765, 0.785)):
        put_at(c, I.taiko(68 + k * 2.5, 0.45 + 0.07 * k, 0.6, 0.55), at, 0.55, (-0.3, 0.3)[k % 2])
    # suck-in: the reversed tail of a burst, ending exactly at the launch
    sw = reverse_swell(fireburst(0.4, 800, 3000, 900, 60), 0.32)
    put_at(c, sw, WINDUP - len(sw) / SR, 0.9)
    # after the launch: embers
    put_at(c, S.crackle(0.9, 50, 0.002, 2500, 9000, rate_curve=np.exp(-secs(0.9) / 0.35)), WINDUP, 0.35, 0.1)
    return space(c.out(), 0.22, 1.5, 0.015, 7000)


@sound('UltStart_Neve', kind='ultimate', loudness=-15.5, note='冰女 妮芙：水晶「叮——」、像音樂盒的上行琶音越轉越快、冰晶與霜氣聚集')
def ult_neve():
    S.seed(202)
    c = Canvas(2.0)
    # the pose: a crystal chord in E (E6 B6 E7 G#7) over a soft frozen thump, a frosty breath
    put_at(c, crystal_chord([1318.5, 1975.5, 2637.0, 3322.4], 1.8, 0.95), 0.0, 0.55)
    put_at(c, thump(0.6, 95, 38, 0.25, 0.1, 1.3), 0.0, 0.6)
    frost = S.hp(S.pink(0.9), 3500) * S.pts(0.9, [(0, 0), (0.05, 1), (0.9, 0)]) ** 1.5
    put_at(c, st(frost, S.line(0.9, -0.4, 0.4)), 0.0, 0.25)
    # a sleepy music-box arpeggio that spins up (E major), alternating sides
    notes = [76, 80, 83, 88, 92, 95, 100, 104]
    for k, m in enumerate(notes):
        at = 0.10 + 0.62 * (1 - (1 - k / (len(notes) - 1)) ** 1.6)
        put_at(c, I.musicbox(m, 0.6, 0.55 + 0.05 * k), at, 0.5, (-0.45, 0.45)[k % 2])
    # a shimmering pad swells, the cold drone below, ice crystals gather
    d = WINDUP - 0.08
    t = secs(d)
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(np.interp(t, [0, d], [4, 22])) / SR)
    pad = sum(S.sine(f * (1 + S.RNG.uniform(-0.003, 0.003)), d) for f in (659.3, 987.8, 1318.5, 1979.0, 2637.0))
    put_at(c, st(pad * trem * S.swell(d, 2.2) * 0.25, 0), 0.08, 0.6)
    put_at(c, S.sine(82.4, d) * S.swell(d, 1.5) * 0.5 + S.sine(123.5, d) * S.swell(d, 2) * 0.2, 0.08, 0.5)
    put_at(c, st(glass(d, 70, 2500, 8000, (0.06, 0.25), S.swell(d, 1.3), 7), 0.0), 0.08, 0.45)
    # reversed crystal swell into the launch
    sw = reverse_swell(crystal_chord([1975.5, 2637.0, 3951.1], 0.8, 0.5), 0.3)
    put_at(c, sw, WINDUP - len(sw) / SR, 0.8)
    # snow settling after the launch
    put_at(c, glass(0.9, 18, 3000, 9000, (0.05, 0.2), np.exp(-secs(0.9) / 0.4), 9), WINDUP, 0.35, 0.2)
    return space(c.out(), 0.34, 2.2, 0.02, 9000)


@sound('UltStart_Gale', kind='ultimate', loudness=-15.0, note='風男 蓋爾：拔刀「鏘——」、低沉的鼓、旋轉加速的風、陰冷的低鳴；安靜但很銳利')
def ult_gale():
    S.seed(303)
    c = Canvas(1.7)
    # the pose: a blade drawn (scrape + ring), a muted low drum, a sharp gust
    scrape_d = 0.2
    sc = S.sweep(S.white(scrape_d), S.expo(scrape_d, 1800, 7500), 6.0, 'bp')
    sc *= (0.55 + 0.45 * np.sin(2 * np.pi * 70 * secs(scrape_d)) ** 2) * S.pts(scrape_d, [(0, 0), (0.02, 1), (0.2, 0.15)])
    put_at(c, st(sc, S.line(scrape_d, 0.6, 0.1)), 0.0, 0.7)
    ring_d = 1.4
    t = secs(ring_d)
    ring = sum(a * S.sine(f * 2 ** (0.03 * np.sin(2 * np.pi * 5.5 * t) / 12), ring_d) * np.exp(-t / dec)
               for f, a, dec in ((2349, 1.0, 1.0), (3720, 0.6, 0.8), (5180, 0.45, 0.6), (6890, 0.25, 0.45), (1175, 0.2, 0.9)))
    put_at(c, ring * np.minimum(t / 0.004, 1) * 0.35, 0.07, 0.8, 0.15)
    put_at(c, I.taiko(52, 0.8, 1.2, 0.2), 0.0, 0.7)
    put_at(c, whoosh(0.28, 600, 4200, 900, 1.8, 0.3, (-0.8, 0.6), 'white', 1.2), 0.0, 0.55)
    # the wind spirals up (band-pass centre circling and rising, panning faster and faster)
    d = WINDUP - 0.05
    tt = secs(d)
    centre = S.expo(d, 350, 1700) * (1 + 0.25 * np.sin(2 * np.pi * np.cumsum(np.interp(tt, [0, d], [2, 9])) / SR))
    wind = S.sweep(S.pink(d), centre, 3.5, 'bp') * S.swell(d, 1.4)
    put_at(c, auto_pan(wind, np.interp(tt, [0, d], [1.2, 7.0])), 0.05, 0.75)
    # a cold drone a minor second apart, felt more than heard
    drone = S.lp(S.saw(41.2, d) + S.saw(43.65, d), 260) * S.swell(d, 1.2)
    put_at(c, drone, 0.05, 0.4)
    # shuriken whirr: ticks that speed up
    tick_times = np.cumsum(np.interp(np.arange(28), [0, 27], [0.07, 0.012]))
    for k, at in enumerate(tick_times):
        if 0.12 + at < WINDUP - 0.03:
            tk = S.bell(3200 + 120 * (k % 3), 0.05, partials=((1, 1, 1), (1.7, .5, .6)), decay=0.012)
            put_at(c, tk, 0.12 + at, 0.12 + 0.012 * k, (-0.5, 0.5)[k % 2])
    # a tight reversed whoosh into the dash
    rw = S.rev(whoosh(0.22, 3000, 1200, 500, 1.4, 0.15, (0.4, -0.4), 'pink', 1.0))
    put_at(c, rw, WINDUP - len(rw) / SR, 0.8)
    return space(c.out(), 0.18, 1.1, 0.008, 8000)


@sound('UltStart_Volta', kind='ultimate', loudness=-14.5, note='雷女 沃爾妲：電光「劈啪」＋俏皮的上揚口哨、越來越密的電擊連打、充電的嗡鳴、熱鬧的琶音')
def ult_volta():
    S.seed(404)
    c = Canvas(1.8)
    # the pose: a spark crack, a party clap, a cheeky rising whoop
    put_at(c, spark_crack(0.3), 0.0, 0.85, -0.1)
    put_at(c, I.clap(1.0), 0.005, 0.7, 0.15)
    wd = 0.38
    wt = secs(wd)
    whoop = S.fm(S.expo(wd, 340, 1450) * 2 ** (0.4 * np.sin(2 * np.pi * 9 * wt) / 12), 2.0, 0.6, wd)
    put_at(c, whoop * S.pts(wd, [(0, 0), (0.03, 1), (0.3, 0.8), (wd, 0)]) * 0.45, 0.03, 0.8, 0.2)
    # the charge: a whine that climbs with growing vibrato, an electric buzz underneath
    d = WINDUP - 0.08
    put_at(c, riser_tone(d, 190, 1600, 'saw', (5, 13), 3.5, (500, 7000)), 0.08, 0.38)
    put_at(c, buzz(d, 96, 15, 3.5) * S.swell(d, 1.6), 0.08, 0.32)
    put_at(c, S.crackle(d, 180, 0.0015, 2500, 11000, rate_curve=S.swell(d, 1.1)), 0.08, 0.5, -0.15)
    # a festive roll of zaps, left / right, faster and faster
    times = [0.26, 0.37, 0.46, 0.53, 0.585, 0.63, 0.665, 0.695, 0.72, 0.742, 0.762, 0.78, 0.795]
    for k, at in enumerate(times):
        put_at(c, zap(0.07, 2600 + 160 * k, 220, 4.0), at, 0.35 + 0.035 * k, (-0.55, 0.55)[k % 2])
    # a bright arpeggio running up (C major pentatonic)
    for k, m in enumerate((72, 74, 76, 79, 81, 84, 86, 88, 91)):
        put_at(c, I.synthpluck(m, 0.12, 0.7, 1.2), 0.14 + k * 0.068, 0.32, (k / 8.0 - 0.5))
    # a reversed thunder crack swelling into the launch
    sw = reverse_swell(thunder(0.6, 1.2)[:ns(0.25)], 0.3)
    put_at(c, sw, WINDUP - len(sw) / SR, 0.9)
    put_at(c, S.crackle(0.8, 60, 0.0015, 3000, 11000, rate_curve=np.exp(-secs(0.8) / 0.3)), WINDUP, 0.4, 0.15)
    return space(c.out(), 0.2, 1.3, 0.01, 8500)


@sound('UltCutIn', group='UI', kind='ui', loudness=-16.0, note='立繪滑入：從左邊掃進來的「咻」＋閃亮的「鏘～」')
def ult_cutin():
    S.seed(505)
    c = Canvas(1.4)
    # the swish travels from the left (the portrait slides in from the left)
    d = 0.18
    sw = S.sweep(S.white(d), S.expo(d, 900, 9500), 2.2, 'bp') * S.pts(d, [(0, 0), (0.012, 1), (d, 0.0)]) ** 0.8
    put_at(c, st(sw, S.line(d, -0.9, 0.0)), 0.0, 0.9)
    put_at(c, thump(0.35, 160, 60, 0.07, 0.4, 1.6), 0.03, 0.6)
    # the shine: a bright chord (C6 G6 E7 C8) of FM bells, quickly shimmering
    for k, m in enumerate((84, 91, 100, 108)):
        f = S.mtof(m)
        dd = 1.0
        b = S.fm(f, 3.5, 1.6 * np.exp(-secs(dd) / 0.15), dd) * S.env_ad(dd, 0.002, 0.45 - 0.07 * k)
        put_at(c, b * (0.5 - 0.08 * k), 0.06 + 0.012 * k, 0.6, (k - 1.5) * 0.25)
    put_at(c, st(glass(0.6, 40, 4000, 10000, (0.04, 0.15), np.exp(-secs(0.6) / 0.25), 13), 0.1), 0.08, 0.35)
    return space(c.out(), 0.3, 1.5, 0.01, 10000)


# ===================================================================== CHARGE (element layer under the wind-up)
@sound('Charge_Fire', kind='ultimate', loudness=-20.0, note='火的蓄力層：越燒越旺的火聲')
def charge_fire():
    S.seed(11)
    d = WINDUP + 0.06
    x = roar(d, 250, 3500, (8, 24), 1.4) + S.crackle(d, 120, 0.002, 1800, 9000, rate_curve=S.swell(d, 1.3)) * 0.8
    return space(S.fade(st(x, 0), 0.02, 0.06), 0.15, 1.0)


@sound('Charge_Ice', kind='ultimate', loudness=-21.0, note='冰的蓄力層：冰晶聚集、霜氣')
def charge_ice():
    S.seed(12)
    d = WINDUP + 0.06
    t = secs(d)
    sh = sum(S.sine(f * (1 + S.RNG.uniform(-.004, .004)), d) for f in (1046.5, 1568.0, 2093.0, 3136.0))
    sh *= (0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(np.interp(t, [0, d], [6, 20])) / SR)) * S.swell(d, 1.8) * 0.2
    gl = glass(d, 90, 2600, 9000, (0.05, 0.2), S.swell(d, 1.2), 3)[:ns(d)]
    fr = S.hp(S.pink(d), 4000) * S.swell(d, 1.5) * 0.4
    return space(S.fade(st(sh + gl * 0.7 + fr, 0), 0.02, 0.06), 0.3, 1.8, 0.02, 9000)


@sound('Charge_Wind', kind='ultimate', loudness=-20.0, note='風的蓄力層：旋轉加速的風')
def charge_wind():
    S.seed(13)
    d = WINDUP + 0.06
    t = secs(d)
    w = S.sweep(S.pink(d), S.expo(d, 300, 2400), 3.0, 'bp') * S.swell(d, 1.3)
    return space(S.fade(auto_pan(w, np.interp(t, [0, d], [1.5, 8])), 0.02, 0.06), 0.15, 1.0)


@sound('Charge_Lightning', kind='ultimate', loudness=-20.5, note='雷的蓄力層：充電的嗡鳴與電花')
def charge_lightning():
    S.seed(14)
    d = WINDUP + 0.06
    b = S.sweep(buzz(d, S.expo(d, 80, 230), 18, 3.0), S.expo(d, 500, 5000), 3.0, 'bp') * S.swell(d, 1.5)
    cr = S.crackle(d, 150, 0.0015, 2500, 11000, rate_curve=S.swell(d, 1.0))
    return space(S.fade(st(b * 0.8 + cr * 0.7, 0), 0.02, 0.06), 0.15, 1.0)


# ===================================================================== SUPER (the launch)
@sound('Super_Fire', kind='ultimate', loudness=-14.0, note='火大招發射：沉重的爆音＋巨大的火焰呼嘯')
def super_fire():
    S.seed(21)
    c = Canvas(2.2)
    put_at(c, boom(1.8, 75, 26, 0.6, 2.4), 0.0, 0.9)
    put_at(c, thump(0.4, 180, 50, 0.1, 0.8, 2.2), 0.0, 0.6)
    put_at(c, fireburst(1.1, 300, 3200, 400, 150), 0.0, 0.9)
    put_at(c, whoosh(1.0, 1800, 2600, 300, 0.9, 0.12, (-0.2, 0.6), 'brown', 1.1), 0.02, 0.8)
    put_at(c, S.crackle(1.6, 90, 0.002, 2000, 9000, rate_curve=np.exp(-secs(1.6) / 0.6)), 0.05, 0.45, 0.2)
    return space(c.out(), 0.25, 1.8, 0.02, 6000)


@sound('Super_Ice', kind='ultimate', loudness=-15.0, note='冰大招發射：冰晶爆開的閃亮聲＋深沉的轟')
def super_ice():
    S.seed(22)
    c = Canvas(2.4)
    put_at(c, boom(1.6, 65, 28, 0.5, 1.8), 0.0, 0.8)
    put_at(c, st(glass(0.12, 500, 1800, 9000, (0.12, 0.6), None, 5), 0), 0.0, 0.8)
    put_at(c, crystal_chord([1318.5, 1661.2, 1975.5, 2637.0, 3322.4], 2.0, 1.1), 0.0, 0.45)
    put_at(c, whoosh(0.7, 3000, 6000, 1500, 1.2, 0.08, (-0.4, 0.4), 'white', 1.2), 0.0, 0.45)
    put_at(c, st(glass(1.6, 30, 3000, 9500, (0.04, 0.2), np.exp(-secs(1.6) / 0.5), 6), 0), 0.15, 0.4)
    return space(c.out(), 0.35, 2.4, 0.02, 10000)


@sound('Super_Wind', kind='ultimate', loudness=-14.5, note='風大招發射：掠過的強風（左到右）＋低鳴與哨音')
def super_wind():
    S.seed(23)
    c = Canvas(2.0)
    d = 1.2
    w = S.sweep(S.pink(d), S.pts(d, [(0, 500), (0.2, 3000), (d, 350)], 'exp'), 1.4, 'bp') * S.pts(d, [(0, 0), (0.12, 1), (d, 0)]) ** 1.2
    put_at(c, st(w, S.line(d, -0.9, 0.9)), 0.0, 1.0)
    put_at(c, boom(1.2, 60, 32, 0.35, 1.6), 0.0, 0.6)
    wh_t = secs(d)
    whistle = (S.sine(S.expo(d, 1900, 1200), d) + 0.5 * S.sine(S.expo(d, 2850, 1800), d)) * S.pts(d, [(0, 0), (0.1, 1), (d, 0)]) ** 2
    put_at(c, st(whistle * 0.15, S.line(d, -0.6, 0.6)), 0.0, 0.8)
    put_at(c, S.lp(S.brown(1.3), 200) * S.env_ad(1.3, 0.05, 0.4), 0.0, 0.5)
    return space(c.out(), 0.2, 1.4, 0.015, 8000)


@sound('Super_Lightning', kind='ultimate', loudness=-14.0, note='雷大招發射：落雷的爆裂＋翻滾的雷聲＋電流')
def super_lightning():
    S.seed(24)
    c = Canvas(3.0)
    put_at(c, thunder(2.6, 1.3), 0.0, 1.0)
    put_at(c, zap(0.2, 5000, 120, 5.0), 0.0, 0.8)
    put_at(c, buzz(1.0, 110, 21, 3.0) * S.env_ad(1.0, 0.002, 0.25), 0.02, 0.4, 0.2)
    put_at(c, S.crackle(1.2, 120, 0.0015, 2500, 11000, rate_curve=np.exp(-secs(1.2) / 0.35)), 0.0, 0.5, -0.2)
    return space(c.out(), 0.25, 2.0, 0.02, 7000)


# ===================================================================== CAST (basic attacks, instant)
@sound('Cast_Fire', kind='cast', loudness=-18.0, note='火球普攻：「噗呼」一團火＋小小的爆音')
def cast_fire():
    S.seed(31)
    c = Canvas(0.7)
    put_at(c, thump(0.25, 150, 60, 0.05, 0.4, 1.8), 0.0, 0.6)
    put_at(c, fireburst(0.42, 700, 3000, 900, 70), 0.0, 0.85, 0.1)
    put_at(c, whoosh(0.3, 1200, 2000, 500, 1.0, 0.1, (0.0, 0.5), 'pink', 1.0), 0.01, 0.4)
    return space(c.out(), 0.12, 0.8)


@sound('Cast_Ice', kind='cast', loudness=-19.0, note='冰球普攻：清脆的「叮」＋霜氣「咻」')
def cast_ice():
    S.seed(32)
    c = Canvas(0.8)
    put_at(c, crystal_chord([2093.0, 3136.0], 0.6, 0.3), 0.0, 0.5, 0.1)
    put_at(c, whoosh(0.3, 3000, 7000, 2500, 1.4, 0.15, (-0.2, 0.5), 'white', 1.3), 0.0, 0.55)
    put_at(c, thump(0.2, 130, 70, 0.04, 0.2, 1.4), 0.0, 0.35)
    put_at(c, st(glass(0.2, 60, 3500, 9000, (0.04, 0.12), None, 4), 0.2), 0.02, 0.35)
    return space(c.out(), 0.2, 1.4, 0.015, 9500)


@sound('Cast_Wind', kind='cast', loudness=-19.0, note='風球普攻：輕快的「咻」＋一點哨音')
def cast_wind():
    S.seed(33)
    c = Canvas(0.6)
    put_at(c, whoosh(0.3, 500, 3200, 1100, 1.8, 0.35, (-0.5, 0.6), 'pink', 1.3), 0.0, 1.0)
    d = 0.25
    put_at(c, S.sine(S.expo(d, 1700, 2700), d) * S.pts(d, [(0, 0), (0.05, 1), (d, 0)]) ** 2 * 0.12, 0.02, 0.8, 0.3)
    return space(c.out(), 0.12, 0.8)


@sound('Cast_Lightning', kind='cast', loudness=-18.5, note='雷球普攻：「滋—啪」電擊＋短促的電流')
def cast_lightning():
    S.seed(34)
    c = Canvas(0.6)
    put_at(c, zap(0.12, 3200, 260, 4.0), 0.0, 0.9)
    put_at(c, S.hp(S.white(0.05), 3000) * np.exp(-secs(0.05) / 0.006), 0.0, 0.6)
    put_at(c, buzz(0.25, 140, 30, 3.0) * S.env_ad(0.25, 0.002, 0.07), 0.02, 0.35, 0.2)
    put_at(c, S.crackle(0.3, 90, 0.0012, 3000, 11000, rate_curve=np.exp(-secs(0.3) / 0.1)), 0.0, 0.4, -0.2)
    return space(c.out(), 0.12, 0.8)


# ===================================================================== IMPACT
@sound('Impact_Fire', kind='impact', loudness=-16.5, note='火球命中：爆炸＋餘燼劈啪')
def impact_fire():
    S.seed(41)
    c = Canvas(1.2)
    put_at(c, thump(0.5, 140, 42, 0.13, 0.6, 2.2), 0.0, 0.8)
    t = secs(0.6)
    blast = S.sweep(S.pink(0.6), S.expo(0.6, 7000, 300), 0.8, 'lp') * np.exp(-t / 0.13)
    put_at(c, blast, 0.0, 0.9)
    put_at(c, S.crackle(0.9, 70, 0.002, 1800, 9000, rate_curve=np.exp(-secs(0.9) / 0.3)), 0.03, 0.55, 0.2)
    return space(c.out(), 0.18, 1.2, 0.012, 6500)


@sound('Impact_Ice', kind='impact', loudness=-17.5, note='冰球命中：冰晶碎裂')
def impact_ice():
    S.seed(42)
    c = Canvas(1.2)
    put_at(c, thump(0.3, 140, 60, 0.06, 0.3, 1.6), 0.0, 0.5)
    t = secs(0.08)
    put_at(c, S.hp(S.white(0.08), 2500) * np.exp(-t / 0.012), 0.0, 0.6)
    put_at(c, st(glass(0.09, 400, 2000, 9500, (0.08, 0.45), None, 8), 0), 0.0, 0.9)
    put_at(c, st(glass(0.5, 25, 3000, 9000, (0.04, 0.15), np.exp(-secs(0.5) / 0.15), 18), 0), 0.08, 0.4)
    return space(c.out(), 0.25, 1.6, 0.015, 9500)


@sound('Impact_Wind', kind='impact', loudness=-18.0, note='風球命中：「噗」的一陣風壓＋打旋')
def impact_wind():
    S.seed(43)
    c = Canvas(1.0)
    put_at(c, thump(0.35, 100, 50, 0.08, 0.15, 1.3), 0.0, 0.7)
    put_at(c, whoosh(0.5, 2600, 1200, 300, 1.2, 0.08, (0.3, -0.3), 'pink', 1.0), 0.0, 1.0)
    t = secs(0.6)
    swirl = S.sweep(S.pink(0.6), 700 * (1 + 0.4 * np.sin(2 * np.pi * 5 * t)), 4.0, 'bp') * np.exp(-t / 0.18)
    put_at(c, auto_pan(swirl, np.full(len(t), 4.0)), 0.04, 0.45)
    return space(c.out(), 0.15, 1.0)


@sound('Impact_Lightning', kind='impact', loudness=-17.0, note='雷球命中：「啪滋」爆裂＋電流餘音')
def impact_lightning():
    S.seed(44)
    c = Canvas(1.0)
    put_at(c, spark_crack(0.3), 0.0, 1.0)
    put_at(c, thump(0.3, 160, 70, 0.05, 0.2, 1.8), 0.0, 0.5)
    put_at(c, buzz(0.45, 100, 24, 3.5) * S.env_ad(0.45, 0.002, 0.12), 0.01, 0.45, 0.2)
    put_at(c, S.crackle(0.6, 90, 0.0012, 3000, 11000, rate_curve=np.exp(-secs(0.6) / 0.18)), 0.0, 0.45, -0.2)
    return space(c.out(), 0.15, 1.0)


@sound('IceSplit', kind='impact', loudness=-20.0, note='冰晶分裂：一串往上的「叮叮叮」')
def ice_split():
    S.seed(45)
    c = Canvas(0.9)
    for k, f in enumerate((2637.0, 3136.0, 3951.1, 4698.6)):
        put_at(c, S.bell(f, 0.5, partials=((1, 1, 1), (2.76, .3, .5), (5.4, .12, .3)), decay=0.18), k * 0.045, 0.5, (k - 1.5) * 0.35)
    put_at(c, S.hp(S.white(0.05), 3000) * np.exp(-secs(0.05) / 0.01), 0.0, 0.3)
    return space(c.out(), 0.25, 1.3, 0.01, 10000)


@sound('Ricochet', kind='impact', loudness=-20.0, note='反彈：有彈性的「啵嚶」＋小風聲')
def ricochet():
    S.seed(46)
    c = Canvas(0.6)
    d = 0.3
    t = secs(d)
    f = 520 * (1 + 0.45 * np.exp(-t / 0.08) * np.sin(2 * np.pi * 18 * t)) * (1 + 0.6 * np.exp(-t / 0.02))
    put_at(c, S.sine(f, d) * S.env_ad(d, 0.002, 0.09) * 0.6, 0.0, 0.8)
    put_at(c, whoosh(0.22, 1500, 3500, 900, 1.6, 0.2, (-0.3, 0.3), 'pink', 1.2), 0.0, 0.4)
    put_at(c, thump(0.15, 220, 120, 0.03, 0.4, 1.3), 0.0, 0.35)
    return space(c.out(), 0.12, 0.8)


# ===================================================================== SECONDARY (round 14)
# 二段: the second press while a basic shot is flying.  Each starts with the same small
# 'seal breaks' snap (so the ear learns 'that was my second press'), then the element's
# own payload.  Played by Multicast_HitFX (fire / ice / lightning) and
# Multicast_WindRedirectFX (wind) on every machine.
def trigger_snap(pitch=1.0):
    d = 0.07
    t = secs(d)
    tick = S.hp(S.white(d), 4000) * np.exp(-t / 0.0025)
    chirp = S.sine(S.expo(d, 3400 * pitch, 1300 * pitch), d) * np.exp(-t / 0.012) * 0.5
    sparkle = S.bell(5200 * pitch, d, partials=((1, 1, 1), (2.76, .3, .5)), decay=0.03) * 0.25
    return tick * 0.9 + chirp + sparkle


@sound('Secondary_Fire', kind='impact', loudness=-15.5, note='火球二段「引爆」：「喀」一聲解開，接著比命中更大的「轟——」＋往兩邊翻滾的火焰＋餘燼')
def secondary_fire():
    S.seed(81)
    c = Canvas(1.8)
    put_at(c, trigger_snap(0.9), 0.0, 0.6)
    put_at(c, thump(0.7, 130, 36, 0.2, 0.5, 2.6), 0.01, 1.0)
    put_at(c, boom(1.4, 60, 24, 0.5, 2.0), 0.01, 0.55)
    t = secs(0.9)
    put_at(c, S.sweep(S.pink(0.9), S.expo(0.9, 9000, 220), 0.8, 'lp') * np.exp(-t / 0.2), 0.01, 1.0)
    put_at(c, fireburst(0.8, 400, 2800, 500, 110), 0.02, 0.75, -0.45)
    put_at(c, fireburst(0.8, 450, 2600, 520, 110), 0.035, 0.7, 0.45)
    put_at(c, S.crackle(1.4, 80, 0.002, 1600, 9000, rate_curve=np.exp(-secs(1.4) / 0.45)), 0.06, 0.55)
    return space(c.out(), 0.22, 1.6, 0.015, 6000)


@sound('Secondary_Ice', kind='impact', loudness=-17.0, note='冰球二段「分裂」：冰殼「喀啦」裂開＋閃亮的和弦「鈴」＋碎片往左右飛散的「咻咻」')
def secondary_ice():
    S.seed(82)
    c = Canvas(1.4)
    put_at(c, trigger_snap(1.25), 0.0, 0.55)
    put_at(c, S.hp(S.white(0.05), 3000) * np.exp(-secs(0.05) / 0.004), 0.0, 0.8)
    put_at(c, st(glass(0.06, 500, 2500, 9500, (0.05, 0.25), None, 9), 0), 0.0, 0.8)
    put_at(c, crystal_chord([2637.0, 3520.0, 4698.6], 0.9, 0.35), 0.005, 0.45)
    put_at(c, thump(0.25, 150, 70, 0.05, 0.2, 1.5), 0.0, 0.4)
    # the shards fly apart: a short 'tsing' falling in pitch as each one leaves, panned out
    for k, (at, pan) in enumerate(((0.03, -0.7), (0.065, 0.7), (0.1, -0.35), (0.135, 0.4))):
        d = 0.22
        t = secs(d)
        f0 = 5600 - 500 * k
        ting = S.sine(S.expo(d, f0, f0 * 0.62), d) * np.exp(-t / 0.05) * 0.35
        swish = S.sweep(S.white(d), S.expo(d, 7000, 2600), 2.0, 'bp') * S.pts(d, [(0, 0), (0.02, 1), (d, 0)]) ** 1.5 * 0.5
        put_at(c, ting + swish, at, 0.7, S.line(d, pan * 0.4, pan))
    put_at(c, st(glass(0.5, 30, 3500, 10000, (0.04, 0.14), np.exp(-secs(0.5) / 0.18), 19), 0), 0.12, 0.35)
    return space(c.out(), 0.25, 1.6, 0.015, 10000)


@sound('Secondary_Wind', kind='impact', loudness=-17.5, note='風球二段「轉向追蹤」：鎖定的「嗶啵！」＋急轉的「咻——」＋上揚的哨音')
def secondary_wind():
    S.seed(83)
    c = Canvas(1.0)
    put_at(c, trigger_snap(1.1), 0.0, 0.5)
    for at, f, d in ((0.0, 1760.0, 0.045), (0.05, 2637.0, 0.07)):
        blip = (S.sine(f, d) + 0.25 * S.lp(S.square(f, d, 0.5), 5000)) * S.env_adsr(d, 0.002, 0.02, 0.6, d * 0.4)
        put_at(c, blip, at, 0.3)
    put_at(c, whoosh(0.34, 500, 5000, 1400, 2.2, 0.3, (-0.75, 0.8), 'pink', 1.1), 0.03, 1.0)
    d = 0.32
    whistle = S.sine(S.expo(d, 900, 2400), d) * S.pts(d, [(0, 0), (0.12, 1), (d, 0)]) ** 2 * 0.12
    put_at(c, whistle, 0.04, 0.9, S.line(d, -0.5, 0.7))
    put_at(c, thump(0.2, 160, 80, 0.04, 0.1, 1.3), 0.03, 0.35)
    return space(c.out(), 0.15, 1.0)


@sound('Secondary_Lightning', kind='impact', loudness=-16.0, note='雷球二段「落雷」：往下劈的「滋——」＋落地的「轟啪」＋雷場通電的嗡聲（之後交給雷場的循環聲）')
def secondary_lightning():
    S.seed(84)
    c = Canvas(1.6)
    put_at(c, trigger_snap(1.0), 0.0, 0.5)
    put_at(c, zap(0.22, 6000, 120, 4.5), 0.0, 0.85)
    put_at(c, spark_crack(0.3), 0.06, 1.0)
    put_at(c, thump(0.45, 150, 40, 0.12, 0.6, 2.4), 0.06, 0.9)
    put_at(c, thunder(1.3, 0.6), 0.06, 0.45)
    d = 0.9
    hum = buzz(d, 110, 18, 3.5) * S.pts(d, [(0, 0), (0.08, 1), (0.3, 0.6), (d, 0)])
    put_at(c, hum, 0.1, 0.32, 0.15)
    put_at(c, S.crackle(0.8, 110, 0.0012, 3000, 11000, rate_curve=np.exp(-secs(0.8) / 0.25)), 0.08, 0.45, -0.2)
    return space(c.out(), 0.18, 1.3)


# ===================================================================== CHARACTER ACTIONS
@sound('Blink', kind='cast', loudness=-17.5, note='閃現：電光一閃的「咻—叮」（雷女最喜歡的特效）')
def blink():
    S.seed(51)
    c = Canvas(0.9)
    d = 0.14
    put_at(c, S.fm(S.expo(d, 420, 2600), 1.5, 0.8, d) * S.pts(d, [(0, 0), (0.01, 1), (d, 0.2)]) * 0.5, 0.0, 0.8)
    put_at(c, S.hp(S.white(0.06), 3500) * np.exp(-secs(0.06) / 0.01), 0.0, 0.5)
    put_at(c, zap(0.06, 4000, 900, 3.0), 0.12, 0.35)
    put_at(c, crystal_chord([3136.0, 4186.0], 0.6, 0.25), 0.12, 0.35, 0.15)
    put_at(c, st(S.crackle(0.35, 120, 0.001, 4000, 12000, rate_curve=np.exp(-secs(0.35) / 0.1)), 0), 0.1, 0.35)
    return space(c.out(), 0.2, 1.1, 0.01, 10000)


@sound('Block', kind='impact', loudness=-19.0, note='格擋：護盾的「噹」')
def block():
    S.seed(52)
    c = Canvas(0.8)
    d = 0.6
    t = secs(d)
    metal = sum(a * S.sine(f, d) * np.exp(-t / dec) for f, a, dec in ((520, 1, 0.25), (1310, 0.6, 0.15), (2160, 0.35, 0.1), (3380, 0.2, 0.06)))
    put_at(c, metal * 0.4, 0.0, 0.8)
    put_at(c, thump(0.3, 110, 60, 0.06, 0.4, 1.5), 0.0, 0.6)
    return space(c.out(), 0.18, 1.0)


@sound('Footstep', kind='movement', loudness=-27.0, note='腳步：軟底鞋踩在石地')
def footstep():
    S.seed(53)
    d = 0.14
    t = secs(d)
    knock = S.sine(90 + 60 * np.exp(-t / 0.01), d) * np.exp(-t / 0.022)
    heel = S.bandpass(S.white(d), 400, 3500) * np.exp(-t / 0.012)
    grit = S.hp(S.white(d), 5000) * np.exp(-t / 0.004) * 0.3
    return st(knock * 0.7 + heel * 0.6 + grit, 0)


@sound('Jump', kind='movement', loudness=-24.0, note='跳躍：衣服「唰」')
def jump():
    S.seed(54)
    c = Canvas(0.4)
    put_at(c, whoosh(0.22, 900, 3200, 1500, 1.4, 0.35, (-0.2, 0.2), 'pink', 1.3), 0.0, 1.0)
    put_at(c, footstep() * 0.6, 0.0, 1.0)
    return c.out()


@sound('Land', kind='movement', loudness=-22.0, note='落地：「咚」＋衣服')
def land():
    S.seed(55)
    c = Canvas(0.5)
    put_at(c, thump(0.3, 105, 45, 0.07, 0.25, 1.5), 0.0, 0.8)
    put_at(c, S.lp(S.white(0.15), 1800) * np.exp(-secs(0.15) / 0.03), 0.0, 0.5)
    put_at(c, whoosh(0.15, 2500, 1500, 800, 1.5, 0.1, (0.1, -0.1), 'pink', 1.0), 0.0, 0.3)
    return c.out()


@sound('Hurt', kind='impact', loudness=-18.0, note='受傷：打擊聲＋卡通的「咿—」下滑音')
def hurt():
    S.seed(56)
    c = Canvas(0.6)
    put_at(c, thump(0.3, 170, 60, 0.06, 0.6, 2.0), 0.0, 0.8)
    put_at(c, S.bandpass(S.white(0.05), 1200, 5000) * np.exp(-secs(0.05) / 0.01), 0.0, 0.6)
    d = 0.16
    put_at(c, S.tri(S.expo(d, 950, 380), d) * S.env_ad(d, 0.004, 0.08) * 0.3, 0.03, 0.8)
    return space(c.out(), 0.1, 0.7)


@sound('Death', kind='impact', loudness=-17.0, note='倒下：魔法消散的「噗」＋往下的鈴聲＋低鳴')
def death():
    S.seed(57)
    c = Canvas(2.4)
    put_at(c, boom(1.2, 80, 30, 0.35, 1.5), 0.0, 0.7)
    put_at(c, S.lp(S.pink(0.7), 2500) * S.env_ad(0.7, 0.005, 0.18), 0.0, 0.7)
    for k, m in enumerate((96, 91, 88, 84, 79, 76, 72)):
        put_at(c, I.celesta(m, 0.5, 0.7 - 0.05 * k), 0.08 + k * 0.085, 0.45, (0.4, -0.4)[k % 2])
    put_at(c, st(glass(1.0, 20, 2000, 6000, (0.05, 0.2), np.exp(-secs(1.0) / 0.4), 21), 0), 0.05, 0.3)
    return space(c.out(), 0.3, 2.0, 0.02, 7000)


# ===================================================================== LOOPS (3 s, seamless)
LOOP = 3.0


@sound('HoverLoop', kind='loop', loudness=-24.0, loop=True, note='冰女浮空：柔和的閃爍嗡聲＋細碎冰晶')
def hover_loop():
    S.seed(61)
    d = LOOP + 0.4
    t = secs(d)
    hum = sum(S.sine(f, d) * (0.6 + 0.4 * np.sin(2 * np.pi * (k + 1) / LOOP * t + k)) for k, f in enumerate((659.3, 987.8, 1318.5)))
    air = S.lp(S.pink(d), 1400) * (0.7 + 0.3 * np.sin(2 * np.pi * 2 / LOOP * t))
    gl = glass(d, 8, 3000, 8000, (0.05, 0.2), None, 31)[:ns(d)]
    x = st(hum * 0.18 + air * 0.25 + gl * 0.5, 0)
    return loopify(S.reverb(x, 0.3, 1.6, dry=1.0)[:ns(d)], LOOP, 0.4)


@sound('WindFlightLoop', kind='loop', loudness=-21.0, loop=True, note='風男化成法球飛行：疾風呼嘯')
def wind_flight_loop():
    S.seed(62)
    d = LOOP + 0.4
    t = secs(d)
    centre = 900 * (1 + 0.35 * np.sin(2 * np.pi * 2 / LOOP * t) + 0.15 * np.sin(2 * np.pi * 5 / LOOP * t))
    w = S.sweep(S.pink(d), centre, 1.6, 'bp')
    rumble = S.lp(S.brown(d), 180) * 0.5
    x = st(w, 0.35 * np.sin(2 * np.pi * 1 / LOOP * t)) + st(rumble, 0)
    return loopify(x, LOOP, 0.4)


@sound('StormLoop', kind='loop', loudness=-21.0, loop=True, note='雷暴持續：電流＋劈啪＋遠雷')
def storm_loop():
    S.seed(63)
    d = LOOP + 0.4
    t = secs(d)
    b = buzz(d, 98, 13, 3.0) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 / LOOP * t))
    cr = S.crackle(d, 45, 0.0015, 2500, 11000)
    rum = S.lp(S.brown(d), 150) * (0.5 + 0.5 * np.sin(2 * np.pi * 1 / LOOP * t) ** 2)
    x = st(b * 0.35 + cr * 0.6 + rum * 0.5, 0)
    return loopify(x, LOOP, 0.4)


@sound('FieldLoop', kind='loop', loudness=-25.0, loop=True, note='雷場：低低的電流嗡聲')
def field_loop():
    S.seed(64)
    d = LOOP + 0.4
    t = secs(d)
    b = buzz(d, 120, 10, 2.5) * (0.7 + 0.3 * np.sin(2 * np.pi * 4 / LOOP * t))
    cr = S.crackle(d, 14, 0.0012, 3000, 11000)
    return loopify(st(b * 0.4 + cr * 0.5, 0), LOOP, 0.4)


# ===================================================================== UI
@sound('UI_Hover', group='UI', kind='ui', loudness=-30.0, note='選單滑過：很輕的「嗒」')
def ui_hover():
    d = 0.06
    t = secs(d)
    return st(S.sine(2300, d) * np.exp(-t / 0.012) * 0.5 + S.hp(S.white(d), 6000) * np.exp(-t / 0.002) * 0.2, 0)


@sound('UI_Click', group='UI', kind='ui', loudness=-24.0, note='選單點擊：圓潤的「啵」')
def ui_click():
    d = 0.12
    t = secs(d)
    pop = S.sine(S.expo(d, 1100, 520), d) * np.exp(-t / 0.035)
    return S.reverb(st(pop + S.hp(S.white(d), 5000) * np.exp(-t / 0.002) * 0.3, 0), 0.12, 0.6)


@sound('UI_Select', group='UI', kind='ui', loudness=-21.0, note='確認選擇：閃亮的兩聲「叮叮」')
def ui_select():
    c = Canvas(0.9)
    put_at(c, I.celesta(79, 0.4, 0.8), 0.0, 0.8, -0.2)
    put_at(c, I.celesta(86, 0.6, 0.9), 0.075, 0.8, 0.2)
    put_at(c, st(glass(0.4, 30, 4000, 10000, (0.04, 0.12), np.exp(-secs(0.4) / 0.15), 41), 0), 0.08, 0.3)
    return space(c.out(), 0.25, 1.2, 0.01, 10000)


@sound('UI_Back', group='UI', kind='ui', loudness=-24.0, note='返回：往下的「嘟」')
def ui_back():
    d = 0.16
    t = secs(d)
    x = S.tri(S.expo(d, 760, 420), d) * np.exp(-t / 0.05)
    return S.reverb(st(x, 0), 0.12, 0.6)


@sound('Countdown', group='UI', kind='ui', loudness=-20.0, note='倒數：木魚般的「咚」')
def countdown():
    d = 0.25
    t = secs(d)
    wood = S.sine(1150, d) * np.exp(-t / 0.03) + 0.5 * S.sine(1760, d) * np.exp(-t / 0.018)
    wood += S.bandpass(S.white(d), 1500, 6000) * np.exp(-t / 0.004) * 0.4
    return S.reverb(st(wood, 0), 0.15, 0.8)


@sound('LowTime', group='UI', kind='ui', loudness=-20.0, note='時間快到：急促的「嗶嗶」')
def low_time():
    c = Canvas(0.4)
    for at in (0.0, 0.12):
        d = 0.08
        put_at(c, S.lp(S.square(988, d, 0.5), 3500) * S.env_adsr(d, 0.003, 0.03, 0.7, 0.02) * 0.5, at, 1.0)
    return c.out()


# round 14: the player found SpellReady too loud (it rings after every cast) -> the same
# sound at about a third of the volume (-10.5 dB); SuperReady a little quieter too
@sound('SpellReady', group='UI', kind='ui', loudness=-25.0, volume=0.3, note='法術冷卻完成：輕輕的「叮」（第 14 輪：音量調到約三分之一）')
def spell_ready():
    c = Canvas(0.6)
    put_at(c, I.celesta(93, 0.3, 0.8), 0.0, 1.0)
    return space(c.out(), 0.18, 0.9, 0.01, 10000)


@sound('SpellSwitch', group='UI', kind='ui', loudness=-26.0, note='切換魔法：俐落的「嚓」')
def spell_switch():
    d = 0.09
    t = secs(d)
    x = S.sweep(S.white(d), S.expo(d, 2500, 6500), 2.0, 'bp') * np.exp(-t / 0.025) + S.sine(1500, d) * np.exp(-t / 0.015) * 0.3
    return st(x, 0)


@sound('SuperReady', group='UI', kind='ui', loudness=-19.0, volume=0.6, note='大招準備好了：往上的閃亮琶音＋「咻」（第 14 輪：音量調小一點）')
def super_ready():
    c = Canvas(1.4)
    put_at(c, whoosh(0.35, 1500, 6000, 3000, 1.6, 0.85, (-0.3, 0.3), 'white', 1.6), 0.0, 0.35)
    for k, m in enumerate((84, 88, 91, 96, 100)):
        put_at(c, I.glock(m, 0.5, 0.75), 0.22 + k * 0.06, 0.55, (k - 2) * 0.2)
    put_at(c, st(glass(0.6, 40, 4000, 10000, (0.04, 0.15), np.exp(-secs(0.6) / 0.25), 51), 0), 0.45, 0.3)
    return space(c.out(), 0.3, 1.6, 0.015, 10000)


def _chord_hit(c, at, notes, inst, d, vel, gain, spread=0.5):
    for k, m in enumerate(notes):
        put_at(c, inst(m, d, vel), at, gain, (k / max(len(notes) - 1, 1) - 0.5) * spread * 2)


@sound('RoundStart', group='UI', kind='ui', loudness=-16.0, note='開打：太鼓＋銅管和弦＋鈸＋閃光')
def round_start():
    S.seed(71)
    c = Canvas(2.4)
    put_at(c, I.taiko(58, 1.0, 1.4, 0.6), 0.0, 0.9)
    put_at(c, I.timpani(43, 0.9), 0.0, 0.5)
    _chord_hit(c, 0.0, [60, 67, 72, 76, 79], I.brass, 0.9, 0.95, 0.5)
    put_at(c, I.crash(0.9, 2.0), 0.0, 0.5)
    for k, m in enumerate((84, 91, 96)):
        put_at(c, I.glock(m, 0.6, 0.7), 0.05 + k * 0.05, 0.4, (k - 1) * 0.4)
    return space(c.out(), 0.25, 1.8, 0.02, 9000)


@sound('Victory', group='UI', kind='ui', loudness=-16.0, note='勝利：銅管號角＋定音鼓＋鐘琴')
def victory():
    S.seed(72)
    c = Canvas(4.0)
    b = 0.16
    melody = [(67, 0, 1), (72, 1, 1), (76, 2, 1), (79, 3, 3), (76, 6, 1), (79, 7, 6)]
    for m, at, dur in melody:
        put_at(c, I.brass(m, dur * b * 1.05, 0.9), at * b, 0.55, 0.1)
    for at, chord in ((0, [48, 55, 60, 64]), (3 * b, [53, 60, 65, 69]), (7 * b, [55, 62, 67, 71]), (10 * b, [48, 55, 60, 64, 67])):
        _chord_hit(c, at, chord, I.strings, 1.2 if at < 10 * b else 2.0, 0.7, 0.4)
    put_at(c, I.timpani_roll(43, 0.9, 0.9), 0.4, 0.5)
    put_at(c, I.timpani(36, 1.0, 1.8), 10 * b, 0.6)
    put_at(c, I.crash(0.8, 2.4), 10 * b, 0.45)
    for k, m in enumerate((84, 88, 91, 96, 100, 103)):
        put_at(c, I.glock(m, 0.5, 0.6), 10 * b + k * 0.07, 0.35, (k - 2.5) * 0.18)
    return space(c.out(), 0.28, 2.0, 0.02, 9000)


@sound('Defeat', group='UI', kind='ui', loudness=-18.0, note='落敗：溫柔下行的小調＋低鐘')
def defeat():
    S.seed(73)
    c = Canvas(4.0)
    b = 0.3
    for m, at, dur in [(76, 0, 1), (74, 1, 1), (72, 2, 1), (71, 3, 3)]:
        put_at(c, I.flute(m, dur * b * 1.1, 0.7), at * b, 0.6)
    _chord_hit(c, 0.0, [57, 60, 64], I.pad, 1.0, 0.7, 0.5)
    _chord_hit(c, 3 * b, [52, 56, 59, 64], I.pad, 2.0, 0.7, 0.5)
    put_at(c, I.celesta(52, 2.0, 0.6), 3 * b, 0.4)
    return space(c.out(), 0.35, 2.4, 0.03, 7000)


@sound('Draw', group='UI', kind='ui', loudness=-18.0, note='平手：懸而未決的和弦')
def draw():
    S.seed(74)
    c = Canvas(3.6)
    b = 0.28
    for m, at, dur in [(72, 0, 1), (74, 1, 1), (77, 2, 2), (74, 4, 3)]:
        put_at(c, I.celesta(m, dur * b, 0.75), at * b, 0.5)
    _chord_hit(c, 0.0, [53, 60, 65, 67], I.pad, 2.4, 0.7, 0.5)
    return space(c.out(), 0.3, 2.0, 0.02, 8000)


# ===================================================================== render
def short_term_rms(x, win=0.2, hop=0.05):
    """The loudest 0.2 s of a sound (its 'how loud does it hit' level), not the
    average over its tail -- a long reverb tail must not make a sound quieter."""
    m = st(x)
    e = np.mean(m * m, axis=1)
    w, h = ns(win), ns(hop)
    if len(e) <= w:
        return float(np.sqrt(e.mean()) + 1e-12)
    c = np.cumsum(np.concatenate([[0.0], e]))
    vals = [(c[i + w] - c[i]) / w for i in range(0, len(e) - w, h)]
    return float(np.sqrt(max(vals)) + 1e-12)


def render(names=None):
    OUT.mkdir(parents=True, exist_ok=True)
    SHEETS.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, meta in REGISTRY.items():
        if names and name not in names:
            continue
        x = st(meta['fn']())
        x -= x.mean(0)
        if not meta['loop']:
            x = S.trim(x, -58, 0.03)
            x = S.fade(x, 0.0005, min(0.25, len(x) / SR * 0.2))
        # loudness: the loudest 0.2 s sits 4 dB above the listed average-style target
        x = x * (S.db(meta['loudness'] + 4.0) / short_term_rms(x))
        x = S.limit(x, S.db(-1.0)) if S.peak(x) > S.db(-1.0) else x
        if meta['loop']:
            # the loop has no fades; keep the seam continuous after limiting
            x = np.clip(x, -0.97, 0.97)
        S.write_wav(OUT / (name + '.wav'), x)
        S.spectrogram_image(x, name).save(SHEETS / (name + '.png'))
        manifest.append(dict(name=name, group=meta['group'], kind=meta['kind'], loop=meta['loop'],
                             duration=round(len(x) / SR, 3), peak_db=round(20 * np.log10(S.peak(x)), 1),
                             rms_db=round(20 * np.log10(S.rms(x)), 1), volume=meta['volume'], note=meta['note'],
                             origin='Original procedural synthesis (r13_sfx.py), no samples'))
        print('%-18s %5.2f s  peak %5.1f dB  rms %5.1f dB' % (name, len(x) / SR, manifest[-1]['peak_db'], manifest[-1]['rms_db']), flush=True)
    path = ROOT / 'audio-r13' / 'sfx-manifest.json'
    old = {m['name']: m for m in json.loads(path.read_text(encoding='utf-8'))} if (names and path.exists()) else {}
    for m in manifest:
        old[m['name']] = m
    path.write_text(json.dumps(list(old.values()) if old else manifest, indent=1, ensure_ascii=False), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    render(sys.argv[1:] or None)
