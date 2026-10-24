"""Round 13: new background music for 小小魔法師 (original compositions, synthesized).

python r13_music.py [Name ...]  -> audio-r13/music/Music_<Name>.wav (seamless loops),
                                   audio-r13/music-manifest.json

Seven pieces, the game's existing slots (BP_ThirdPersonPlayerController.AudioSetMusic):
  Menu         F major  92  cosy: celesta / flute melody, harp, pizzicato, soft pads
  Duel         D minor  150 the main battle: brass theme over a string ostinato, taiko
  Geometric    A minor  140 the default arena: playful synth-pluck battle, glock + lead
  EmberRuins   E minor  132 fire: taiko, low strings, brass, a phrygian colour
  FrostGarden  E major  112 ice: dreamy celesta / glockenspiel, harp, flute
  SkyGrove     G major  128 wind: an airy dance, flute, plucks, tambourine
  NeonFoundry  F# minor 128 lightning: synthwave, square lead, arps, four on the floor

Each piece: melodies and chords written by hand (bars checked to add up), the
accompaniment from patterns, per-part panning and reverb, a glue compressor and a
limiter; the tail after the last bar is folded onto the start so the loop is seamless.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

import r13_synth as S
import r13_instruments as I
from r13_synth import SR, ns

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'audio-r13' / 'music'

# ------------------------------------------------------------------ notation
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def pitch(name):
    """'C#5' -> MIDI 73 ('Bb4', 'E#6' and 'Cb' allowed)."""
    m = re.fullmatch(r'([A-G])([#b]?)(-?\d)', name)
    assert m, name
    v = NOTE[m.group(1)] + {'#': 1, 'b': -1, '': 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + v


def melody(text, beats_per_bar=4):
    """'E5/1 G5/.5 r/.5 | ...' -> [(midi or None, start beat, length beats, accent)].
    Bars are checked to add up."""
    out, t = [], 0.0
    for b, bar in enumerate(text.split('|')):
        bar_t = 0.0
        for tok in bar.split():
            acc = tok.startswith('>')
            tok = tok.lstrip('>')
            p, d = tok.split('/')
            d = float(d)
            out.append((None if p == 'r' else pitch(p), t + bar_t, d, acc))
            bar_t += d
        assert abs(bar_t - beats_per_bar) < 1e-6, 'bar %d adds up to %s: %s' % (b + 1, bar_t, bar)
        t += beats_per_bar
    return out


QUAL = {'': (0, 4, 7), 'm': (0, 3, 7), '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10),
        'dim': (0, 3, 6), 'sus4': (0, 5, 7), 'sus2': (0, 2, 7), '6': (0, 4, 7, 9), 'add9': (0, 4, 7, 14),
        'm9': (0, 3, 7, 10, 14), 'maj9': (0, 4, 7, 11, 14), '9': (0, 4, 7, 10, 14), 'm6': (0, 3, 7, 9),
        '7sus4': (0, 5, 7, 10)}


def chord(sym):
    """'F#m7/A' -> (root pc, intervals, bass pc)."""
    m = re.fullmatch(r'([A-G][#b]?)([a-z0-9]*)(?:/([A-G][#b]?))?', sym)
    assert m and m.group(2) in QUAL, sym
    root = (NOTE[m.group(1)[0]] + {'#': 1, 'b': -1}.get(m.group(1)[1:], 0)) % 12
    bass = root if not m.group(3) else (NOTE[m.group(3)[0]] + {'#': 1, 'b': -1}.get(m.group(3)[1:], 0)) % 12
    return root, QUAL[m.group(2)], bass


def voicing(sym, prev=None, lo=53, hi=74):
    """Close voicing (any inversion) within [lo, hi], moving the voices as little as
    possible from the previous chord (smooth voice leading)."""
    root, iv, _ = chord(sym)
    pcs = []
    for i in iv:
        if (root + i) % 12 not in pcs:
            pcs.append((root + i) % 12)
    cands = []
    for start in range(lo, hi + 1):
        if start % 12 not in pcs:
            continue
        k = pcs.index(start % 12)
        notes = [start]
        for pc in (pcs[k:] + pcs[:k])[1:]:
            n = notes[-1] + 1
            while n % 12 != pc:
                n += 1
            notes.append(n)
        if notes[-1] <= hi:
            cands.append(notes)
    centre = (lo + hi) / 2

    def cost(v):
        move = 0 if prev is None else sum(min(abs(n - q) for q in prev) for n in v)
        return move + 0.15 * abs(np.mean(v) - centre)
    return min(cands, key=cost) if cands else [60 + root + i for i in iv]


def bass_note(sym, octave=2):
    _, _, bass = chord(sym)
    return 12 * (octave + 1) + bass


def chord_tones(sym, lo=60, hi=96):
    root, iv, _ = chord(sym)
    pcs = set((root + i) % 12 for i in iv)
    return [n for n in range(lo, hi + 1) if n % 12 in pcs]


# ------------------------------------------------------------------ rendering
_CACHE = {}


def note_audio(inst, m, d, vel):
    key = (inst.__name__, int(m), round(d, 3), round(vel, 1))
    if key not in _CACHE:
        _CACHE[key] = np.asarray(inst(m, d, round(vel, 1)), float)
    return _CACHE[key]


# mix levels by role (dBFS RMS while the part plays): the melody sits on top, drums and
# bass carry the drive, the accompaniment and the pads stay under the tune
ROLE = {'lead': -17.0, 'brass': -17.0, 'mel': -17.5, 'flute': -17.5, 'choir': -24.0,
        'kick': -21.0, 'snare': -24.5, 'hats': -30.0, 'crash': -29.0, 'taiko': -21.5, 'timp': -26.0,
        'bass': -20.5, 'arp': -24.0, 'harp': -24.0, 'ost': -23.0, 'strings': -23.5, 'pad': -25.5,
        'stab': -25.0, 'pizz': -25.5, 'glock': -27.0, 'sparkle': -29.0, 'echo': -28.0}


def active_rms(x, block=0.05, floor_db=-55.0):
    """RMS over the 50 ms blocks where the part actually sounds."""
    m = S.st(x)
    b = ns(block)
    n = len(m) // b
    if n == 0:
        return S.rms(m)
    e = np.mean(np.square(m[:n * b]).reshape(n, b, 2), axis=(1, 2))
    on = e > S.db(floor_db) ** 2
    return float(np.sqrt(e[on].mean())) if on.any() else 0.0


class Song:
    def __init__(self, name, bpm, beats=4, swing=0.0, seed=1):
        self.name, self.bpm, self.beats, self.swing = name, bpm, beats, swing
        self.spb = 60.0 / bpm
        self.levels = {}
        self.trim = {}        # per-song level offsets (dB) on top of ROLE
        self.parts = {}       # part -> dict(buf, pan, reverb send, gain)
        self.bars = 0
        S.seed(seed)
        self.rng = np.random.default_rng(seed)

    def part(self, name, gain=1.0, send=0.25, pan=0.0, hp=None, lp=None):
        self.parts[name] = dict(events=[], gain=gain, send=send, pan=pan, hp=hp, lp=lp)

    def t(self, beat):
        """Beat -> seconds, with swing on the off-eighths."""
        frac = beat % 1.0
        sw = self.swing * self.spb * 0.5 if abs(frac - 0.5) < 1e-6 else 0.0
        return beat * self.spb + sw

    def add(self, part, audio, beat, gain=1.0, pan=None, human=0.004):
        jitter = self.rng.uniform(-human, human) if human else 0.0
        self.parts[part]['events'].append((self.t(beat) + jitter, audio, gain, pan))

    def note(self, part, inst, m, beat, length, vel=0.8, pan=None, human=0.004, gate=1.0):
        if m is None:
            return
        a = note_audio(inst, m, max(0.05, length * self.spb * gate), vel)
        self.add(part, a, beat, 1.0, pan, human)

    def drum(self, part, audio, beat, gain=1.0, pan=None, human=0.002):
        self.add(part, audio, beat, gain, pan, human)

    def render(self, total_beats):
        loop_n = ns(total_beats * self.spb)
        mix = np.zeros((loop_n + ns(6.0), 2))
        send = np.zeros_like(mix)
        stems = {}
        for name, p in self.parts.items():
            buf = np.zeros_like(mix)
            for at, a, g, pan in p['events']:
                i = max(0, int(round(at * SR)))
                x = S.st(a, p['pan'] if pan is None else pan) * g
                end = min(len(buf), i + len(x))
                buf[i:end] += x[:end - i]
            if p['hp']:
                buf = S.hp(buf, p['hp'], 2)
            if p['lp']:
                buf = S.lp(buf, p['lp'], 2)
            # balance: each part to its role's level while it plays (the lead on top)
            target = ROLE.get(name)
            if target is not None:
                target += self.trim.get(name, 0.0)
            act = active_rms(buf)
            if target is not None and act > 1e-6:
                buf *= S.db(target) / act
            buf *= p['gain'] if target is None else 1.0
            stems[name] = buf
            self.levels[name] = round(20 * np.log10(active_rms(buf) + 1e-12), 1)
            mix += buf
            send += buf * p['send']
        wet = S.reverb(send, wet=1.0, rt=self.rt, predelay=0.02, damp=self.damp, dry=0.0)[:len(mix)]
        mix += wet * 0.55
        # fold everything past the loop end back onto the start: a seamless loop
        out = mix[:loop_n].copy()
        tail = mix[loop_n:]
        k = min(len(tail), loop_n)
        out[:k] += tail[:k]
        # master (glue compressor + limiter) run on the loop with 2 s of wrap-around
        # context on each side, so the dynamics are continuous across the seam
        c = ns(2.0)
        ring = np.concatenate([out[-c:], out, out[:c]])
        ring = S.compress(ring, -16, 2.0, 0.01, 0.2, 2.0)
        ring = ring * (S.db(-15.0) / S.rms(ring[c:-c]))
        ring = S.limit(ring, S.db(-1.0), 0.08)
        return ring[c:-c], stems

    levels = None

    rt = 1.8
    damp = 7000.0


# ------------------------------------------------------------------ accompaniment patterns
def arp(song, part, inst, chords, bars, start_bar, step=0.5, pattern=(0, 1, 2, 3, 2, 1), lo=60, hi=88, vel=0.6,
        gate=1.6, pan_spread=0.3):
    for b in range(bars):
        sym = chords[b % len(chords)]
        tones = chord_tones(sym, lo, hi)[:5]
        n = int(song.beats / step)
        for k in range(n):
            m = tones[pattern[k % len(pattern)] % len(tones)]
            v = vel * (1.0 if k % 2 == 0 else 0.82)
            song.note(part, inst, m, (start_bar + b) * song.beats + k * step, step * gate, v,
                      pan=pan_spread * (1 if k % 2 else -1))


def pad_chords(song, part, inst, chords, bars, start_bar, vel=0.55, lo=53, hi=74, length=None):
    prev = None
    for b in range(bars):
        sym = chords[b % len(chords)]
        v = voicing(sym, prev, lo, hi)
        prev = v
        for k, m in enumerate(v):
            song.note(part, inst, m, (start_bar + b) * song.beats, length or song.beats * 1.02, vel,
                      pan=(k / max(len(v) - 1, 1) - 0.5) * 0.6, human=0.0)


def stabs(song, part, inst, chords, bars, start_bar, beats=(0.5, 1.5, 2.5, 3.5), length=0.4, vel=0.6, lo=55, hi=76):
    prev = None
    for b in range(bars):
        sym = chords[b % len(chords)]
        v = voicing(sym, prev, lo, hi)
        prev = v
        for bt in beats:
            for k, m in enumerate(v):
                song.note(part, inst, m, (start_bar + b) * song.beats + bt, length, vel, pan=(k - 1) * 0.3)


def bassline(song, part, inst, chords, bars, start_bar, pattern, octave=2, vel=0.8):
    """pattern: [(beat, interval in semitones above the bass note or 'o' for octave, length)]."""
    for b in range(bars):
        sym = chords[b % len(chords)]
        root = bass_note(sym, octave)
        for bt, iv, ln in pattern:
            m = root + (12 if iv == 'o' else iv)
            song.note(part, inst, m, (start_bar + b) * song.beats + bt, ln, vel * (1.0 if bt % 1 == 0 else 0.85), pan=0.0)


def lead(song, part, inst, text, start_bar, vel=0.75, gate=0.95, octave=0, double=None):
    for m, st_, ln, acc in melody(text, song.beats):
        if m is None:
            continue
        song.note(part, inst, m + 12 * octave, start_bar * song.beats + st_, ln, min(1.0, vel + (0.12 if acc else 0)), gate=gate)
        if double:
            inst2, part2, oct2, v2 = double
            song.note(part2, inst2, m + 12 * oct2, start_bar * song.beats + st_, ln, v2, gate=gate)


def drums(song, bars, start_bar, style, fill=True, intensity=1.0):
    K, SN, H, OH, CL, SH, TK, CR, TOM = (I.kick(), I.snare(), I.hat(), I.hat(1, True), I.clap(), I.shaker(),
                                         I.taiko(66, 1.0, 1.0, 0.5), I.crash(1.0, 2.2), None)
    for b in range(bars):
        base = (start_bar + b) * song.beats
        last = fill and b == bars - 1
        if style == 'battle':
            for bt in ((0, 1.0), (1.5, 0.6), (2, 0.95), (2.75, 0.55)) if not last else ((0, 1.0), (2, 0.9)):
                song.drum('kick', K, base + bt[0], bt[1] * intensity)
            for bt in (1, 3):
                song.drum('snare', SN, base + bt, 0.9 * intensity)
            for k in range(8):
                song.drum('hats', OH if (k == 7 and b % 2) else H, base + k * 0.5, (0.55 if k % 2 else 0.8) * intensity, 0.25)
            if last:
                for k in range(6):
                    song.drum('snare', SN, base + 2.5 + k * 0.25, (0.35 + k * 0.1) * intensity, (k - 2.5) * 0.15)
        elif style == 'four':
            for k in range(4):
                song.drum('kick', K, base + k, 1.0 * intensity)
            for bt in (1, 3):
                song.drum('snare', CL, base + bt, 0.9 * intensity)
            for k in range(16):
                song.drum('hats', OH if k % 4 == 2 else H, base + k * 0.25, (0.7 if k % 4 == 2 else 0.4 + 0.15 * (k % 2 == 0)) * intensity, 0.2)
            if last:
                for k in range(4):
                    song.drum('snare', SN, base + 3 + k * 0.25, (0.4 + k * 0.15) * intensity)
        elif style == 'light':
            song.drum('kick', K, base, 0.7 * intensity)
            song.drum('kick', K, base + 2.5, 0.45 * intensity)
            for bt in (1, 3):
                song.drum('snare', I.snare(0.7, 210, 0.2, 0.6), base + bt, 0.45 * intensity)
            for k in range(8):
                song.drum('hats', SH, base + k * 0.5, (0.5 if k % 2 else 0.7) * intensity, 0.3)
        elif style == 'waltz':
            song.drum('kick', K, base, 0.6 * intensity)
            for k in range(1, 3):
                song.drum('hats', SH, base + k, 0.5 * intensity, 0.3)
        elif style == 'taiko':
            for bt, g in ((0, 1.0), (1.5, 0.6), (2, 0.85), (3, 0.7), (3.5, 0.6)):
                song.drum('taiko', TK, base + bt, g * intensity, (-0.2, 0.2)[int(bt * 2) % 2])
            for bt in (1, 3):
                song.drum('snare', SN, base + bt, 0.7 * intensity)
            for k in range(8):
                song.drum('hats', H, base + k * 0.5, (0.45 if k % 2 else 0.6) * intensity, 0.25)
            if last:
                for k in range(8):
                    song.drum('taiko', I.taiko(70 + 4 * k, 1.0, 0.7, 0.5), base + 2 + k * 0.25, 0.4 + 0.07 * k, (k % 2 - 0.5) * 0.4)
        elif style == 'half':
            song.drum('kick', K, base, 0.9 * intensity)
            song.drum('snare', SN, base + 2, 0.8 * intensity)
            for k in range(4):
                song.drum('hats', H, base + k, 0.5 * intensity, 0.25)
        if b == 0:
            song.drum('crash', CR, base, 0.8 * intensity, -0.25)


def setup_parts(song, extra=()):
    for name, gain, send, pan, hp_, lp_ in (('kick', 1.0, 0.05, 0.0, None, None), ('snare', 0.7, 0.18, 0.05, 120, None),
                                            ('hats', 0.45, 0.12, 0.25, 4000, None), ('crash', 0.35, 0.2, -0.2, 300, None),
                                            ('taiko', 0.9, 0.22, 0.0, None, None), ('bass', 0.85, 0.05, 0.0, None, 4000)) + tuple(extra):
        song.part(name, gain, send, pan, hp_, lp_)


# ------------------------------------------------------------------ the pieces
def menu():
    s = Song('Menu', 92, seed=11, swing=0.08)
    s.trim = {'kick': -7, 'snare': -6, 'hats': -4, 'crash': -6, 'bass': -2}
    s.rt, s.damp = 2.4, 8000
    setup_parts(s, (('mel', 0.9, 0.35, 0.05, 150, None), ('flute', 0.8, 0.35, 0.1, 200, None), ('harp', 0.55, 0.35, -0.2, 120, None),
                    ('pizz', 0.5, 0.25, 0.25, 100, None), ('pad', 0.4, 0.4, 0.0, 120, 6000), ('sparkle', 0.25, 0.5, 0.0, 2000, None)))
    A = ['F', 'C/E', 'Dm7', 'Bbmaj7', 'F/A', 'Gm7', 'C7sus4', 'C7']
    A2 = ['F', 'C/E', 'Dm7', 'Bbmaj7', 'F/A', 'Gm7', 'C7', 'F']
    B = ['Dm', 'Am', 'Bb', 'F', 'Gm7', 'Am7', 'Bbmaj7', 'C7']
    melA = 'A5/1.5 G5/.5 F5/1 C5/1 | E5/1.5 F5/.5 G5/2 | F5/1.5 E5/.5 D5/1 A4/1 | D5/2 r/1 C5/1 | A5/1.5 G5/.5 F5/1 A5/1 | Bb5/1.5 A5/.5 G5/1 F5/1 | F5/1 G5/1 C6/1 Bb5/1 | G5/3 r/1'
    melA2 = 'A5/1.5 G5/.5 F5/1 C5/1 | E5/1.5 F5/.5 G5/2 | F5/1.5 E5/.5 D5/1 A4/1 | D5/2 r/1 C5/1 | A5/1.5 G5/.5 F5/1 A5/1 | Bb5/1.5 A5/.5 G5/1 F5/1 | A5/1 G5/1 F5/1 E5/1 | F5/3 r/1'
    melB = 'D6/2 C6/1 A5/1 | C6/2 A5/1 E5/1 | D6/1.5 C6/.5 Bb5/1 F5/1 | A5/3 r/1 | Bb5/1 A5/1 G5/1 D6/1 | C6/1.5 Bb5/.5 A5/1 E5/1 | D6/1 C6/1 A5/1 F5/1 | G5/2 E5/1 C5/1'
    plan = [(A, melA, 'mel'), (A2, melA2, 'mel'), (B, melB, 'flute'), (A2, melA2, 'mel')]
    for sec, (ch, mel, who) in enumerate(plan):
        sb = sec * 8
        if who == 'mel':
            lead(s, 'mel', I.celesta, mel, sb, 0.75, 0.9)
        else:
            lead(s, 'flute', I.flute, mel, sb, 0.7, 0.92, double=(I.celesta, 'sparkle', 1, 0.35))
        arp(s, 'harp', I.harp, ch, 8, sb, 0.5, (0, 1, 2, 3, 4, 3, 2, 1), 53, 79, 0.55, 2.2)
        pad_chords(s, 'pad', I.strings, ch, 8, sb, 0.45)
        bassline(s, 'bass', I.pick_bass, ch, 8, sb, [(0, 0, 1.5), (2, 7, 1.0), (3, 0, 0.8)], 2, 0.7)
        stabs(s, 'pizz', I.pizz, ch, 8, sb, (1, 3), 0.3, 0.45, 60, 77)
        drums(s, 8, sb, 'light', fill=(sec == 3), intensity=0.55 if sec != 2 else 0.7)
    return s, 32


def duel():
    s = Song('Duel', 150, seed=12)
    s.rt, s.damp = 1.9, 7000
    setup_parts(s, (('brass', 0.95, 0.3, 0.0, 150, None), ('strings', 0.7, 0.3, -0.15, 120, None), ('ost', 0.55, 0.15, 0.2, 100, None),
                    ('choir', 0.45, 0.45, 0.0, 200, None), ('timp', 0.6, 0.25, 0.1, None, None)))
    A = ['Dm', 'Dm', 'Bb', 'C', 'Dm', 'Dm', 'Gm', 'A']
    B = ['Bb', 'F', 'C', 'Dm', 'Bb', 'F', 'Gm', 'A7']
    BR = ['Dm', 'Bb', 'Gm', 'A', 'Dm', 'Bb', 'Gm', 'A']
    melA = 'D5/1.5 A4/.5 D5/.5 E5/.5 F5/1 | E5/1 D5/1 C5/1 A4/1 | Bb4/1.5 C5/.5 D5/1 F5/1 | E5/2 G5/1 E5/1 | A5/1.5 G5/.5 F5/.5 G5/.5 A5/1 | G5/1 F5/1 E5/1 D5/1 | D5/1 G5/1 Bb5/1 A5/1 | A5/2 C#5/1 E5/1'
    melB = 'F5/1 D5/1 F5/1 Bb5/1 | A5/2 F5/1 C5/1 | E5/1 G5/1 C6/1 G5/1 | A5/3 r/1 | D6/1.5 C6/.5 Bb5/1 F5/1 | C6/1.5 Bb5/.5 A5/1 F5/1 | G5/1 Bb5/1 D6/1 C6/1 | C#6/2 A5/1 E5/1'
    melBR = 'D5/4 | F5/4 | G5/2 Bb5/2 | A5/4 | D6/4 | F6/2 D6/2 | Bb5/2 G5/2 | A5/2 C#6/2'
    plan = [('A', A, melA), ('B', B, melB), ('A', A, melA), ('BR', BR, melBR), ('B', B, melB)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        if kind == 'BR':
            lead(s, 'choir', I.choir, mel, sb, 0.65, 1.0)
            pad_chords(s, 'strings', I.strings, ch, 8, sb, 0.5, 50, 70)
            bassline(s, 'bass', I.bass, ch, 8, sb, [(0, 0, 3.5)], 2, 0.75)
            drums(s, 8, sb, 'half', fill=True, intensity=0.8)
            for b in range(8):
                s.drum('taiko', I.taiko(58, 1.0, 1.3, 0.4), (sb + b) * 4, 0.8)
        else:
            lead(s, 'brass', I.brass, mel, sb, 0.85, 0.92, double=(I.strings, 'strings', 1, 0.45) if kind == 'B' else None)
            # the string ostinato: sixteenths on the chord's root and fifth
            for b in range(8):
                root = bass_note(ch[b], 3)
                for k in range(16):
                    m = root + (0, 0, 7, 0, 12, 0, 7, 0)[k % 8]
                    s.note('ost', I.strings, m, (sb + b) * 4 + k * 0.25, 0.22, 0.55 if k % 4 else 0.75, pan=0.2)
            bassline(s, 'bass', I.bass, ch, 8, sb, [(k * 0.5, 0 if k % 4 != 3 else 'o', 0.42) for k in range(8)], 2, 0.8)
            drums(s, 8, sb, 'battle', fill=True, intensity=1.0)
            pad_chords(s, 'choir', I.choir, ch, 8, sb, 0.35, 55, 72) if kind == 'B' else None
        s.drum('timp', I.timpani(38, 1.0), sb * 4, 0.9)
    return s, 40


def geometric():
    s = Song('Geometric', 140, seed=13)
    s.rt, s.damp = 1.5, 8000
    setup_parts(s, (('lead', 0.75, 0.25, 0.05, 200, None), ('glock', 0.45, 0.35, 0.15, 500, None), ('arp', 0.45, 0.2, -0.2, 200, None),
                    ('stab', 0.5, 0.25, 0.1, 150, None), ('pad', 0.35, 0.35, 0.0, 150, 5000)))
    A = ['Am', 'F', 'C', 'G']
    B = ['F', 'G', 'Em', 'Am', 'Dm', 'G', 'C', 'E7']
    melA = 'E5/.5 A5/.5 C6/1 B5/.5 A5/.5 E5/1 | F5/.5 A5/.5 C6/1 D6/.5 C6/.5 A5/1 | G5/.5 C6/.5 E6/1 D6/.5 C6/.5 G5/1 | B5/1.5 A5/.5 G5/1 D5/1 | E5/.5 A5/.5 C6/1 B5/.5 A5/.5 E6/1 | F6/1 E6/.5 D6/.5 C6/1 A5/1 | G5/.5 A5/.5 C6/.5 D6/.5 E6/1 G6/1 | D6/2 B5/1 G5/1'
    melB = 'A5/1 C6/1 F6/1.5 E6/.5 | D6/1 B5/1 G5/2 | E6/1 D6/.5 B5/.5 G5/1 E5/1 | A5/3 r/1 | F5/1 A5/1 D6/1 F6/1 | G6/1.5 F6/.5 D6/1 B5/1 | C6/1 E6/1 G6/1 E6/1 | G#5/2 B5/1 D6/1'
    plan = [('A', A, melA), ('A', A, melA), ('B', B, melB), ('BD', A, None), ('B', B, melB)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        arp(s, 'arp', I.synthpluck, ch, 8, sb, 0.25, (0, 1, 2, 3, 2, 1, 0, 2), 57, 84, 0.55, 1.3, 0.35)
        if mel:
            lead(s, 'lead', I.lead, mel, sb, 0.75, 0.85, double=(I.glock, 'glock', 0, 0.45))
        if kind == 'B':
            stabs(s, 'stab', I.brass, ch, 8, sb, (0.5, 1.5, 2.5, 3.5), 0.22, 0.55)
        pad_chords(s, 'pad', I.pad, ch, 8, sb, 0.5)
        if kind == 'BD':
            bassline(s, 'bass', I.bass, ch, 8, sb, [(0, 0, 1.5), (2, 0, 1.5)], 2, 0.7)
            drums(s, 8, sb, 'half', fill=True, intensity=0.7)
        else:
            bassline(s, 'bass', I.bass, ch, 8, sb, [(0, 0, 0.45), (0.5, 0, 0.4), (1.5, 'o', 0.4), (2, 0, 0.45), (2.75, 0, 0.35), (3.5, 7, 0.4)], 2, 0.8)
            drums(s, 8, sb, 'battle', fill=True, intensity=0.95)
    return s, 40


def ember():
    s = Song('EmberRuins', 132, seed=14)
    s.rt, s.damp = 2.0, 6000
    setup_parts(s, (('brass', 0.95, 0.3, 0.0, 120, None), ('ost', 0.6, 0.15, -0.2, 60, None), ('choir', 0.4, 0.45, 0.0, 200, None),
                    ('timp', 0.6, 0.25, 0.1, None, None)))
    A = ['Em', 'F', 'Em', 'D', 'Em', 'F', 'G', 'F']
    B = ['Am', 'Em', 'F', 'B7', 'Am', 'Em', 'C', 'B7']
    melA = 'E5/1 B4/.5 E5/.5 F5/1 E5/1 | F5/1.5 E5/.5 C5/1 A4/1 | G5/1 F5/.5 E5/.5 D5/1 B4/1 | A4/1 D5/1 F#5/2 | B5/1.5 A5/.5 G5/1 E5/1 | A5/1 G5/.5 F5/.5 E5/1 C5/1 | D5/1 G5/1 B5/1 D6/1 | C6/2 A5/1 F5/1'
    melB = 'A5/1 C6/1 E6/2 | D6/1 B5/1 G5/2 | C6/1 A5/1 F5/1 A5/1 | D#6/2 B5/1 F#5/1 | E6/1.5 D6/.5 C6/1 A5/1 | B5/1.5 A5/.5 G5/1 E5/1 | G5/1 C6/1 E6/1 G6/1 | F#6/2 D#6/1 B5/1'
    plan = [('A', A, melA), ('A', A, melA), ('B', B, melB), ('T', A, None), ('B', B, melB)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        for b in range(8):
            root = bass_note(ch[b], 2)
            for k in range(8):
                s.note('ost', I.strings, root + (0, 0, 12, 0, 7, 0, 12, 0)[k], (sb + b) * 4 + k * 0.5, 0.4, 0.7 if k % 2 == 0 else 0.55)
        if mel:
            lead(s, 'brass', I.brass, mel, sb, 0.85, 0.92)
        if kind == 'B':
            pad_chords(s, 'choir', I.choir, ch, 8, sb, 0.4, 55, 72)
        bassline(s, 'bass', I.bass, ch, 8, sb, [(0, 0, 0.9), (1, 0, 0.4), (1.5, 0, 0.4), (2, 0, 0.9), (3, 'o', 0.4), (3.5, 0, 0.4)], 2, 0.8)
        drums(s, 8, sb, 'taiko', fill=True, intensity=1.0 if kind != 'T' else 1.15)
        s.drum('timp', I.timpani(40, 1.0), sb * 4, 0.9)
    return s, 40


def frost():
    s = Song('FrostGarden', 112, seed=15, swing=0.05)
    s.trim = {'kick': -6, 'snare': -6, 'hats': -3, 'crash': -5, 'bass': -2}
    s.rt, s.damp = 2.8, 9500
    setup_parts(s, (('mel', 0.85, 0.4, 0.05, 300, None), ('flute', 0.75, 0.4, 0.1, 200, None), ('harp', 0.5, 0.4, -0.2, 120, None),
                    ('pad', 0.45, 0.45, 0.0, 120, 7000), ('sparkle', 0.3, 0.6, 0.2, 2000, None)))
    A = ['Emaj7', 'C#m7', 'Amaj7', 'B6', 'Emaj7', 'G#m7', 'Amaj7', 'Bsus4']
    B = ['C#m', 'A', 'E', 'B', 'C#m', 'A', 'F#m7', 'B7']
    melA = 'G#5/1 B5/1 D#6/1 E6/1 | E6/1.5 D#6/.5 C#6/1 G#5/1 | A5/1 C#6/1 E6/1.5 G#6/.5 | F#6/2 D#6/1 B5/1 | G#6/1.5 F#6/.5 E6/1 B5/1 | D#6/1 B5/1 G#5/1 F#5/1 | E5/1 A5/1 C#6/1 E6/1 | E6/2 D#6/2'
    melB = 'C#6/2 B5/1 G#5/1 | A5/1.5 B5/.5 C#6/1 E6/1 | B5/2 G#5/1 E5/1 | F#5/2 D#6/2 | E6/1.5 D#6/.5 C#6/1 G#5/1 | C#6/1 B5/1 A5/1 E5/1 | F#5/1 A5/1 C#6/1 E6/1 | D#6/2 A5/1 F#5/1'
    plan = [('A', A, melA), ('B', B, melB), ('A', A, melA), ('B', B, melB)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        if kind == 'A':
            lead(s, 'mel', I.glock if sec == 0 else I.celesta, mel, sb, 0.7, 0.9, double=(I.celesta, 'sparkle', 1, 0.3) if sec == 2 else None)
        else:
            lead(s, 'flute', I.flute, mel, sb, 0.7, 0.92)
        arp(s, 'harp', I.harp, ch, 8, sb, 0.5, (0, 2, 4, 3, 1, 3, 2, 4), 52, 83, 0.5, 2.4)
        pad_chords(s, 'pad', I.strings, ch, 8, sb, 0.45, 52, 72)
        bassline(s, 'bass', I.pick_bass, ch, 8, sb, [(0, 0, 2.5), (2.5, 7, 1.2)], 2, 0.6)
        drums(s, 8, sb, 'light', fill=(sec % 2 == 1), intensity=0.5 if kind == 'A' else 0.65)
    return s, 32


def sky():
    s = Song('SkyGrove', 128, seed=16, swing=0.1)
    s.trim = {'kick': -3, 'snare': -3, 'hats': -1}
    s.rt, s.damp = 1.9, 9000
    setup_parts(s, (('flute', 0.85, 0.3, 0.05, 200, None), ('harp', 0.45, 0.3, -0.25, 120, None), ('pizz', 0.55, 0.25, 0.25, 100, None),
                    ('pad', 0.35, 0.35, 0.0, 120, 6000), ('glock', 0.3, 0.4, 0.2, 800, None)))
    A = ['G', 'D/F#', 'Em', 'C', 'G', 'D', 'C', 'D']
    B = ['Em', 'C', 'G', 'D', 'Em', 'C', 'Am7', 'D7']
    melA = 'D5/.5 G5/.5 B5/1 A5/.5 G5/.5 D5/1 | F#5/.5 A5/.5 D6/1 C6/.5 B5/.5 A5/1 | G5/.5 B5/.5 E6/1 D6/.5 B5/.5 G5/1 | E6/1.5 D6/.5 C6/2 | B5/.5 D6/.5 G6/1 F#6/.5 E6/.5 D6/1 | A5/.5 D6/.5 F#6/1 E6/.5 D6/.5 A5/1 | G5/.5 A5/.5 B5/.5 C6/.5 E6/1 D6/1 | D6/2 A5/1 F#5/1'
    melB = 'B5/1 G5/1 E5/1 G5/1 | C6/1.5 B5/.5 A5/1 G5/1 | D6/1 B5/1 G5/2 | A5/1 F#5/1 D5/2 | E6/1 D6/.5 B5/.5 G5/1 B5/1 | C6/1 E6/1 G6/1.5 E6/.5 | E6/1 C6/1 A5/1 G5/1 | F#5/1 A5/1 C6/1 D6/1'
    plan = [('A', A, melA), ('A', A, melA), ('B', B, melB), ('A', A, melA)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        lead(s, 'flute', I.flute, mel, sb, 0.72, 0.9, double=(I.glock, 'glock', 1, 0.3) if sec == 1 else None)
        arp(s, 'harp', I.harp, ch, 8, sb, 0.5, (0, 1, 2, 1, 3, 1, 2, 1), 55, 81, 0.5, 2.0)
        stabs(s, 'pizz', I.pizz, ch, 8, sb, (0.5, 1.5, 2.5, 3.5), 0.25, 0.45, 60, 76)
        if kind == 'B':
            pad_chords(s, 'pad', I.strings, ch, 8, sb, 0.45)
        bassline(s, 'bass', I.pick_bass, ch, 8, sb, [(0, 0, 0.9), (1, 7, 0.9), (2, 'o', 0.9), (3, 7, 0.9)], 2, 0.65)
        drums(s, 8, sb, 'light', fill=True, intensity=0.75)
    return s, 32


def neon():
    s = Song('NeonFoundry', 128, seed=17)
    s.rt, s.damp = 1.6, 9000
    setup_parts(s, (('lead', 0.8, 0.3, 0.0, 200, None), ('arp', 0.45, 0.25, -0.2, 200, None), ('pad', 0.45, 0.35, 0.0, 120, 6000),
                    ('echo', 0.3, 0.3, 0.3, 300, 5000)))
    A = ['F#m', 'D', 'A', 'E']
    B = ['Bm', 'D', 'F#m', 'E', 'Bm', 'D', 'E', 'C#7']
    melA = 'C#5/.5 F#5/.5 A5/.5 C#6/.5 B5/1 A5/1 | A5/1 F#5/.5 D5/.5 F#5/1 A5/1 | E5/.5 A5/.5 C#6/.5 E6/.5 D6/1 C#6/1 | B5/2 G#5/1 E5/1 | C#6/.5 F#6/.5 E6/.5 C#6/.5 B5/1 A5/1 | F#5/1 A5/1 D6/1 F#6/1 | E6/1.5 C#6/.5 A5/1 E5/1 | G#5/2 B5/2'
    melB = 'D6/1 B5/1 F#5/1 B5/1 | A5/1.5 F#5/.5 D5/1 F#5/1 | C#6/2 A5/1 F#5/1 | G#5/1 B5/1 E6/2 | F#6/1 D6/1 B5/1 D6/1 | F#6/1.5 E6/.5 D6/1 A5/1 | B5/1 E6/1 G#6/1 E6/1 | F6/2 C#6/1 G#5/1'
    plan = [('A', A, melA), ('A', A, melA), ('B', B, melB), ('BD', A, None), ('B', B, melB)]
    for sec, (kind, ch, mel) in enumerate(plan):
        sb = sec * 8
        arp(s, 'arp', I.synthpluck, ch, 8, sb, 0.25, (0, 1, 2, 3, 4, 3, 2, 1), 54, 85, 0.5, 1.2, 0.4)
        if mel:
            lead(s, 'lead', I.lead, mel, sb, 0.75, 0.9)
            # a dotted-eighth echo of the lead, quieter, to the right
            for m, st_, ln, acc in melody(mel, 4):
                if m is not None:
                    s.note('echo', I.lead, m, sb * 4 + st_ + 0.75, ln * 0.8, 0.4)
        pad_chords(s, 'pad', I.pad, ch, 8, sb, 0.55)
        bassline(s, 'bass', I.bass, ch, 8, sb, [(k * 0.5, 0 if k % 2 == 0 else 'o', 0.4) for k in range(8)], 2, 0.8)
        drums(s, 8, sb, 'four' if kind != 'BD' else 'half', fill=True, intensity=0.95 if kind != 'BD' else 0.7)
    return s, 40


PIECES = {'Menu': menu, 'Duel': duel, 'Geometric': geometric, 'EmberRuins': ember, 'FrostGarden': frost,
          'SkyGrove': sky, 'NeonFoundry': neon}


def render(names=None):
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, fn in PIECES.items():
        if names and name not in names:
            continue
        _CACHE.clear()
        song, bars = fn()
        x, _ = song.render(bars * song.beats)
        seam = float(np.abs(x[0] - x[-1]).max())
        S.write_wav(OUT / ('Music_%s.wav' % name), x)
        S.spectrogram_image(x[:ns(min(40, len(x) / SR))], 'Music_' + name, 1400, 260).save(ROOT / 'audio-r13' / 'sheets' / ('Music_%s.png' % name))
        rows.append(dict(name='Music_' + name, group='Music', bpm=song.bpm, bars=bars, duration=round(len(x) / SR, 2),
                         peak_db=round(20 * np.log10(S.peak(x)), 1), rms_db=round(20 * np.log10(S.rms(x)), 1), loop_seam=round(seam, 4),
                         origin='Original composition and synthesis (r13_music.py), no samples'))
        print('%-22s %3d bpm %3d bars %6.1f s  peak %5.1f dB  rms %5.1f dB  seam %.4f' % (
            'Music_' + name, song.bpm, bars, len(x) / SR, rows[-1]['peak_db'], rows[-1]['rms_db'], seam), flush=True)
    path = ROOT / 'audio-r13' / 'music-manifest.json'
    old = {m['name']: m for m in json.loads(path.read_text(encoding='utf-8'))} if path.exists() else {}
    for r in rows:
        old[r['name']] = r
    path.write_text(json.dumps(list(old.values()), indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    render(sys.argv[1:] or None)
