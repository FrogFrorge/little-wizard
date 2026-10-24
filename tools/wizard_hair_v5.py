"""Little Wizards V5 heads (imported by build_wizard_models_v5.py).

The four wizards share one head pipeline; everything character-specific lives
in STYLES[kind] (reference: output/character-turnarounds/3d-v2):

  head     the head surface: a smooth union of rounded volumes (skull, round
           cheeks, soft chin, button nose) in units of E = eye line to chin
  mouth    small closed mouth line (height, width, smile curve)
  cranium  the skull the hair is fitted to
  ear      sculpted ears placed where the turnarounds show them
  face     eyes, lashes, brows, blush
  scalp    Wind keeps its clipped undercut; the others get a dark scalp under
           the hair so gaps between locks never show skin
  hair     rounded, tapered clumps that grow from the scalp onto layered shells
           and flow from a crown whorl (Wind) or a part line (Fire, Lightning,
           Ice), with per-style fringe and extras (ahoge, flyaways, long fall)
  proportion  head scale, neck, torso width and arms (PROPORTIONS for the body)

Why V4 read as a "pineapple": every lock was a round closed tube, sitting on a
flat drum above the skull with a straight lower edge.

Numbers in STYLES are in the published (final) coordinates measured on the
reference sheets: metres, Z up, front -Y, character's left +X.  The build
lowers the head by SEAT after this module runs, so z gets +SEAT internally.
"""
import math, random
from math import sin, cos, pi, radians, degrees, atan2, sqrt
import numpy as np
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

SEAT = .035


# ======================================================================
#  Per-character styles
# ======================================================================
def _wind():
    return dict(
        # head scale vs body, torso width by z_old (tank top: narrower chest)
        proportion=dict(neck=dict(r=.39, ry=.41, dy=-.19), head=.80, width=[(0.75, 1.0), (0.95, .78), (1.40, .78)]),
        head=dict(E=.144, nose_z=.38, centre=(0, -.45, -.1), blobs=[
            dict(c=(0, -.62, -.3), r=(.92, .88, .58), k=.28, tilt=12),                # round cheeks
            dict(c=(0, -.833, -.524), r=(.654, .618, .431), k=.398, tilt=-2.562),     # jaw: chin forward, flat underside
            dict(relief=True, c=(0, -1.607, -.056), s=(.303, .3, .205), a=.061),      # soft dip at the nose root
            dict(c=(0, -1.365, -.349), r=(.075, .074, .12), k=.1),                    # nose bridge
            dict(c=(0, -1.52, -.378), r=(.116, .11, .102), k=.09),                    # button nose tip
            dict(relief=True, c=(0, -1.585, -.486), s=(.22, .1, .069), a=.018),       # under the nose
            dict(relief=True, c=(0, -1.346, -.783), s=(.32, .14, .07), a=.012),       # fold under the lower lip
            dict(relief=True, c=(0, -1.291, -.956), s=(.366, .22, .184), a=-.077),    # soft chin
            dict(relief=True, c=(.507, -1.318, -.02), s=(.30, .35, .19), a=.09),      # soft eye socket (left)
            dict(relief=True, c=(-.507, -1.318, -.02), s=(.30, .35, .19), a=.09)]),   # soft eye socket (right)
        mouth=dict(z=.64, width=.40, curve=-.015, thick=.022, lip_gap=.10, lip_w=.55, lip_th=.032),
        skin=(.80, .53, .41),
        cranium=dict(center=(0, .030, 1.47), axes=(.190, .188, .186), top=True),
        ear=dict(dz=.032, height=.102, width=.077, flare=45, lean=12),
        scalp=dict(mode='undercut', stubble=(.43, .345, .285),
                   hairline=[(0, 9.0), (54, 9.0), (60, 1.395), (78, 1.368), (100, 1.352), (125, 1.326),
                             (155, 1.312), (180, 1.305)],
                   temple=(60, 69)),
        face=dict(
            # round 21: a little taller, a slightly larger iris (spacing and width as before)
            eye=dict(x=.073, half_w=.042, up=.0195, low=.0240, tilt=.0040, iris=.0265, pupil=.31,
                     up_pow=.55, low_pow=.80, up_skew=.18, low_skew=-.12),
            lash=dict(base=.0024, add=.0058, wing=.40, rise=.0060, spikes=0, lower=0),
            iris=dict(rim=(.016, .034, .015), dark=(.036, .074, .028), mid=(.075, .140, .046),
                      glow=(.17, .24, .080), pupil=(.006, .008, .006)),
            brow=dict(inner=(.035, .033), outer=(.119, .059), arch=.004, thick_in=.0160, thick_out=.0070,
                      colour=(.062, .050, .026)),
            blush=dict(x=.090, z=-.044, rx=.040, rz=.026, colour=(.95, .40, .38), amount=.55),
        ),
        hair=dict(
            seed=11, center=(0, .050, 1.525),
            shell=dict(x=.226, front=.226, back=.226, top=.198, power=2.3),
            rim=[(0, 1.518), (30, 1.522), (47, 1.536), (57, 1.542), (72, 1.522), (95, 1.500), (140, 1.484),
                 (180, 1.476)],
            rim_noise=1.0,
            edge=[(0, 1.556), (40, 1.552), (65, 1.545), (95, 1.540), (125, 1.522), (155, 1.497), (180, 1.488)],
            flow=dict(type='whorl', whorl=(139, 46), swirl=1.0, fringe_pull=.6),
            whorl_locks=7,
            fringe=dict(layer=.975, root=(-.12, .030), locks=[
                (-.158, .012, .030, -72, .046), (-.112, .024, .046, -50, .054), (-.066, .002, .062, -30, .058),
                (-.022, .030, .074, -12, .056), (.022, .008, .070, 16, .058), (.066, .026, .058, 34, .054),
                (.110, .004, .044, 52, .050), (.154, .016, .030, 74, .044), (-.088, .042, .040, 40, .032),
                (.044, .046, .046, -34, .032), (-.004, .052, .036, 24, .030)]),
            skip_front=(40, .45), top_v=.50, spacing=.027,
            width=(.050, .072), thick=(.0150, .0210), round=.55, under=.38, ao_min=.30,
            lie={'fringe': (.050, .100), 'top': (.050, .110), 'side': (.070, .170), 'back': (.070, .170)},
            flick={'fringe': (.030, .055), 'top': (.052, .085), 'side': (.045, .075), 'back': (.045, .075)},
            curl={'fringe': (35, 95), 'top': (110, 170), 'side': (100, 165), 'back': (95, 160)},
            gravity={'fringe': 4.0, 'top': 0.0, 'side': 0.0, 'back': 0.0},
            rise_angle=(18, 45), jitter=14, twist=35, bend=(2.0, 5.5), rise=.010, gap=.006,
            wave=(0.0, .06), front_stop=-.78,
            colors=dict(base=(.005, .017, .014), dark=(.005, .017, .014), light=(.026, .072, .052)),
            sheen=(1.0, .86, .45),
            # physics chains (round 6): fringe by root x, curls on top by angle around the head
            chains=[dict(name='bang_r', group='bang', x=-.05, bones=2), dict(name='bang_c', group='bang', x=.0, bones=2),
                    dict(name='bang_l', group='bang', x=.05, bones=2),
                    dict(name='top_f', group='hang', angle=0, bones=2), dict(name='top_l', group='hang', angle=90, bones=2),
                    dict(name='top_b', group='hang', angle=180, bones=2), dict(name='top_r', group='hang', angle=-90, bones=2)],
            chain_attach=.40,
        ),
    )


def _fire():
    return dict(
        proportion=dict(neck=dict(r=.36, ry=.38, dy=-.20), head=.82),
        head=dict(E=.147, nose_z=.36, centre=(0, -.45, -.1), blobs=[
            dict(c=(0, -.62, -.3), r=(.97, .88, .58), k=.28, tilt=12),                # round cheeks
            dict(c=(0, -.847, -.597), r=(.643, .612, .389), k=.401, tilt=8.12),       # jaw: chin forward, flat underside
            dict(relief=True, c=(0, -1.464, -.106), s=(.314, .3, .193), a=.07),       # soft dip at the nose root
            dict(c=(0, -1.337, -.348), r=(.075, .09, .097), k=.1),                    # nose bridge
            dict(c=(0, -1.484, -.358), r=(.135, .128, .118), k=.09),                  # button nose tip
            dict(relief=True, c=(0, -1.546, -.472), s=(.22, .1, .07), a=.018),        # under the nose
            dict(relief=True, c=(0, -1.406, -.737), s=(.32, .14, .07), a=.012),       # fold under the lower lip
            dict(relief=True, c=(0, -1.295, -.96), s=(.366, .22, .12), a=-.08),       # soft chin
            dict(relief=True, c=(.473, -1.334, -.02), s=(.30, .35, .19), a=.09),      # soft eye socket (left)
            dict(relief=True, c=(-.473, -1.334, -.02), s=(.30, .35, .19), a=.09)]),   # soft eye socket (right)
        mouth=dict(z=.57, width=.58, curve=.055, thick=.020, lip_gap=.10, lip_w=.40, lip_th=.026),
        skin=(.80, .52, .40),
        cranium=dict(center=(0, .040, 1.47), axes=(.190, .200, .186), top=True),
        ear=dict(dz=.028, height=.095, width=.070, flare=36, lean=12),
        scalp=dict(mode='hair'),
        face=dict(
            # round 21: a little taller, a slightly larger iris (spacing and width as before)
            eye=dict(x=.0695, half_w=.0390, up=.0262, low=.0280, tilt=.0010, iris=.0278, pupil=.30,
                     up_pow=.42, low_pow=.50, up_skew=.10, low_skew=-.05),
            lash=dict(base=.0025, add=.0057, wing=.30, rise=.0035, spikes=0, lower=0),
            iris=dict(rim=(.10, .012, .004), dark=(.30, .030, .008), mid=(.66, .10, .016),
                      glow=(.95, .40, .06), pupil=(.03, .004, .003)),
            brow=dict(inner=(.048, .050), outer=(.118, .058), arch=.008, thick_in=.0060, thick_out=.0030,
                      colour=(.42, .14, .030)),
            blush=dict(x=.088, z=-.044, rx=.042, rz=.026, colour=(.95, .40, .36), amount=.60),
        ),
        hair=dict(
            seed=23, center=(0, .040, 1.500),
            shell=dict(x=.232, front=.212, back=.240, top=.188, power=2.2),
            rim=[(0, 1.505), (30, 1.488), (55, 1.452), (80, 1.430), (110, 1.410), (150, 1.348), (180, 1.320)],
            rim_noise=.8,
            edge=[(0, 1.548), (35, 1.535), (60, 1.488), (90, 1.452), (130, 1.398), (165, 1.338), (180, 1.330)],
            flow=dict(type='part', part_x=.004, crown=(96, 58), lateral=1.0, down=.55, fringe_pull=.25),
            whorl_locks=7, whorl=dict(lie=(.08, .12), flick=(.035, .050), curl=(15, 35)),
            part_locks=dict(count=10, phi=(30, 120), cross=.012, back=.4, down=.30, kind='side', width=(.058, .074)),
            part_skin=dict(width=.006, flare=2.5, back=-.06), steer=.04,
            fringe=dict(layer=.975, root=(-.115, .034), dir=(.35, 1.0, .55), locks=[
                (-.016, .006, .058, -30, .050), (.016, .006, .055, 28, .050), (-.060, .014, .052, -48, .054),
                (.060, .012, .050, 46, .054), (-.105, .010, .040, -60, .050), (.105, .010, .042, 62, .050),
                (-.034, .032, .040, -18, .030), (.036, .030, .036, 22, .030)]),
            skip_front=(26, .22), top_v=.50, spacing=.038,
            width=(.064, .086), thick=(.0170, .0240), round=.55, under=.40, ao_min=.35,
            lie={'fringe': (.050, .100), 'top': (.070, .130), 'side': (.080, .170), 'back': (.080, .170)},
            flick={'fringe': (.035, .060), 'top': (.060, .090), 'side': (.060, .090), 'back': (.060, .085)},
            curl={'fringe': (40, 100), 'top': (85, 135), 'side': (100, 160), 'back': (95, 150)},
            gravity={'fringe': 4.0, 'top': 0.0, 'side': 0.0, 'back': 0.0},
            rise_angle=(18, 45), jitter=12, twist=35, bend=(1.5, 4.5), rise=.010, gap=.006, rise_fixed=True,
            stable_lie=True,
            wave=(7.0, .075), front_stop=-.80,
            colors=dict(base=(.30, .060, .006), dark=(.36, .070, .006), light=(.86, .32, .030)),
            sheen=(1.0, .70, .38), spec=.30, tip=.62,
            # physics chains (round 6): fringe, sides, back, and the ahoge
            chains=[dict(name='bang_r', group='bang', x=-.05, bones=2), dict(name='bang_c', group='bang', x=.0, bones=2),
                    dict(name='bang_l', group='bang', x=.05, bones=2),
                    dict(name='side_l', group='hang', angle=80, bones=2), dict(name='back_l', group='hang', angle=135, bones=2),
                    dict(name='back_c', group='hang', angle=180, bones=2), dict(name='back_r', group='hang', angle=-135, bones=2),
                    dict(name='side_r', group='hang', angle=-80, bones=2), dict(name='top_f', group='hang', angle=0, bones=2),
                    dict(name='ahoge', group='ahoge', bones=3)],
            chain_attach=.35,
            ahoge=dict(root=(-85, 76), length=.16, width=.032, curl=250, lean=(-.35, -.3, 1.0)),
        ),
    )


def _lightning():
    return dict(
        proportion=dict(neck=dict(r=.32, ry=.34, dy=-.20), head=.82),
        head=dict(E=.143, nose_z=.33, centre=(0, -.45, -.1), blobs=[
            dict(c=(0, -.62, -.3), r=(.95, .88, .58), k=.28, tilt=12),                # round cheeks
            dict(c=(0, -.831, -.506), r=(.654, .627, .458), k=.462, tilt=8.059),      # jaw: chin forward, flat underside
            dict(relief=True, c=(0, -1.502, -.08), s=(.317, .3, .2), a=.07),          # soft dip at the nose root
            dict(c=(0, -1.322, -.27), r=(.075, .09, .12), k=.1),                      # nose bridge
            dict(c=(0, -1.452, -.337), r=(.13, .124, .114), k=.09),                   # button nose tip
            dict(relief=True, c=(0, -1.528, -.462), s=(.22, .1, .067), a=.011),       # under the nose
            dict(relief=True, c=(0, -1.423, -.701), s=(.32, .14, .07), a=.012),       # fold under the lower lip
            dict(relief=True, c=(0, -1.331, -.968), s=(.366, .22, .124), a=-.08),     # soft chin
            dict(relief=True, c=(.469, -1.352, -.02), s=(.30, .35, .19), a=.09),      # soft eye socket (left)
            dict(relief=True, c=(-.469, -1.352, -.02), s=(.30, .35, .19), a=.09)]),   # soft eye socket (right)
        mouth=dict(z=.57, width=.55, curve=.060, thick=.020, lip_gap=.10, lip_w=.40, lip_th=.028),
        skin=(.84, .56, .45),
        cranium=dict(center=(0, .040, 1.47), axes=(.190, .200, .186), top=True),
        ear=dict(dz=.010, height=.083, width=.062, flare=32, lean=12, dy=0.019),
        scalp=dict(mode='hair'),
        face=dict(
            # round 21: a little taller, a slightly larger iris (spacing and width as before)
            eye=dict(x=.067, half_w=.0390, up=.0266, low=.0275, tilt=.0030, iris=.0285, pupil=.30,
                     up_pow=.45, low_pow=.50, up_skew=.12, low_skew=-.04),
            lash=dict(base=.0025, add=.0055, wing=.32, rise=.0058, spikes=3, lower=2),
            iris=dict(rim=(.07, .012, .14), dark=(.18, .040, .36), mid=(.42, .14, .72),
                      glow=(.76, .48, .96), pupil=(.03, .006, .05)),
            brow=dict(inner=(.049, .068), outer=(.100, .072), arch=.006, thick_in=.0042, thick_out=.0018,
                      colour=(.50, .44, .50)),
            blush=dict(x=.086, z=-.042, rx=.042, rz=.026, colour=(.97, .45, .45), amount=.62),
        ),
        hair=dict(
            seed=37, center=(0, .040, 1.470),
            # scalp casting, hairline and part (shared hair code)
            shell=dict(x=.242, front=.214, back=.244, top=.200, power=2.2),
            rim=[(0, 1.468), (25, 1.470), (40, 1.462), (52, 1.385), (65, 1.300), (85, 1.288), (100, 1.290),
                 (130, 1.300), (180, 1.312)],
            rim_noise=.6,
            edge=[(0, 1.590), (35, 1.572), (60, 1.505), (90, 1.440), (130, 1.385), (165, 1.330), (180, 1.322)],
            flow=dict(type='part', part_x=-.058, crown=(100, 60), lateral=.7, down=.6, back=.25, fringe_pull=.10),
            part_skin=dict(width=.005, flare=1.5, back=-.02),
            colors=dict(base=(.68, .58, .60), dark=(.60, .49, .52), light=(.96, .88, .87)),
            sheen=(1.0, .93, .95), ao_min=.55,
            # sculpted clumps on bone chains (see ClumpHair)
            clumps=dict(
                # outer surface of the bob on the 3d-v2 sheet: height above the hair
                # centre, half-width, front and back reach (m); widest at the cheeks
                # normal short hair (round 8): the outer surface hugs the head, about
                # 2 cm out on top and at the sides, falling behind the ears to the
                # jaw (the round-6 bob reached 12 cm out and read as a hat)
                # round 21: fuller, as on the sheet (about 4-5 cm out at the cheeks instead of 2, a
                # little higher on top) -- still well inside the round-6 'hat' (12 cm)
                envelope=[(.234, .010, .010, .010), (.226, .066, .071, .066), (.210, .116, .126, .116),
                          (.182, .154, .164, .156), (.136, .190, .198, .195), (.078, .220, .222, .228),
                          (.025, .238, .232, .244), (-.028, .244, .228, .248), (-.070, .242, .220, .244),
                          (-.110, .234, .212, .236), (-.150, .220, .200, .222), (-.190, .204, .188, .206)],
                power=2.3, lam=(.22, 1.0), spacing=.021, skip_front=(40, .45), max_roots=520,
                width=(.040, .054), thick=(.017, .024), ring=.009, K=12, three=.40, part=.20, overlap=1.8,
                strand_len=(.97, 1.0), tip=.80, taper_from=.68, round=.70, under=.45, cup=.06, root_w=.60,
                w_peak=.45, widen=1.45, rise_angle=(10, 20), steer=.40, swell=(.01, .12),
                sweep_back=[(30, 0.0), (50, 22.0), (100, 22.0), (125, 10.0), (150, 0.0)], sweep_top=.20,   # round 21: was 50
                skip_temple=(40, 105, .30),
                whorl=dict(count=20, offset=.012, lam=.99, full=True, width=(.050, .066)),   # crown hair radiating from the whorl
                wave_amp=(1.0, 2.2), wave_len=(.20, .32), wave_phase=.6, phase_jitter=1.4, lock_deg=24.0,
                # hanging part around the hair axis: allowed front angle by height above the ear top
                skirt=dict(front=[(-.12, 96.0), (-.06, 108.0), (-.01, 114.0), (.04, 112.0), (.09, 100.0), (.14, 80.0)],
                           ease=.10, soft=6.0, only_back=True, cap=1.515, under_sweep=108.0,
                           cap_root_min=.03, cap_curl=-12.0,        # no cap locks from roots beside the ear
                           ear_inner_lam=.50, ear_inner_deg=140.0),
                # temples: (side, angle0, z0, angle1, z1, angle2, z2, width, layer, end curl);
                # angles from the front around the head, heights in metres
                sweeps=dict(lam_root=.75, thick=(.018, .024), flick=(.015, .022), locks=[
                    # round 21: from the part down the side to the jaw (they wrapped round to the back)
                    (1, -14, 1.692, 58, 1.575, 118, 1.335, .095, 1.02, -10),
                    (1, 12, 1.690, 66, 1.565, 120, 1.330, .090, 1.01, -10),
                    (-1, 22, 1.692, 66, 1.570, 118, 1.335, .090, 1.02, -10),
                    (1, 40, 1.672, 74, 1.550, 122, 1.325, .090, 1.00, -10),
                    (1, 50, 1.662, 80, 1.520, 126, 1.305, .085, .97, -10),
                    (1, 60, 1.650, 86, 1.495, 130, 1.290, .080, .93, -10),
                    (1, 70, 1.632, 92, 1.475, 116, 1.320, .070, .88, -8),
                    (-1, 45, 1.668, 78, 1.540, 124, 1.320, .085, 1.00, -10),
                    (-1, 58, 1.655, 86, 1.505, 128, 1.300, .080, .95, -10),
                    (-1, 70, 1.640, 92, 1.480, 116, 1.320, .070, .90, -8),
                    # short hair: the temples, from the hairline back over the ear
                    (1, 38, 1.598, 64, 1.500, 108, 1.360, .080, .97, -8),
                    (1, 48, 1.570, 72, 1.472, 108, 1.350, .075, .95, -8),
                    (-1, 38, 1.598, 64, 1.500, 108, 1.360, .080, .97, -8),
                    (-1, 48, 1.570, 72, 1.472, 108, 1.350, .075, .95, -8)]),
                bottom=[(0, 1.296), (60, 1.284), (100, 1.272), (140, 1.268), (180, 1.266)],
                bottom_jitter=(-.020, .030), layer_lift=.016,
                flip_out=.45, curl_out=(18, 36), curl_in=(-20, -8), flick=(.020, .036), inner_lam=.55, inner_curl=(-8, 2),
                tuck=dict(x=.09, margin=.010, above=.012, ramp=.07),   # side hair passes behind the ears
                release=1.490,                                   # the chains take over below this height
                core=[(-30, .25), (15, .35), (45, .70), (90, .82)], core_bottom=1.45,   # no opaque wall inside the hanging bob
                core_front=(112, 130), core_face=.12,
                # bangs (designed curves): (root x, root elevation, tip x, tip height, sideways bow,
                # width, gap over the scalp at the root / at the tip, tip curl, layer); part at x = -.035
                curtain=dict(attach=.03, thick=(.010, .014), flick=(.008, .012), tip=.70, taper_from=.55, card_tip=.55,
                             sweep_from=.25, locks=[
                    # round 21: longer and swept from the part (the sheet's fringe reaches the brows and the
                    # upper lids; over the eyes the tips stop just above the lid)
                    (-.030, 52, -.005, 1.428, .05, .064, .026, .005, -8, 1.0),     # centre lock between the brows
                    (-.015, 50, .045, 1.442, .14, .066, .026, .005, -10, 1.0),     # sweeping to her left
                    (.015, 48, .085, 1.444, .16, .064, .025, .005, -10, 1.0),
                    (.045, 45, .118, 1.428, .15, .060, .023, .005, -12, 1.0),
                    (.075, 40, .142, 1.410, .12, .056, .021, .005, -14, 1.0),
                    (-.055, 50, -.060, 1.444, -.07, .060, .024, .005, -10, 1.0),   # right of the part
                    (-.080, 45, -.098, 1.440, -.09, .058, .022, .005, -12, 1.0),
                    (-.105, 40, -.128, 1.414, -.09, .054, .020, .005, -14, 1.0),
                    (-.050, 60, -.072, 1.448, -.06, .064, .030, .006, -8, 1.0),    # behind them, over the part
                    (-.085, 56, -.116, 1.438, -.08, .060, .028, .006, -10, 1.0),
                    (.000, 60, .066, 1.446, .13, .066, .030, .006, -10, 1.0),
                    (-.022, 46, .020, 1.440, .09, .060, .014, .003, -8, .6),       # inner layer
                    (.030, 44, .100, 1.440, .14, .060, .014, .003, -10, .6),
                    (.062, 40, .130, 1.418, .12, .056, .013, .003, -12, .6),
                    (-.068, 46, -.080, 1.444, -.08, .056, .013, .003, -10, .6),
                    (-.095, 40, -.116, 1.424, -.09, .054, .012, .003, -12, .6)]),
                # face-framing locks in front of the ears: (side, front angle, tip height, width, curl)
                wisps=dict(locks=[(1, 50, 1.330, .048, -16), (1, 58, 1.318, .056, -18), (1, 68, 1.345, .046, -14),
                                  (-1, 50, 1.326, .048, -16), (-1, 58, 1.312, .056, -18), (-1, 68, 1.340, .046, -14)],
                           lam=.25, gravity=10.0, margin=.008, flick=.03, above=6.0, thick=(.012, .016)),
                # hair cards: strand-texture strips on the guides (split = cards side by side)
                cards=dict(root_w=.75, tip_narrow=.35, bow=.16, rough=.34, spec=.50, texture=2048, seed=7, translucent=.25,
                           split={'bang': 2, 'front': 2, 'sweep': 2}, base_layer=dict(lam=(.05, .12), every=2, wide=1.3)),
                # physics chains hair_<name>_NN: hanging hair by angle around the head
                # (0 front, +90 her left), face-framing locks by side, bangs by root x
                chains=[dict(name='side_l', group='hang', angle=100, bones=3),
                        dict(name='back_l', group='hang', angle=145, bones=3),
                        dict(name='back_c', group='hang', angle=180, bones=3),
                        dict(name='back_r', group='hang', angle=-145, bones=3),
                        dict(name='side_r', group='hang', angle=-100, bones=3),
                        dict(name='front_l', group='front', bones=2),
                        dict(name='front_r', group='front', bones=2),
                        dict(name='bang_r', group='bang', x=-.06, bones=2),
                        dict(name='bang_c', group='bang', x=.02, bones=2),
                        dict(name='bang_l', group='bang', x=.10, bones=2)]),
        ),
    )


def _ice():
    return dict(
        # small face under a big hat: the hat keeps most of its size
        proportion=dict(neck=dict(r=.34, ry=.36, dy=-.20), head=.75, hat=.93),
        head=dict(E=.136, nose_z=.36, centre=(0, -.5, -.1), blobs=[
            dict(c=(0, -.58, -.26), r=(1.08, .86, .7), k=.4, tilt=6),                 # round cheeks
            dict(c=(0, -.763, -.541), r=(.637, .621, .46), k=.492, tilt=-4.731),      # jaw: chin forward, flat underside
            dict(c=(0, -1.306, -.245), r=(.075, .09, .12), k=.1),                     # nose bridge
            dict(c=(0, -1.477, -.339), r=(.132, .126, .116), k=.09),                  # button nose tip
            dict(relief=True, c=(0, -1.563, -.444), s=(.22, .1, .058), a=.018),       # under the nose
            dict(relief=True, c=(0, -1.347, -.843), s=(.32, .14, .07), a=.012),       # fold under the lower lip
            dict(relief=True, c=(0, -1.229, -.889), s=(.366, .22, .12), a=-.017),     # soft chin
            dict(relief=True, c=(.551, -1.336, -.02), s=(.30, .35, .19), a=.09),      # soft eye socket (left)
            dict(relief=True, c=(-.551, -1.336, -.02), s=(.30, .35, .19), a=.09)]),   # soft eye socket (right)
        mouth=dict(z=.66, width=.32, curve=-.012, thick=.018, lip_gap=.09, lip_w=.55, lip_th=.026),
        skin=(.84, .56, .45),
        cranium=dict(center=(0, .040, 1.46), axes=(.186, .192, .176), top=False),
        ear=dict(dz=.030, height=.082, width=.062, flare=30, lean=12, dy=0.065),
        scalp=dict(mode='hair'),
        face=dict(
            # round 21: a little taller, a slightly larger iris (spacing and width as before), still half-lidded
            eye=dict(x=.075, half_w=.0450, up=.0155, low=.0285, tilt=-.0040, iris=.0245, pupil=.30,
                     up_pow=.95, low_pow=.62, up_skew=.10, low_skew=-.08),
            lash=dict(base=.0026, add=.0044, wing=.22, rise=.0010, spikes=2, lower=2),
            iris=dict(rim=(.035, .035, .11), dark=(.10, .11, .30), mid=(.24, .27, .58),
                      glow=(.50, .52, .82), pupil=(.02, .02, .05)),
            brow=dict(inner=(.035, .068), outer=(.105, .062), arch=.004, thick_in=.0045, thick_out=.0018,
                      colour=(.28, .12, .38)),
            blush=dict(x=.092, z=-.044, rx=.044, rz=.026, colour=(.95, .45, .45), amount=.50),
        ),
        hair=dict(
            seed=53, center=(0, .040, 1.460),
            shell=dict(x=.198, front=.192, back=.206, top=.150, power=2.2),
            rim=[(0, 1.500), (30, 1.478), (60, 1.420), (90, 1.405), (180, 1.395)],
            rim_noise=.2,
            edge=[(0, 1.548), (35, 1.535), (60, 1.486), (90, 1.440), (130, 1.385), (165, 1.330), (180, 1.322)],
            flow=dict(type='part', part_x=.052, crown=(100, 62), lateral=.55, down=.80, fringe_pull=.0),
            colors=dict(base=(.17, .09, .25), dark=(.20, .11, .30), light=(.55, .36, .70)),
            sheen=(.85, .80, 1.0), spec=.22, ao_min=.40,
            hat_top=1.585,                 # final z: nothing above this (under the hat)
            body=[(1.24, .072, .068, 0), (1.18, .130, .118, 0), (1.12, .250, .155, 0), (1.00, .265, .170, 0),
                  (.85, .285, .200, 0), (.60, .310, .230, 0)],
            clumps=dict(
                # hair spreading from under the hat (3d-v2 sheet), then falling to the hips
                envelope=[(.150, .010, .010, .010), (.125, .120, .130, .130), (.090, .185, .180, .190),
                          (.040, .230, .200, .225), (-.010, .262, .200, .240), (-.064, .292, .190, .252),
                          (-.105, .292, .180, .258), (-.150, .296, .170, .262), (-.200, .300, .160, .262)],
                power=2.2, lam=(.22, 1.0), spacing=.022, skip_front=(55, .60), max_roots=440,
                width=(.070, .092), thick=(.012, .018), ring=.012, K=8, three=.30, part=.15, overlap=1.9,
                strand_len=(.90, 1.0), tip=.90, taper_from=.60, round=.60, under=.40, cup=.06, widen=1.15,
                steer=.30, swell=(.0, .14), wave_amp=(.0, .0015), wave_len=(.30, .40),
                release=1.300, body_gap=.012,
                # below 'release' the hair falls: front strands over the shoulders, the rest down the back
                long=dict(release=1.300, front_end=.85, back_end=.60, ds=.012, gravity=14.0, split=88,
                          split_z=1.36, front=.55, front_y=-.10, pull=1.4, back=.10, margin=.008,
                          fall_wave=(.0005, .40), layer_drop=.12),
                tuck=dict(x=.09, margin=.008, above=.010, ramp=.12),
                # side hair turns back above the ears (no jog where the tuck would push it)
                sweep_back=[(30, 0.0), (50, 30.0), (100, 30.0), (125, 12.0), (150, 0.0)], sweep_top=.06,
                core=.10, core_bottom=1.33, core_front=(95, 120),
                # bangs (designed curves, see Lightning): long and choppy, tips at the upper lids,
                # one strand between the eyes; roots under the hat
                curtain=dict(attach=.03, thick=(.008, .012), flick=(.006, .010), tip=.70, taper_from=.50, card_tip=.60,
                             sweep_from=.30, locks=[
                    (-.020, 36, -.010, 1.400, .02, .055, .016, .004, -6, 1.0),     # between the eyes
                    (.010, 36, .035, 1.418, .05, .055, .016, .004, -8, 1.0),
                    (.040, 35, .068, 1.420, .06, .052, .015, .004, -8, 1.0),      # over her left eye
                    (.070, 33, .098, 1.414, .06, .050, .014, .004, -10, 1.0),
                    (.100, 30, .122, 1.400, .05, .046, .013, .004, -10, 1.0),     # temple
                    (-.050, 36, -.060, 1.416, -.05, .055, .016, .004, -8, 1.0),   # over her right eye
                    (-.080, 34, -.095, 1.412, -.06, .050, .014, .004, -10, 1.0),
                    (-.110, 30, -.122, 1.398, -.05, .046, .013, .004, -10, 1.0),
                    (-.005, 33, .012, 1.425, .03, .052, .009, .003, -6, .6),      # inner layer
                    (.055, 32, .082, 1.424, .05, .050, .009, .003, -8, .6),
                    (-.065, 32, -.078, 1.424, -.05, .050, .009, .003, -8, .6),
                    (.090, 30, .110, 1.414, .05, .046, .008, .003, -8, .6),
                    (-.095, 30, -.110, 1.414, -.05, .046, .008, .003, -8, .6)]),
                cards=dict(root_w=.80, tip_narrow=.22, bow=.14, rough=.36, spec=.48, texture=2048, seed=11, translucent=.15,
                           split={'bang': 2, 'long_front': 3}, twist={'long_back': 35.0, 'long_front': 25.0}, base_layer=dict(lam=(.05, .12), every=2, wide=1.3)),
                chains=[dict(name='front_l', group='front', bones=5),
                        dict(name='front_r', group='front', bones=5),
                        dict(name='side_l', group='hang', angle=105, bones=5),
                        dict(name='back_l', group='hang', angle=145, bones=5),
                        dict(name='back_c', group='hang', angle=180, bones=5),
                        dict(name='back_r', group='hang', angle=-145, bones=5),
                        dict(name='side_r', group='hang', angle=-105, bones=5),
                        dict(name='bang_r', group='bang', x=-.06, bones=2),
                        dict(name='bang_c', group='bang', x=.0, bones=2),
                        dict(name='bang_l', group='bang', x=.06, bones=2)]),
        ),
    )


STYLES = {'wind': _wind(), 'fire': _fire(), 'lightning': _lightning(), 'ice': _ice()}


# ======================================================================
#  Helpers
# ======================================================================
def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def table(points, x):
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t * t * (3 - 2 * t)
    return points[-1][1]


def V(x, y, z):
    """Final coordinates -> build space."""
    return Vector((x, y, z + SEAT))


def front_angle(p, cy=.047):
    """Degrees between the heading of p (around a vertical axis) and the front."""
    az = degrees(atan2(p.y - cy, p.x))
    return abs(((az + 90) + 180) % 360 - 180)


def direction(az, el):
    az, el = radians(az), radians(el)
    return Vector((cos(el) * cos(az), cos(el) * sin(az), sin(el)))


def rotate(v, axis, angle):
    if axis.length < 1e-9 or abs(angle) < 1e-9:
        return v.copy()
    return Matrix.Rotation(angle, 3, axis.normalized()) @ v


def bvh_of(ob):
    me = ob.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [list(p.vertices) for p in me.polygons])


def gauss_sum(terms, z):
    return sum(a * math.exp(-((z - zc) / w) ** 2) for a, zc, w in terms)


# ======================================================================
#  Ears
# ======================================================================
def build_ears(G, E, bvh):
    """Sculpted ears: rolled helix, scapha, antihelix, deep concha, tragus, lobe.
    Returns the lobe positions (for earrings)."""
    parts = G['parts']
    for ob in [o for o in parts if o.name.startswith('Ear')]:
        parts.remove(ob)
        bpy.data.objects.remove(ob, do_unlink=True)
    H, Wd = E['height'], E['width']
    G['mat']('Ear inner', (.72, .40, .32), .55)
    MR, MT = 16, 56
    lobes = {}
    for sg in (1, -1):
        cz = E['center'][2] + SEAT
        ey = E['center'][1]
        hit = bvh.ray_cast(Vector((0, ey, cz)), Vector((sg, 0, 0)), 1.0)[0]
        root_x = hit.x if hit is not None else sg * .17
        # local frame: u runs back along the ear, t up, n outward.  The back
        # rim flares away from the head; the top leans backward.
        u = Matrix.Rotation(-radians(E['flare']) * sg, 3, 'Z') @ Vector((0, 1, 0))
        lean = radians(E['lean'])
        t = (Vector((0, 0, 1)) * cos(lean) + u * sin(lean)).normalized()
        u = (u - t * u.dot(t)).normalized()
        n = u.cross(t).normalized() * sg
        front = Vector((root_x - sg * .006, ey - Wd * .42, cz))

        def outline(th):
            a = .5 * Wd * (.78 + .22 * smooth(-.85, -.15, sin(th)))
            b = .5 * H
            ct, st = cos(th), sin(th)
            r = 1 / ((abs(ct) / a) ** 2.3 + (abs(st) / b) ** 2.3) ** (1 / 2.3)
            return Vector((r * ct, r * st))
        centre2 = Vector((.47 * Wd, 0))

        def relief(rho, th):
            s, st = cos(th), sin(th)
            front_low = smooth(.2, .9, -s) * smooth(-.2, .5, -st)
            helix = .0105 * math.exp(-((rho - .90) / .085) ** 2) * (1 - .85 * front_low)
            scapha = -.0035 * math.exp(-((rho - .74) / .06) ** 2) * (1 - front_low)
            anti = .0060 * math.exp(-((rho - .56) / .075) ** 2) * smooth(-.6, .2, s + .35 * st) * smooth(-.75, -.2, st)
            px, py = rho * s, rho * st
            concha = -.0105 * math.exp(-(((px + .18) / .36) ** 2 + ((py + .12) / .42) ** 2) * 1.6)
            tragus = .006 * math.exp(-(((px + .78) / .16) ** 2 + ((py + .12) / .22) ** 2))
            lobe = .004 * math.exp(-(((px + .05) / .45) ** 2 + ((py + .86) / .22) ** 2))
            return .006 + helix + scapha + anti + concha + tragus + lobe
        rings, inner_flags = [], []
        for i in range(1, MR + 1):
            rho = i / MR
            rings.append([(outline(2 * pi * j / MT) * rho, relief(rho, 2 * pi * j / MT) - .0015 * rho) for j in range(MT)])
            inner_flags.append(rho)
        rings.append([(outline(2 * pi * j / MT) * 1.03, .0010) for j in range(MT)])
        inner_flags.append(2)
        for i in range(MR, 0, -1):
            rho = i / MR
            rings.append([(outline(2 * pi * j / MT) * rho * .97, -.0045 * (1 - .4 * rho * rho) - .002) for j in range(MT)])
            inner_flags.append(2)
        vs, fs, mi = [], [], []
        to3 = lambda o, h: front + u * (centre2.x + o.x) + t * o.y + n * h
        vs.append(to3(Vector((0, 0)), relief(0, 0)))
        for ring in rings:
            for o, h in ring:
                vs.append(to3(o, h))
        vs.append(to3(Vector((0, 0)), -.0065))
        back_c = len(vs) - 1

        def quad(a, b, c, d):
            # n = (u x t) * sg: the winding flips with the mirrored side
            fs.append((a, d, c, b) if sg > 0 else (a, b, c, d))
        for j in range(MT):
            a, b = 1 + j, 1 + (j + 1) % MT
            fs.append((0, a, b) if sg > 0 else (0, b, a))
            mi.append(1)
        for i in range(len(rings) - 1):
            for j in range(MT):
                a = 1 + i * MT + j
                b = 1 + i * MT + (j + 1) % MT
                quad(a, b, b + MT, a + MT)
                rho = inner_flags[i]
                th = 2 * pi * (j + .5) / MT
                mi.append(1 if rho < .86 and relief(rho, th) < .0040 else 0)
        last = 1 + (len(rings) - 1) * MT
        for j in range(MT):
            a, b = last + j, last + (j + 1) % MT
            fs.append((back_c, b, a) if sg > 0 else (back_c, a, b))
            mi.append(0)
        for k, p in enumerate(vs):
            along = (p - front).dot(u)
            if along < Wd * .30:
                vs[k] = p - n * .010 * smooth(Wd * .30, 0, along)
        ob = G['mesh']('Ear sculpted ' + ('l' if sg > 0 else 'r'), vs, fs, 'Skin', 'head')
        ob.data.materials.append(G['mats']['Ear inner'])
        for poly, m in zip(ob.data.polygons, mi):
            poly.material_index = m
        lobes['l' if sg > 0 else 'r'] = to3(Vector((-.05 * Wd, -.46 * H)), .002) - n * .002
    return lobes


# ======================================================================
#  Eyes, brows, nose, blush
# ======================================================================
def _surf(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[0]
    return hit.y if hit is not None else -.15


def _ribbon(G, name, lo, hi, material, w, lift=.0, thick=.0008):
    """Decal strip between two point lists lying on the face, with a little
    thickness so it reads in silhouette and survives back-face culling."""
    n = len(lo)
    vs = []
    for k in range(n):
        vs.append(lo[k] - Vector((0, lift, 0)))
        vs.append(hi[k] - Vector((0, lift, 0)))
    for k in range(n):
        vs.append(lo[k] - Vector((0, lift - thick, 0)))
        vs.append(hi[k] - Vector((0, lift - thick, 0)))
    b = 2 * n
    fs = []
    for k in range(n - 1):
        a0, a1, c0, c1 = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        fs.append((a0, c0, c1, a1))
        fs.append((b + a0, b + a1, b + c1, b + c0))
        fs.append((a1, c1, b + c1, b + a1))
        fs.append((a0, b + a0, b + c0, c0))
    fs.append((0, 1, b + 1, b))
    fs.append((2 * n - 2, b + 2 * n - 2, b + 2 * n - 1, 2 * n - 1))
    nrm = (vs[2] - vs[0]).cross(vs[3] - vs[0])
    if nrm.y > 0:
        fs = [tuple(reversed(f)) for f in fs]
    return G['mesh'](name, vs, fs, material, w)


def ribbon_points(lo, hi, lift=.0, thick=.0008):
    """Vertex positions of _ribbon(lo, hi, ..., lift, thick), in its order."""
    out = []
    for a, b in zip(lo, hi):
        out += [a - Vector((0, lift, 0)), b - Vector((0, lift, 0))]
    for a, b in zip(lo, hi):
        out += [a - Vector((0, lift - thick, 0)), b - Vector((0, lift - thick, 0))]
    return out


def set_shape_keys(ob, keys):
    """Morph targets: name -> absolute vertex positions (mesh order).  Blender
    joins shape keys by name, so the game mesh gets one morph target each
    (Unreal imports them from the FBX)."""
    me = ob.data
    if me.shape_keys is None:
        ob.shape_key_add(name='Basis', from_mix=False)
    for name, pos in keys.items():
        assert len(pos) == len(me.vertices), (ob.name, name)
        kb = me.shape_keys.key_blocks.get(name)
        if kb is None:
            kb = ob.shape_key_add(name=name, from_mix=False)
        for d, p in zip(kb.data, pos):
            d.co = p
        kb.value = 0.0                        # new keys start at 1.0 in Blender: neutral face
    me.update()


def _normals_from_face(ob, face, w):
    """Custom shading normals for a sheet lying on the face: per vertex,
    weight w of the face's smooth normal at the nearest face point, the rest
    the sheet's own.  (Blender keeps custom normals relative to the surface,
    so they follow the armature and the morph targets.)"""
    from mathutils.interpolate import poly_3d_calc
    fm = face.data
    fm.update()
    fv = [v.co.copy() for v in fm.vertices]
    fn = [v.normal.copy() for v in fm.vertices]
    fbvh = BVHTree.FromPolygons(fv, [p.vertices[:] for p in fm.polygons])
    me = ob.data
    me.update()
    out = []
    for v in me.vertices:
        own = v.normal.copy()
        k = w[v.index]
        if k <= 1e-4:
            out.append(own)
            continue
        loc, _, idx, _ = fbvh.find_nearest(v.co)
        vids = fm.polygons[idx].vertices[:]
        ws = poly_3d_calc([fv[i] for i in vids], loc)
        n = sum((fn[i] * c for i, c in zip(vids, ws)), Vector())
        if n.length < 1e-9:
            out.append(own)
            continue
        n.normalize()
        if n.dot(own) < 0:
            n = -n
        out.append(own.lerp(n, k).normalized())
    me.normals_split_custom_set_from_vertices(out)


def join_lids_into_face(G):
    """Round 10: the upper eyelid sheets become part of the face object.
    Subsurface scattering (Cycles) works per object, so the closed lid next
    to the face showed its outline even with matching shape and normals; one
    object also gives the lid the face's own material (scalp, blush).  The
    lid vertices keep an 'eyelid' attribute (1 left, 2 right) for the checks."""
    import bpy
    face = G['faceob']
    lids = [o for o in G['parts'] if o.name.startswith('Upper eyelid')]
    if not lids:
        return
    if 'eyelid' not in face.data.attributes:
        face.data.attributes.new('eyelid', 'INT', 'POINT')
    for o in lids:
        a = o.data.attributes.new('eyelid', 'INT', 'POINT')
        a.data.foreach_set('value', [1 if o.name.endswith(' l') else 2] * len(o.data.vertices))
        G['parts'].remove(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in lids:
        o.select_set(True)
    face.select_set(True)
    bpy.context.view_layer.objects.active = face
    bpy.ops.object.join()


def rebuild_eyes_and_brows(G, F, ez):
    """Lash line with wing, crease, lower lid, iris tucked under the upper lid,
    girl lashes where asked, flat tapered brows, nostrils."""
    parts = G['parts']
    drop = ('Eye white', 'Iris limbal rim', 'Iris color', 'Iris inner light', 'Iris radial fiber', 'Large pupil',
            'Eye catchlight', 'Upper eyelid', 'Lower eyelid', 'Soft eyelash', 'Expressive eyebrow')
    for ob in [o for o in parts if o.name.startswith(drop)]:
        parts.remove(ob)
        bpy.data.objects.remove(ob, do_unlink=True)
    bvh = bvh_of(G['faceob'])
    mat = G['mat']
    I = F['iris']
    mat('Lash', (.016, .010, .008), .45)
    mat('Brow', F['brow']['colour'], .75)
    mat('Lower lid', (.60, .36, .30), .6)
    mat('Lid crease', (.66, .42, .34), .6)
    mat('Eye white', (.92, .90, .87), .3)
    mat('Eye white shade', (.74, .69, .68), .35)
    for k in ('rim', 'dark', 'mid', 'glow', 'pupil'):
        mat('Iris ' + k, I[k], .25 if k != 'pupil' else .2)
    mat('Catchlight', (1.0, 1.0, 1.0), .1)
    E = F['eye']
    Lh = F['lash']
    EW = E['half_w']
    bones = G['bones']
    pk = dict(EYE_POCKET, **STYLES[G['KIND']]['head'].get('eye_pocket', {}))
    Eh = G.get('HEAD_E', .14)
    Mm = pk['margin'] * Eh                       # socket margin around the eye outline (m)
    dome_m = pk['dome'] * pk['depth'] * Eh       # how far the eyeball bulges out of the socket floor
    for sg in (1, -1):
        side = 'l' if sg > 0 else 'r'
        ex = sg * E['x']
        for nm, dz in (('face_eye_', 0.0), ('face_gaze_', 0.0)):
            h, t_, parent = bones[nm + side]
            h = Vector(h)
            h2 = Vector((ex, h.y, ez + dz))
            bones[nm + side] = (h2, h2 + (Vector(t_) - h), parent)

        def upper(u):
            return ez + E['up'] * max(0, 1 - u * u) ** E['up_pow'] * (1 + E['up_skew'] * u) + E['tilt'] * u

        def lower(u):
            return ez - E['low'] * max(0, 1 - u * u) ** E['low_pow'] * (1 + E['low_skew'] * u) + E['tilt'] * u

        def X(u):
            return ex + sg * u * EW

        def on(x, z, lift):
            return Vector((x, _surf(bvh, x, z) - lift, z))

        Me = .45 * Mm                                  # the eye white stops partway up the socket walls
        UNC = G.get('UNCARVED_BVH')

        def unc_y(x, z):
            """The face without the socket (the closed lid lies on it)."""
            hit = UNC.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[0] if UNC else None
            return hit.y if hit is not None else _surf(bvh, x, z)

        def eye_lift(x, z):
            """Eye surface above the socket floor: lies on the walls at the edges
            (tucked under the lids), bulges like an eyeball in the middle."""
            u = max(-1.0, min(1.0, (x - ex) / EW * sg))
            zu, zl = upper(u) + Me, lower(u) - Me
            v = max(0.0, min(1.0, (z - zl) / max(1e-6, zu - zl)))
            return .0004 + dome_m * max(0.0, 1 - u * u) ** .7 * sin(pi * v) ** .8
        # eye white: fills the socket opening
        NU, NV = 36, 11
        vs, fs, mi = [], [], []
        for i in range(NU + 1):
            u = -1 + 2 * i / NU
            for j in range(NV + 1):
                v = j / NV
                z = lerp(lower(u) - Me, upper(u) + Me, v)
                vs.append(on(X(u), z, eye_lift(X(u), z)))
        white = [v.copy() for v in vs]
        for i in range(NU):
            for j in range(NV):
                a = i * (NV + 1) + j
                fs.append((a, a + 1, a + NV + 2, a + NV + 1) if sg < 0 else (a, a + NV + 1, a + NV + 2, a + 1))
                mi.append(1 if j >= NV - 2 else 0)
        ob = ob_white = G['mesh']('Eye white ' + side, vs, fs, 'Eye white', 'face_eye_' + side)
        ob.data.materials.append(G['mats']['Eye white shade'])
        for poly, m in zip(ob.data.polygons, mi):
            poly.material_index = m
        # iris: polar grid clipped by the lids
        RI = E['iris']
        icx, icz = ex + sg * .002, ez - .0025

        def clip(x, z):
            u = max(-1, min(1, (x - ex) / EW * sg))
            return max(lower(u) - Me + .0004, min(upper(u) + Me - .0003, z))
        NA = 48
        vs, fs, mi = [], [], []
        radii = [0, .18, .30, .40, .48, .62, .74, .86, .93, 1.0]
        for r in radii:
            for j in range(NA):
                a = 2 * pi * j / NA
                x = icx + RI * r * cos(a)
                z = clip(x, icz + RI * r * sin(a))
                vs.append(on(x, z, eye_lift(x, z) + .0003 + .0004 * (1 - r)))
        for ri in range(len(radii) - 1):
            for j in range(NA):
                a = ri * NA + j
                b = ri * NA + (j + 1) % NA
                fs.append((a, a + NA, b + NA, b))
                rr = (radii[ri] + radii[ri + 1]) / 2
                ang = 2 * pi * (j + .5) / NA
                if rr < E['pupil']:
                    m = 0
                elif rr > .88:
                    m = 1
                elif sin(ang) > .45:
                    m = 2                                     # shadow of the upper lid
                elif rr > .70:
                    m = 2
                elif sin(ang) < -.25 and rr < .86:
                    m = 4                                     # lower glow crescent
                else:
                    m = 3
                mi.append(m)
        ob = ob_iris = G['mesh']('Iris ' + side, vs, fs, 'Iris pupil', 'face_gaze_' + side)
        ob.data.materials.clear()
        for nm in ['Iris pupil', 'Iris rim', 'Iris dark', 'Iris mid', 'Iris glow']:
            ob.data.materials.append(G['mats'][nm])
        for poly, m in zip(ob.data.polygons, mi):
            poly.material_index = m
        obs_catch = []
        for dx, dz, rx, rz in [(-.36, .30, .30, .26), (.40, -.42, .12, .10)]:
            cx = icx + sg * dx * RI
            cz = clip(cx, icz + dz * RI)
            vs = [on(cx, cz, eye_lift(cx, cz) + .0010)]
            for j in range(16):
                a = 2 * pi * j / 16
                qx, qz = cx + RI * rx * cos(a), clip(cx, cz + RI * rz * sin(a))
                vs.append(on(qx, qz, eye_lift(qx, qz) + .0010))
            fs = [(0, 1 + j, 1 + (j + 1) % 16) for j in range(16)]
            obs_catch.append(G['mesh']('Eye catchlight ' + side, vs, fs, 'Catchlight', 'face_gaze_' + side))
        # ---- blink: morph targets Blink / Blink_L / Blink_R (as in VRM / VRoid
        # faces).  The upper lid is a skin sheet: a band just above the rim
        # lies on the face all the time (it meets the skin at a very shallow
        # angle, so no seam shows), and the rows below it -- folded into a thin
        # strip under the lash line while the eye is open -- slide down over
        # the eye to the lower rim.  Closed, the lid follows the face as if
        # there were no socket, with a soft eyeball bulge; the upper lash line
        # becomes a soft U on the lower rim.  The eye itself does not move.
        bulge = pk['lid_bulge']

        def rims(u):
            uc = max(-1.0, min(1.0, u))
            return upper(uc) + Mm, lower(uc) - Mm

        def band(u):
            """Height of the static band above the rim (tapering to the corners)."""
            return .0016 + (pk['lid_band'] - .0016) * max(0.0, 1 - u * u) ** .5

        def lid_y(x, z):
            """Closed lid: flush with the face as if there were no socket
            (lid_front in front of it) with a soft eyeball bulge; toward the top
            of the band it passes just under the skin (lid_tuck)."""
            u = max(-1.0, min(1.0, (x - ex) / EW * sg))
            zt, zb = rims(u)
            vc = max(0.0, min(1.0, (zt - z) / max(1e-6, zt - zb)))
            t = smooth(zt + .0008, zt + band(u), z)
            # in front of the face all over the band, passing under it only at
            # the band's top edge (round 10: the crossing was halfway up the
            # band, where the face already curves into the socket -- a faint
            # line around the closed lid up close)
            off = -pk['lid_front'] * (1 - smooth(.80, 1.0, t)) + pk['lid_tuck'] * smooth(.95, 1.0, t)
            # past the eye corners it ends under the skin (it bridges the
            # socket's corners: following the carved face there instead left
            # folds, or let the face poke through -- tested in round 10)
            off = lerp(off, pk['lid_tuck'], smooth(1.05, 1.11, abs(x - ex) / EW))
            # (the eyeball bulge fades to nothing at the corners with zero slope:
            # the old (1 - u^2)^.6 fell off steeply there and outlined the lid)
            return unc_y(x, z) + off - bulge * sin(pi * vc) ** 2 * max(0.0, 1 - u * u) ** 2
        # closed, the eye sits a little further back (its edges are a hair in
        # front of the socket-free face level), so the lid can lie flush
        back = Vector((0, pk['eye_back'], 0))
        morph = {o: [v.co + back for v in o.data.vertices] for o in [ob_white, ob_iris] + obs_catch}
        # upper lash line with an outward wing (closed: a soft U on the lower rim,
        # the wing flicking a little down and out)
        lo, hi, clo, chi = [], [], [], []
        NL = 34
        wing = Lh['wing']
        for i in range(NL + 1):
            u = -.98 + (1.98 + wing) * i / NL
            if u <= 1:
                base = upper(u) + Mm - .0007
                th = Lh['base'] + Lh['add'] * smooth(-.90, .55, u)
                x = X(u)
                cth = .55 * th + .0004
                cb = lower(u) - Mm - .35 * cth
            else:
                k = min(1.0, (u - 1) / wing)
                x = X(1) + sg * EW * wing * k
                base = upper(1) + Mm - .0007 + Lh['rise'] * k * k + .002 * k
                th = (Lh['base'] + Lh['add']) * max(0.0, 1 - k) ** 1.1 + .0002
                c1 = .55 * (Lh['base'] + Lh['add']) + .0004
                cth = .55 * th + .0002
                cb = lower(1) - Mm - .35 * c1 - .0018 * k - .4 * Lh['rise'] * k * k
            lo.append(on(x, base, .0014))
            hi.append(on(x, base + th, .0014))
            clo.append(Vector((x, lid_y(x, cb) - .0012, cb)))
            chi.append(Vector((x, lid_y(x, cb + cth) - .0012, cb + cth)))
        ob = _ribbon(G, 'Upper lash line ' + side, lo, hi, 'Lash', 'head', .0, .0014)
        morph[ob] = ribbon_points(clo, chi, .0, .0014)
        # girl lashes: small tapered spikes at the outer third (closed: pointing down)
        for k in range(Lh['spikes']):
            u = .55 + .20 * k
            x0, z0 = X(u), upper(u) + Mm + Lh['base'] + Lh['add'] * .8
            cz0 = lower(u) - Mm
            ln = .0065 + .002 * k
            ang = radians(35 + 18 * k)
            lo, hi, clo, chi = [], [], [], []
            for i in range(7):
                s_ = i / 6
                x = x0 + sg * ln * s_ * cos(ang) * 1.0
                rise = ln * s_ * sin(ang) - .0012 * s_ * s_
                z = z0 + rise
                th = .0018 * (1 - s_) + .0002
                lo.append(on(x, z - th / 2, .0036))
                hi.append(on(x, z + th / 2, .0036))
                cz = cz0 - .75 * rise
                clo.append(Vector((x, lid_y(x, cz) - .0020, cz - th / 2)))
                chi.append(Vector((x, lid_y(x, cz) - .0020, cz + th / 2)))
            ob = _ribbon(G, 'Eyelash ' + side, lo, hi, 'Lash', 'head', .0, .0008)
            morph[ob] = ribbon_points(clo, chi, .0, .0008)
        for k in range(Lh['lower']):
            u = .55 + .25 * k
            x0, z0 = X(u), lower(u) - Mm - .0003
            lo, hi = [], []
            for i in range(6):
                s = i / 5
                x = x0 + sg * .0035 * s
                z = z0 - .0045 * s
                th = .0012 * (1 - s) + .0002
                lo.append(on(x - th / 2, z, .0016))
                hi.append(on(x + th / 2, z, .0016))
            _ribbon(G, 'Lower eyelash ' + side, lo, hi, 'Lash', 'face_eye_' + side, .0, .0006)
        # double-eyelid crease (closed: eases down toward the lid)
        lo, hi, clo, chi = [], [], [], []
        for i in range(21):
            u = -.45 + 1.40 * i / 20
            zr = upper(min(u, 1)) + Mm
            z = zr + .0066 + .0020 * max(0, 1 - u * u)
            th = .0007 + .0006 * sin(pi * i / 20)
            x = X(min(u, 1.05))
            lo.append(on(x, z, .0010))
            hi.append(on(x, z + th, .0010))
        ob = _ribbon(G, 'Eyelid crease ' + side, lo, hi, 'Lid crease', 'head', .0, .0006)
        # lower lid line, darker toward the outer corner
        lo, hi = [], []
        for i in range(25):
            u = -.55 + 1.55 * i / 24
            z = lower(u) - Mm
            th = .0004 + .0006 * smooth(-.2, .9, u)
            lo.append(on(X(u), z - th, .0007))
            hi.append(on(X(u), z + .0002, .0007))
        _ribbon(G, 'Lower lid line ' + side, lo, hi, 'Lower lid', 'face_eye_' + side, .0, .0006)
        # the lid sheet: per column, the static band (KA rows, rim + lid_band
        # down to the rim) and KB sliding rows (closed: rim -> lower rim; open:
        # a 0.2 mm strip at the rim, under the lash line)
        NUl, KA, KB = 48, 8, 26
        KL = KA + KB
        vs, cs, fs = [], [], []
        for i in range(NUl + 1):
            u = -1.12 + 2.24 * i / NUl                   # a little past the corners (the socket's corner slots)
            x = X(u)
            zt, zb = rims(u)
            z_end = zt + .0008                           # the band ends just above the rim
            for k in range(KA + 1):
                z = lerp(zt + band(u), z_end, k / KA)
                p = Vector((x, lid_y(x, z), z))
                vs.append(p)
                cs.append(p.copy())
            # open, the sliding rows lie on the socket rim in a strip between the
            # eye's top edge and the lash line (in front of the one, behind the
            # other); past the corners, under the skin
            # (the lash line starts just short of the inner corner and runs on
            # past the outer one in its wing)
            rest_off = lerp(-.0008, .0002, smooth(.86, .96, -u) if u < 0 else smooth(.97, 1.03, u))
            for k in range(1, KB + 1):
                s_ = k / KB
                zc_ = lerp(z_end, zb, s_)
                cs.append(Vector((x, lid_y(x, zc_), zc_)))
                zr = lerp(z_end, zt - .0006, s_)
                vs.append(Vector((x, _surf(bvh, x, zr) + rest_off, zr)))
        for i in range(NUl):
            for k in range(KL):
                a = i * (KL + 1) + k
                fs.append((a, a + KL + 1, a + KL + 2, a + 1))
        mid = (NUl // 2) * (KL + 1) + KL // 2
        nrm = (cs[mid + KL + 1] - cs[mid]).cross(cs[mid + 1] - cs[mid])
        if nrm.y > 0:                                   # normals toward the front (closed shape)
            fs = [tuple(reversed(f)) for f in fs]
        lid = G['mesh']('Upper eyelid ' + side, vs, fs, 'Skin', 'head')
        for poly in lid.data.polygons:
            poly.use_smooth = True
        morph[lid] = cs
        # round 10: the band (it does not move) shades with the face's own
        # normals where it meets the face (its top rows)
        wn = []
        for i in range(NUl + 1):
            u = -1.12 + 2.24 * i / NUl
            for k in range(KL + 1):
                # only the rows near the band's top edge, which lie on
                # uncarved skin (near the rim the face dips into the socket,
                # and its normals there would mark the rim on the closed lid)
                wn.append(smooth(.35, .70, 1 - k / KA) if k <= KA else 0.0)
        _normals_from_face(lid, G['faceob'], wn)
        one = 'Blink_' + side.upper()
        for o, pos in morph.items():
            set_shape_keys(o, {'Blink': pos, one: pos})
        # brow: thick at the inner end, tapering
        B = F['brow']
        lo, hi = [], []
        NB = 30
        for i in range(NB + 1):
            s = i / NB
            x = sg * lerp(B['inner'][0], B['outer'][0], s)
            zc = ez + lerp(B['inner'][1], B['outer'][1], s) + B['arch'] * sin(pi * s ** .85)
            thick = lerp(B['thick_in'], B['thick_out'], s ** 1.3) * (.75 + .25 * smooth(0, .12, s))
            lo.append(on(x, zc - thick * .48, .0014))
            hi.append(on(x, zc + thick * .52, .0014))
        _ribbon(G, 'Brow ' + side, lo, hi, 'Brow', 'face_brow_' + side, .0, .0012)
    # small nostrils under the nose tip so the nose reads from the front
    mat('Nostril', (.58, .33, .27), .6)
    tip = G['NOSE_TIP']
    for sg in (1, -1):
        cx, cz = sg * .0075, tip.z - .0090
        vs = []
        for j in range(14):
            a = 2 * pi * j / 14
            x = cx + .0024 * cos(a)
            z = cz + .0014 * sin(a) - .0005 * sg * cos(a)
            vs.append(Vector((x, _surf(bvh, x, z) - .0009, z)))
        c = sum(vs, Vector()) / len(vs)
        vs.append(c)
        fs = [(14, j, (j + 1) % 14) for j in range(14)]
        if ((vs[0] - vs[14]).cross(vs[1] - vs[14])).y > 0:
            fs = [tuple(reversed(f)) for f in fs]
        G['mesh']('Nostril ' + ('l' if sg > 0 else 'r'), vs, fs, 'Nostril', 'face_nose')


def add_blush(G, F, ez):
    """Soft cheek colour in the skin colour attribute."""
    B = F['blush']
    me = G['faceob'].data
    attr = me.color_attributes.get('Scalp')
    if attr is None:
        return
    pink = Vector(B['colour'])
    for v in me.vertices:
        p = v.co
        if p.y > -.03:
            continue
        a = max(math.exp(-(((p.x - sg * B['x']) / B['rx']) ** 2 + ((p.z - (ez + B['z'])) / B['rz']) ** 2)) for sg in (1, -1))
        if a > .01:
            c = Vector(attr.data[v.index].color[:3])
            attr.data[v.index].color = (*c.lerp(pink, B['amount'] * a), 1)


# ======================================================================
#  Scalp shading
# ======================================================================
def shade_scalp(G, S):
    """Wind: stubble on the clipped sides/back, dark scalp under the long hair.
    Others: dark scalp under the hair (natural hairline)."""
    faceob = G['faceob']
    mats = G['mats']
    me = faceob.data
    H = S['hair']
    Sc = S['scalp']
    skin = Vector(mats['Skin'].diffuse_color[:3])
    under = Vector(H['colors']['base'])
    attr = me.color_attributes.new(name='Scalp', type='FLOAT_COLOR', domain='POINT')
    mask = me.attributes.new(name='StubbleMask', type='FLOAT', domain='POINT')
    for v in me.vertices:
        p = v.co
        fa = front_angle(p)
        ez = table(H['edge'], fa) + SEAT
        if Sc['mode'] == 'undercut':
            stub = Vector(Sc['stubble'])
            z_hl = table(Sc['hairline'], fa) + SEAT
            if fa > 150 and abs(p.x) < .085:
                z_hl -= .012 * (1 - abs(p.x) / .085)
            temple = smooth(Sc['temple'][0], Sc['temple'][1], fa)
            top = smooth(ez - .010, ez + .002, p.z)
            s = temple * smooth(z_hl - .003, z_hl + .007, p.z) * (1 - top)
            fade = smooth(z_hl - .002, z_hl + .035, p.z)
            frontline = (1 - temple) * smooth(ez - .014, ez - .002, p.z)
            u = max(top * temple, frontline)
            col = skin.lerp(stub, s * (.62 + .38 * fade)).lerp(under, u)
        else:
            s = 0.0
            u = smooth(ez - .012, ez + .004, p.z) * (1 - part_mask(H, p))
            col = skin.lerp(under, u)
        attr.data[v.index].color = (*col, 1)
        mask.data[v.index].value = s
    m = mats['Skin'].copy()
    m.name = 'Skin with scalp'
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    a_col = nt.nodes.new('ShaderNodeAttribute')
    a_col.attribute_name = 'Scalp'
    a_mask = nt.nodes.new('ShaderNodeAttribute')
    a_mask.attribute_name = 'StubbleMask'
    coord = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 650.0
    noise.inputs['Detail'].default_value = 1.0
    nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
    rng_ = nt.nodes.new('ShaderNodeMapRange')
    rng_.inputs['From Min'].default_value = .30
    rng_.inputs['From Max'].default_value = .70
    rng_.inputs['To Min'].default_value = .72
    rng_.inputs['To Max'].default_value = 1.16
    nt.links.new(noise.outputs['Fac'], rng_.inputs['Value'])
    sub = nt.nodes.new('ShaderNodeMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = 1.0
    nt.links.new(rng_.outputs['Result'], sub.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(sub.outputs['Value'], mul.inputs[0])
    nt.links.new(a_mask.outputs['Fac'], mul.inputs[1])
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.inputs[1].default_value = 1.0
    nt.links.new(mul.outputs['Value'], add.inputs[0])
    scale = nt.nodes.new('ShaderNodeVectorMath')
    scale.operation = 'SCALE'
    nt.links.new(a_col.outputs['Color'], scale.inputs[0])
    nt.links.new(add.outputs['Value'], scale.inputs['Scale'])
    nt.links.new(scale.outputs['Vector'], bsdf.inputs['Base Color'])
    keep = list(me.materials)
    me.materials.clear()
    me.materials.append(m)
    for extra in keep[1:]:
        me.materials.append(extra)


def bake_scalp_to_material_slots(G, step=.045):
    """The game export packs one flat colour per material slot into an atlas,
    so the smooth 'Scalp' colours (stubble, fade, under-hair, blush) become a
    small palette of slots.  Quantised in a gamma-like space so darks survive."""
    faceob = G['faceob']
    me = faceob.data
    attr = me.color_attributes.get('Scalp')
    if attr is None:
        return 0
    cols = [Vector(attr.data[i].color[:3]) for i in range(len(me.vertices))]
    skin = Vector(G['mats']['Skin'].diffuse_color[:3])
    bins = {}
    for poly in me.polygons:
        if poly.material_index != 0:
            continue
        c = sum((cols[i] for i in poly.vertices), Vector()) / len(poly.vertices)
        if (c - skin).length < .025:
            continue
        key = tuple(round(max(0, v) ** .5 / step) for v in c)
        bins.setdefault(key, []).append((poly.index, c))
    for key, items in bins.items():
        mean = sum((c for _, c in items), Vector()) / len(items)
        m = G['mat']('Skin tone %02d_%02d_%02d' % key, tuple(mean), .7)
        me.materials.append(m)
        slot = len(me.materials) - 1
        for idx, _ in items:
            me.polygons[idx].material_index = slot
    return len(bins)


# ======================================================================
#  Head mesh (3d-v2 turnarounds)
# ======================================================================
# The head is a smooth union of rounded volumes, in "E units" (E = eye line to
# chin) around O = (0, ear depth, eye height):
#   cranium   the V5 skull the hair was fitted to
#   face      a round lower face: full cheeks that stay wide down to the mouth
#   cheeks    baby-fat fullness (3/4 view)
#   chin      a small soft chin
#   nose      a small button nose on a soft bridge
# It is meshed by rays from a point inside the head, so the whole surface is
# smooth -- no flat face plane, creases or hollow cheeks.
# Measured on output/character-turnarounds/3d-v2 (wind, E = 59 px):
#   cheek half-width 0.92 E at the eyes, 0.87 at the mouth, 0.64 at -0.78 E,
#   0.45 at -0.95 E; nose tip 0.36 E and mouth 0.64 E under the eyes;
#   ear centre 1.47 E behind the forehead.


def _smin(a, b, k):
    h = np.clip(.5 + .5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _ellipsoid_d(P, c, r, tilt=0.0):
    """Approximate signed distance to a (tilted about X) ellipsoid."""
    q = P - np.asarray(c, dtype=float)
    if tilt:
        t = radians(tilt)
        y = q[:, 1] * cos(t) - q[:, 2] * sin(t)
        z = q[:, 1] * sin(t) + q[:, 2] * cos(t)
        q = np.stack([q[:, 0], y, z], axis=1)
    r = np.asarray(r, dtype=float)
    k0 = np.sqrt(((q / r) ** 2).sum(axis=1))
    k1 = np.sqrt(((q / (r * r)) ** 2).sum(axis=1))
    return np.where(k1 > 1e-9, k0 * (k0 - 1) / np.maximum(k1, 1e-9), -r.min())


EYE_POCKET = dict(depth=.020, wall=.012, margin=.004, dome=.62,
                  lid_front=.0001, lid_tuck=.0001, lid_band=.0045, lid_bulge=.0005, eye_back=.0010)   # E units / metres (lid_radius)


def _pocket(b, P):
    """Eye socket: depth 'a' inside the eye outline grown by 'm', soft walls
    of width 'wall' (all in E units)."""
    sg = b['side']
    u = (P[:, 0] - b['x']) / b['hw'] * sg
    uu = np.clip(1 - u * u, 0, None)
    zu = b['up'] * uu ** b['up_pow'] * (1 + b['up_skew'] * u) + b['tilt'] * u + b['m']
    zl = -b['low'] * uu ** b['low_pow'] * (1 + b['low_skew'] * u) + b['tilt'] * u - b['m']
    z = P[:, 2] - b['z']
    dist = np.minimum(np.minimum(zu - z, z - zl), (1 + b['mu'] - np.abs(u)) * b['hw'] * .5)
    w = np.clip(dist / b['wall'], 0, 1)
    w = w * w * (3 - 2 * w)
    return b['a'] * w * np.exp(-((P[:, 1] - b['y']) / b['sy']) ** 2)


def head_field(H, P):
    d = None
    for b in H['blobs']:
        if b.get('pocket'):
            d = d + _pocket(b, P)
            continue
        if b.get('relief'):
            # soft surface relief: a Gaussian dent (a > 0) or bump (a < 0)
            q = (P - np.asarray(b['c'], dtype=float)) / np.asarray(b['s'], dtype=float)
            d = d + b['a'] * np.exp(-(q * q).sum(axis=1))
            continue
        di = _ellipsoid_d(P, b['c'], b['r'], b.get('tilt', 0.0))
        if b.get('mirror'):
            c2 = (-b['c'][0], b['c'][1], b['c'][2])
            di = _smin(di, _ellipsoid_d(P, c2, b['r'], b.get('tilt', 0.0)), b.get('k', .15))
        d = di if d is None else _smin(d, di, b.get('k', .15))
    return d


def head_origin(G, S, ez):
    """O in internal coordinates: ear depth chosen so the V5 cranium front sits
    1.47 E in front of the ear (as on the sheet), eye height ez."""
    H = S['head']
    E = H['E']
    C = S['cranium']
    cx, cy, cz = C['center']
    ax, ay, az = C['axes']
    zf = ez - SEAT + .24 * E
    front = cy - ay * sqrt(max(0.0, 1 - ((zf - cz) / az) ** 2))
    return Vector((0.0, front + 1.47 * E, ez))


def _graded_angles(span, dense, ramp, step, low=.42):
    """Grid angles (degrees, -span/2 .. span/2) spaced 'step' apart inside
    the 'dense' interval and step / low outside, with smooth 'ramp'-wide
    transitions.  span 360: a closed ring of n angles (n divisible by 4,
    angle 0 at index n/2); otherwise both ends are included."""
    x = np.linspace(-span / 2, span / 2, 72001)

    def sm(v):
        v = np.clip(v, 0.0, 1.0)
        return v * v * (3 - 2 * v)
    a, b = dense
    rho = low + (1 - low) * sm((x - (a - ramp)) / ramp) * sm(((b + ramp) - x) / ramp)
    C = np.concatenate([[0.0], np.cumsum((rho[1:] + rho[:-1]) / 2 * np.diff(x))])
    if span >= 360:
        n = max(8, 4 * int(round(C[-1] / step / 4)))
        t = C[-1] * np.arange(n) / n
    else:
        n = max(3, int(round(C[-1] / step)) + 1)
        t = np.linspace(0.0, C[-1], n)
    return np.interp(t, C, x)


def build_head_mesh(G, S, ez):
    """Replace the old face loft with the new head surface; returns O."""
    import bmesh
    H = S['head']
    E = H['E']
    O = head_origin(G, S, ez)
    C = S['cranium']
    # the cranium blob reproduces the V5 skull in E units
    cx, cy, cz = C['center']
    ax, ay, az = C['axes']
    cran = dict(c=(0.0, (cy - O.y) / E, (cz + SEAT - O.z) / E), r=(ax / E, ay / E, az / E), k=.10)
    fdy = H.get('face_dy', 0.0)
    H = dict(H, blobs=[cran] + [dict(b, c=(b['c'][0], b['c'][1] + fdy, b['c'][2])) for b in H['blobs']])
    # eye sockets (round 6): carved where the eyes sit, so the eyes are set into the head
    Fe = S['face']['eye']
    pk = dict(EYE_POCKET, **S['head'].get('eye_pocket', {}))
    pockets = []
    for sg in (1, -1):
        x = sg * Fe['x'] / E
        ys = np.linspace(-2.2, -.3, 700)
        inside = head_field(H, np.stack([np.full_like(ys, x), ys, np.zeros_like(ys)], 1)) < 0
        pockets.append(dict(pocket=True, side=sg, x=x, z=0.0, y=float(ys[np.argmax(inside)]), hw=Fe['half_w'] / E,
                            up=Fe['up'] / E, low=Fe['low'] / E, up_pow=Fe['up_pow'], low_pow=Fe['low_pow'],
                            up_skew=Fe['up_skew'], low_skew=Fe['low_skew'], tilt=Fe['tilt'] / E,
                            m=pk['margin'], mu=.08, wall=pk['wall'], a=pk['depth'], sy=.25))
    H0 = H                                    # without sockets: the closed-eye surface
    H = dict(H, blobs=H['blobs'] + pockets)
    centre = np.array(H['centre'], dtype=float)
    # round 10 (triangle budget): the old 208 x 140 grid everywhere; now that
    # density only over the face (azimuth within 85 deg of the front,
    # elevation -72..+55 deg from the projection centre) and 0.42 of it at
    # the back, the crown and under the chin, which the hair and the collar
    # cover.  The column facing -Y stays at index 3N/4 (cut_mouth).
    az_, el_ = _graded_angles(360.0, (-85.0, 85.0), 30.0, 360.0 / 208), _graded_angles(180.0, (-72.0, 55.0), 15.0, 180.0 / 141)
    N = len(az_)
    az_ = np.radians(270.0 + az_[(np.arange(N) - N // 4) % N])
    el_ = np.radians(el_[1:-1])
    M = len(el_)
    A, L_ = np.meshgrid(az_, el_)
    D = np.stack([np.cos(L_) * np.cos(A), np.cos(L_) * np.sin(A), np.sin(L_)], axis=-1).reshape(-1, 3)
    D = np.vstack([D, [[0, 0, -1], [0, 0, 1]]])
    lo = np.zeros(len(D))
    hi = np.full(len(D), 4.0)
    for _ in range(36):
        mid = (lo + hi) / 2
        inside = head_field(H, centre + D * mid[:, None]) < 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    P = centre + D * ((lo + hi) / 2)[:, None]
    verts = [Vector((O.x + p[0] * E, O.y + p[1] * E, O.z + p[2] * E)) for p in P]
    lo0 = np.zeros(len(D))
    hi0 = np.full(len(D), 4.0)
    for _ in range(36):
        mid = (lo0 + hi0) / 2
        inside = head_field(H0, centre + D * mid[:, None]) < 0
        lo0 = np.where(inside, mid, lo0)
        hi0 = np.where(inside, hi0, mid)
    P0 = centre + D * ((lo0 + hi0) / 2)[:, None]
    verts0 = [Vector((O.x + p[0] * E, O.y + p[1] * E, O.z + p[2] * E)) for p in P0]
    faces = []
    for i in range(M - 1):
        for j in range(N):
            a = i * N + j
            b = i * N + (j + 1) % N
            faces.append((a, b, b + N, a + N))
    bot, top = M * N, M * N + 1
    for j in range(N):
        faces.append((bot, (j + 1) % N, j))
        faces.append((top, (M - 1) * N + j, (M - 1) * N + (j + 1) % N))
    G['HEAD_GRID'] = (M, N)
    # finer mesh around the eyes (round 7): the grid is ~5 mm, which made the
    # socket rim a faceted ring (its shading showed around the closed lid).
    # The quads there are cut into a 5 x 5 grid (~1 mm) and the new vertices
    # are projected onto the surface along their rays from the centre, for the
    # head and for the socket-free surface the closed lids lie on.  Grid
    # indices stay valid (new vertices come after the grid).
    bm = bmesh.new()
    for p in verts:
        bm.verts.new(p)
    bm.verts.ensure_lookup_table()
    for f in faces:
        bm.faces.new([bm.verts[i] for i in f])
    n0 = len(verts)
    # round 10 (triangle budget): only the socket's rim gets the fine mesh --
    # the faces where the carving starts (it is deeper inside, behind the
    # eye), plus one ring outside them -- not the whole rectangle around the eye
    dep = np.linalg.norm(np.asarray(P0) - np.asarray(P), axis=1) * E
    bm.verts.index_update()
    rim = set()
    for f in bm.faces:
        d = [dep[v.index] for v in f.verts]
        if max(d) > 2e-5 and min(d) < .0025:
            rim.add(f)
    ring = set(rim)
    for f in rim:
        for v in f.verts:
            for g in v.link_faces:
                if min(dep[w.index] for w in g.verts) < .0025:
                    ring.add(g)
    region = []
    for f in ring:
        c = f.calc_center_median()
        if c.y < O.y - .3 * E and ez - Fe['low'] - .006 < c.z < ez + Fe['up'] + .010 and \
                any(abs(c.x - sg * Fe['x']) < 1.3 * Fe['half_w'] for sg in (1, -1)):
            region.append(f)
    print('HEAD_MESH grid %dx%d carve max %.4f m, rim faces %d, refined %d' % (N, M, float(dep.max()), len(rim), len(region)))
    bmesh.ops.subdivide_edges(bm, edges=list({e for f in region for e in f.edges}), cuts=4, use_grid_fill=True)
    bm.verts.index_update()
    newv = [v for v in bm.verts if v.index >= n0]
    unc_new = []
    if newv:
        Dn = np.array([[(v.co.x - O.x) / E, (v.co.y - O.y) / E, (v.co.z - O.z) / E] for v in newv]) - centre
        Dn /= np.linalg.norm(Dn, axis=1)[:, None]

        def project(HH):
            lo_ = np.zeros(len(Dn))
            hi_ = np.full(len(Dn), 4.0)
            for _ in range(36):
                mid_ = (lo_ + hi_) / 2
                ins = head_field(HH, centre + Dn * mid_[:, None]) < 0
                lo_ = np.where(ins, mid_, lo_)
                hi_ = np.where(ins, hi_, mid_)
            return [Vector((O.x + p[0] * E, O.y + p[1] * E, O.z + p[2] * E))
                    for p in centre + Dn * ((lo_ + hi_) / 2)[:, None]]
        for v, p in zip(newv, project(H)):
            v.co = p
        unc_new = project(H0)
    polys = [[v.index for v in f.verts] for f in bm.faces]
    from mathutils.bvhtree import BVHTree
    G['UNCARVED_BVH'] = BVHTree.FromPolygons(verts0 + unc_new, polys)
    faceob = G['faceob']
    old = faceob.data
    me = bpy.data.meshes.new('Head refined')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(G['mats']['Skin'])
    faceob.data = me
    bpy.data.meshes.remove(old)
    return O


def _surface_y(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[0]
    return hit.y if hit is not None else None


def face_landmarks(G, S, O, bvh):
    """Feature positions on the new head (internal coordinates)."""
    H = S['head']
    E = H['E']
    Mo = S['mouth']
    ez = O.z
    L = dict(E=E, O=O, ez=ez)
    L['mouth_z'] = ez - Mo['z'] * E
    L['mouth_w'] = Mo['width'] * E
    L['mouth_y'] = _surface_y(bvh, 0.0, L['mouth_z'])
    nz = ez - H['nose_z'] * E
    tip = min((v.co for v in G['faceob'].data.vertices if abs(v.co.x) < .004 and abs(v.co.z - nz) < .25 * E),
              key=lambda c: c.y)
    L['nose'] = tip.copy()
    return L


def place_face_bones(G, L, bvh):
    """Move the facial bones onto the new landmarks (directions unchanged)."""
    bones = G['bones']
    E, O = L['E'], L['O']

    def put(name, pos):
        h, t, parent = bones[name]
        h, t = Vector(h), Vector(t)
        bones[name] = (pos, pos + (t - h), parent)
    mz, my = L['mouth_z'], L['mouth_y']
    put('face_lip_upper', Vector((0.0, my, mz + .05 * E)))
    put('face_lip_lower', Vector((0.0, my, mz - .08 * E)))
    put('face_nose', L['nose'].copy())
    for side, sg in (('l', 1), ('r', -1)):
        x = sg * .5 * L['mouth_w']
        put('face_smile_' + side, Vector((x, (_surface_y(bvh, x, mz) or my), mz)))
        x = sg * .62 * E
        z = O.z - .32 * E
        put('face_cheek_' + side, Vector((x, (_surface_y(bvh, x, z) or my), z)))
        x = sg * L['brow']['x']
        z = L['brow']['z']
        put('face_brow_' + side, Vector((x, (_surface_y(bvh, x, z) or my) - .007, z)))


MOUTH_OLD = ('Sculpted smile opening', 'Soft lower lip contour', 'Single rounded tooth row', 'Small tongue', 'Fang',
             'Upper lip line', 'Mouth cavity', 'Upper teeth', 'Tongue')
# mouth shapes (morph targets with the VRM / VRoid names; round 10 adds I U E O):
# opening half width, lower lip drop, upper lip lift (relative to 'A'),
# corners drawn out (+) / in (-), lips forward (x E), corners up (x E)
VISEMES = {'A': (1.00, 1.00, 1.00, .00, .000, .000),
           'I': (1.22, .30, .55, .10, .000, .022),
           'U': (.50, .40, .60, -.26, .035, .000),
           'E': (1.14, .58, .75, .06, .000, .010),
           'O': (.74, .92, .90, -.13, .020, .000)}


def mouth_line(S, L):
    """z of the closed mouth line at x (smile curve)."""
    mz, mw = L['mouth_z'], L['mouth_w']
    curve = S['mouth']['curve'] * L['E']

    def f(x):
        t = max(0.0, min(1.0, x / mw + .5))
        return mz + curve * (2 * t - 1) ** 2
    return f


def cut_mouth(G, S, L):
    """Split the head surface along the mouth line between the corners.  One
    grid row is snapped onto the line first.  Returns the upper and lower lip
    edges (vertex indices, corner to corner)."""
    import bmesh
    faceob = G['faceob']
    me = faceob.data
    M, N = G['HEAD_GRID']
    E, O = L['E'], L['O']
    line = mouth_line(S, L)
    hw = .5 * L['mouth_w']
    vs = me.vertices
    jf = (3 * N) // 4                                  # the column facing -Y
    front = [i for i in range(M) if vs[i * N + jf].co.y < O.y - .6 * E]
    im = min(front, key=lambda i: abs(vs[i * N + jf].co.z - line(0.0)))
    cols = [jf]
    for step in (1, -1):
        j = jf
        while abs(vs[im * N + (j + step) % N].co.x) < hw:
            j = (j + step) % N
            cols.append(j)
    cols = sorted(set(cols), key=lambda j: vs[im * N + j].co.x)
    jl = (cols[0] - 1) % N
    jr = (cols[-1] + 1) % N
    bvh = bvh_of(faceob)
    for j in cols:                                     # snap the row onto the mouth line
        v = vs[im * N + j]
        z = line(v.co.x)
        dz = z - v.co.z
        y = _surface_y(bvh, v.co.x, z)
        if y is not None:
            v.co = Vector((v.co.x, y, z))
        for di in (-1, 1):                             # neighbours follow halfway (even quads)
            w = vs[(im + di) * N + j]
            y2 = _surface_y(bvh, w.co.x, w.co.z + .5 * dz)
            if y2 is not None:
                w.co = Vector((w.co.x, y2, w.co.z + .5 * dz))
    me.update()
    chain = [im * N + jl] + [im * N + j for j in cols] + [im * N + jr]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    cv = [bm.verts[i] for i in chain]
    edges = []
    for a, b in zip(cv, cv[1:]):
        e = bm.edges.get((a, b))
        if e is not None:
            edges.append(e)
    pos = [v.co.copy() for v in cv]
    bmesh.ops.split_edges(bm, edges=edges)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    upper, lower = [], []
    for k, p0 in enumerate(pos):
        here = [v for v in bm.verts if (v.co - p0).length < 1e-7]
        if k in (0, len(pos) - 1) or len(here) < 2:
            upper.append(here[0].index)
            lower.append(here[0].index)
            continue
        def fz(v):
            fs = list(v.link_faces)
            return sum(f.calc_center_median().z for f in fs) / max(1, len(fs))
        here.sort(key=fz)
        lower.append(here[0].index)
        upper.append(here[-1].index)
    for i in set(upper[1:-1] + lower[1:-1]):            # a small crease where the lips meet
        bm.verts[i].co.y += .0007
    bm.to_mesh(me)
    bm.free()
    me.update()
    return dict(upper=upper, lower=lower)


def face_weights_v6(L, S, slit=None):
    """Head weights: upper / lower lip, nose, smile corners, cheeks and brows
    (round 7: no jaw bone -- the mouth opens with the morph target 'A')."""
    E, O = L['E'], L['O']
    line = mouth_line(S, L)
    hw = .5 * L['mouth_w'] / E
    nose = L['nose']
    B = L['brow']
    upper_ids = set(slit['upper'][1:-1]) if slit else set()
    lower_ids = set(slit['lower'][1:-1]) if slit else set()

    def f(p, idx=None):
        X, Y, Z = p.x / E, (p.y - O.y) / E, (p.z - O.z) / E
        Zl = (line(p.x) - O.z) / E
        ax = abs(X)
        front = smooth(-.55, -1.05, Y)
        inside = 1 - smooth(hw - .03, hw + .03, ax)
        h = lerp(.10, .004, inside)
        if idx in lower_ids:
            below = 1.0
        elif idx in upper_ids:
            below = 0.0
        else:
            below = smooth(Zl + .25 * h, Zl - h, Z)
        d = {}
        lipx = math.exp(-(X / (hw + .12)) ** 4) * front
        d['face_lip_upper'] = math.exp(-((Z - (Zl + .05)) / .06) ** 2) * lipx * .55 * (1 - below)
        d['face_lip_lower'] = math.exp(-((Z - (Zl - .08)) / .07) ** 2) * lipx * .25 * below
        Zn = (nose.z - O.z) / E
        d['face_nose'] = .8 * math.exp(-(X / .14) ** 2 - ((Z - Zn) / .18) ** 2) * front
        for side, sg in (('l', 1), ('r', -1)):
            for nm, cx_, cz_, sx, sz, k in (('smile', hw, Zl, .26, .24, .40),
                                             ('cheek', .62, -.32, .27, .28, .28),
                                             ('brow', B['x'] / E, (B['z'] - O.z) / E, .42, .18, .50)):
                d['face_' + nm + '_' + side] = math.exp(-((X - sg * cx_) / sx) ** 2 - ((Z - cz_) / sz) ** 2) * front * k
        total = sum(d.values())
        if total > .97:
            d = {k: v * .97 / total for k, v in d.items()}
            total = .97
        d['head'] = 1 - total
        d = dict(sorted(d.items(), key=lambda x: x[1], reverse=True)[:4])
        sm = sum(d.values())
        return {k: v / sm for k, v in d.items() if v > 1e-5}
    return f


def weight_head(G, L, S, slit):
    ob = G['faceob']
    ob.vertex_groups.clear()
    f = face_weights_v6(L, S, slit)
    groups = {}
    for v in ob.data.vertices:
        for name, w in f(v.co, v.index).items():
            g = groups.get(name)
            if g is None:
                g = groups[name] = ob.vertex_groups.new(name=name)
            g.add([v.index], w, 'REPLACE')


def build_mouth(G, S, L, bvh, slit):
    """Closed mouth = the lip lines along the slit.  The morph target 'A' (as in
    VRM / VRoid faces) parts the lips in a soft rounded opening and shows the
    cavity, the upper teeth and the tongue."""
    parts = G['parts']
    for ob in [o for o in parts if o.name.startswith(MOUTH_OLD)]:
        parts.remove(ob)
        bpy.data.objects.remove(ob, do_unlink=True)
    Mo = S['mouth']
    E = L['E']
    me = G['faceob'].data
    up = [me.vertices[i].co.copy() for i in slit['upper']]
    lo = [me.vertices[i].co.copy() for i in slit['lower']]
    n = len(up)
    G['mat']('Mouth line', Mo.get('colour', (.20, .065, .055)), .5)
    G['mat']('Lip soft', Mo.get('lip', (.78, .40, .34)), .55)
    G['mat']('Mouth inside', (.38, .085, .085), .6)
    G['mat']('Teeth', (.88, .86, .82), .4)
    G['mat']('Tongue', (.80, .33, .33), .5)
    f = face_weights_v6(L, S)
    w_up = lambda p: f(p, None) if p.z > L['mouth_z'] + .002 else {k: v for k, v in f(p + Vector((0, 0, .004)), None).items()}
    w_lo = lambda p: f(p - Vector((0, 0, .004)), None)
    th = Mo['thick'] * E

    def surf(x, z, fallback):
        y = _surface_y(bvh, x, z)
        return Vector((x, (y if y is not None else fallback) - .0008, z))
    # upper lip line: dark, thickest in the middle
    a_, b_ = [], []
    for k in range(n):
        t = k / (n - 1)
        q = up[k]
        h = th * (.30 + .70 * sin(pi * t))
        a_.append(Vector((q.x, q.y - .0008, q.z)))
        b_.append(surf(q.x, q.z + h, q.y))
    _ribbon(G, 'Upper lip line', a_, b_, 'Mouth line', w_up, .0, .0006)
    # lower lip line (moves with the jaw)
    a_, b_ = [], []
    for k in range(n):
        t = k / (n - 1)
        q = lo[k]
        h = th * .45 * (.25 + .75 * sin(pi * t))
        a_.append(surf(q.x, q.z - h, q.y))
        b_.append(Vector((q.x, q.y - .0008, q.z)))
    _ribbon(G, 'Sculpted smile opening', a_, b_, 'Mouth line', w_lo, .0, .0006)
    # soft lower lip stroke
    a_, b_ = [], []
    lw = Mo.get('lip_w', .55)
    mz, mw = L['mouth_z'], L['mouth_w']
    curve = Mo['curve'] * E
    for i in range(25):
        t = i / 24
        x = mw * lw * (t - .5)
        z = mz - Mo.get('lip_gap', .10) * E + curve * (2 * t - 1) ** 2 * lw * lw
        h = Mo.get('lip_th', .035) * E * sin(pi * t) ** .8 + .0002
        a_.append(surf(x, z - h / 2, lo[n // 2].y))
        b_.append(surf(x, z + h / 2, lo[n // 2].y))
    _ribbon(G, 'Soft lower lip contour', a_, b_, 'Lip soft', w_lo, .0, .0005)
    # cavity: a sack behind the slit (roof with the head, floor with the jaw)
    depth = .30 * E
    K = 8
    vs, fs, ws = [], [], []
    rim = up + lo[-2:0:-1]                  # loop: upper edge L->R, lower edge R->L
    rim_up = [True] * n + [False] * (n - 2)
    cx = sum((q.x for q in up), 0.0) / n
    zc = sum((q.z for q in up), 0.0) / n
    for k in range(K + 1):
        t = k / K
        for q, isup in zip(rim, rim_up):
            sh = 1 - .55 * t ** 1.3
            x = cx + (q.x - cx) * sh
            zoff = (.10 * E if isup else -.10 * E) * sin(pi * min(1.0, t * 1.4)) * (1 - .4 * t)
            z = zc + (q.z - zc) * sh + zoff
            y = q.y + .001 + depth * t
            vs.append(Vector((x, y, z)))
            ws.append(('up', t) if isup else ('lo', t))
    R = len(rim)
    for k in range(K):
        for i in range(R):
            a = k * R + i
            b = k * R + (i + 1) % R
            fs.append((a, b, b + R, a + R))
    vs.append(Vector((cx, up[n // 2].y + .001 + depth * 1.05, zc)))
    ws.append(('mid', 1.0))
    c = len(vs) - 1
    for i in range(R):
        fs.append((K * R + i, K * R + (i + 1) % R, c))
    cav = G['mesh']('Mouth cavity', vs, fs, 'Mouth inside', 'head')
    # upper teeth: a soft white band just behind the upper lip
    a_, b_ = [], []
    for k in range(n):
        t = k / (n - 1)
        if not .12 <= t <= .88:
            continue
        q = up[k]
        h = .032 * E * sin(pi * (t - .12) / .76) ** .5
        a_.append(Vector((q.x * .92, q.y + .0035, q.z - h)))
        b_.append(Vector((q.x * .92, q.y + .0040, q.z + .002)))
    teeth = _ribbon(G, 'Upper teeth', a_, b_, 'Teeth', 'head', .0, .0015)
    # tongue on the floor
    import bmesh
    tm = bpy.data.meshes.new('Tongue')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=1.0)
    for v in bm.verts:
        v.co = Vector((cx + v.co.x * .30 * L['mouth_w'], up[n // 2].y + .55 * depth + v.co.y * .45 * depth,
                       zc - .09 * E + v.co.z * .045 * E))
    bm.to_mesh(tm)
    bm.free()
    tob = bpy.data.objects.new('Tongue', tm)
    bpy.context.scene.collection.objects.link(tob)
    bpy.ops.object.select_all(action='DESELECT')
    tob.select_set(True)
    G['finish'](tob, 'Tongue', 'Tongue', 'head')
    # ---- mouth shapes: morph targets A I U E O (the VRM / VRoid set) ---------
    # One rule for all five.  The lips part in a soft rounded opening in the
    # middle of the mouth line (the corners stay closed): the lower lip drops,
    # the upper lip lifts a little and the chin follows about a third of the
    # way -- no hinged jaw.  Per shape the opening is wider or narrower and
    # taller or flatter, the corners are drawn out and up a little (い え) or
    # drawn in with the lips pushed forward (う お).
    hw = .5 * L['mouth_w']
    wo = min(Mo.get('open_w', .74) * hw, Mo.get('open_max', .17) * E)    # half width of the opening ('A')
    Dz = Mo.get('open_h', .80) * wo                                       # lower lip drop in the middle ('A')
    Uz = .16 * Dz                                                         # upper lip lift ('A')
    line = mouth_line(S, L)
    Oh = L['O']

    def prof(x, p, w):
        return max(0.0, 1 - (x / w) ** 2) ** p

    def delta(p, side=None, vis='A'):
        ws, ds, us, pull, fwd, cup = VISEMES[vis]
        w = min(wo * ws, .92 * hw)                 # the slit ends just past the corners
        D, Uu = Dz * ds, Uz * us
        zl = line(p.x)
        if side is None:
            side = 'lo' if p.z < zl else 'up'
        front = smooth(-.50, -1.0, (p.y - Oh.y) / E)
        rz = (p.z - zl) / E
        # corners out / in, lips forward, corners up: the whole mouth area moves
        area = math.exp(-(p.x / (1.7 * hw)) ** 4 - (rz / .34) ** 2)
        lips = math.exp(-(p.x / (1.25 * hw)) ** 4 - (rz / .20) ** 2)
        corner = math.exp(-((abs(p.x) - hw) / (.45 * hw)) ** 2 - (rz / .22) ** 2)
        extra = Vector((pull * p.x * area, -fwd * E * lips, cup * E * corner)) * front
        if side == 'lo':
            t = max(0.0, (zl - p.z) / E)
            lat = lerp(prof(p.x, .55, w), math.exp(-(p.x / (1.5 * w)) ** 2), smooth(0, .20, t))
            fall = lerp(1.0, .32, smooth(0, .40, t)) * (1 - smooth(.42, .80, t))
            return Vector((0, .35 * D * lat * smooth(.02, .30, t) * (1 - smooth(.42, .80, t)), -D * lat * fall)) * front + extra
        t = max(0.0, (p.z - zl) / E)
        lat = lerp(prof(p.x, .9, w), math.exp(-(p.x / (1.3 * w)) ** 2), smooth(0, .06, t))
        return Vector((0, 0, Uu * lat * (1 - smooth(0, .14, t)))) * front + extra
    up_ids, lo_ids = set(slit['upper'][1:-1]), set(slit['lower'][1:-1])
    face = G['faceob']
    sides = ['up' if v.index in up_ids else ('lo' if v.index in lo_ids else None) for v in face.data.vertices]
    set_shape_keys(face, {vis: [v.co + delta(v.co, s, vis) for v, s in zip(face.data.vertices, sides)] for vis in VISEMES})
    for o in parts:
        if o.name.startswith('Upper lip line'):
            set_shape_keys(o, {vis: [v.co + delta(v.co, 'up', vis) for v in o.data.vertices] for vis in VISEMES})
        elif o.name.startswith(('Sculpted smile opening', 'Soft lower lip contour')):
            set_shape_keys(o, {vis: [v.co + delta(v.co, 'lo', vis) for v in o.data.vertices] for vis in VISEMES})
    # cavity: rim rings follow their lip, deeper rings less; the tongue drops
    keys = {}
    for vis in VISEMES:
        tgt = []
        for j, v in enumerate(cav.data.vertices):
            if j < (K + 1) * R:
                k, i = divmod(j, R)
                q = rim[i]
                if rim_up[i]:
                    tgt.append(v.co + delta(q, 'up', vis) * (1 - .6 * k / K))
                else:
                    tgt.append(v.co + delta(q, 'lo', vis) * (1 - .35 * k / K))
            else:
                tgt.append(v.co + (delta(up[n // 2], 'up', vis) + delta(lo[n // 2], 'lo', vis)) * .35)
        keys[vis] = tgt
    set_shape_keys(cav, keys)
    keys = {}
    for vis in VISEMES:
        dt = delta(Vector((cx, lo[n // 2].y, zc - .02 * E)), 'lo', vis) * .55
        keys[vis] = [v.co + dt for v in tob.data.vertices]
    set_shape_keys(tob, keys)
    # the teeth narrow with the lips; for う and お they also go up and back
    # behind the pushed-out upper lip (a grey band showed in the small opening)
    hide = {'U': 1.0, 'O': .45}
    keys = {}
    for vis, (ws, ds, us, pull, fwd, cup) in VISEMES.items():
        k = hide.get(vis, 0.0)
        keys[vis] = [Vector((cx + (v.co.x - cx) * (1 + .85 * min(0.0, pull)), v.co.y + .0025 * k, v.co.z + .030 * E * k))
                     for v in teeth.data.vertices]
    set_shape_keys(teeth, keys)


def skin_material(G, S):
    """Warm, soft skin (sheet colours) with a little subsurface scattering."""
    sk = S.get('skin')
    m = G['mats']['Skin']
    if sk:
        m.diffuse_color = (*sk, 1)
    b = m.node_tree.nodes['Principled BSDF']
    if sk:
        b.inputs['Base Color'].default_value = (*sk, 1)
    b.inputs['Roughness'].default_value = .55
    # Christensen-Burley, not random walk: the eyelid is a thin sheet, and a
    # random walk through a sheet comes out lighter than through the head
    # (round 10: the closed lid showed its outline up close)
    b.subsurface_method = 'BURLEY'
    for name, val in (('Subsurface Weight', .22), ('Subsurface Scale', .006), ('Specular IOR Level', .32)):
        if name in b.inputs:
            b.inputs[name].default_value = val
    if 'Subsurface Radius' in b.inputs:
        b.inputs['Subsurface Radius'].default_value = (1.0, .42, .26)


# ======================================================================
#  Hair volume, flow and locks
# ======================================================================
class HairVolume:
    """Shell the locks lie on: a dome on a vertical skirt, widest at its rim.
    Layers (lam 0..1) interpolate from the scalp to the shell."""

    def __init__(self, H, scalp_bvh):
        self.H = H
        self.bvh = scalp_bvh
        self.c = V(*H['center'])
        self.edge_el = {k: self._solve_edge(k) for k in range(0, 361, 2)}
        self.rim_el = {}
        for k in range(0, 361, 2):
            h = direction(k, 0)
            req = self.shell_radius(h)
            fa = front_angle(self.c + h * req)
            zr = table(H['rim'], fa) + SEAT
            a = radians(k)
            zr += H['rim_noise'] * smooth(40, 70, fa) * (.010 * sin(3 * a + 1.3) + .006 * sin(7 * a + .4) + .004 * sin(11 * a + 2.1))
            self.rim_el[k] = degrees(atan2(zr - self.c.z, req))

    def shell_radius(self, d):
        s = self.H['shell']
        d = d.normalized()
        pw = s['power']
        ay = s['front'] if d.y < 0 else s['back']
        if d.z >= 0:
            return 1 / ((abs(d.x) / s['x']) ** pw + (abs(d.y) / ay) ** pw + (d.z / s['top']) ** pw) ** (1 / pw)
        hl = sqrt(d.x * d.x + d.y * d.y)
        if hl < 1e-6:
            return .05
        req = 1 / ((abs(d.x / hl) / s['x']) ** pw + (abs(d.y / hl) / ay) ** pw) ** (1 / pw)
        return req / hl

    def rim(self, az):
        az = az % 360
        k0 = int(az // 2) * 2
        return lerp(self.rim_el[k0], self.rim_el[min(360, k0 + 2)], (az - k0) / 2)

    def scalp(self, d):
        loc, n, _, dist = self.bvh.ray_cast(self.c, d.normalized(), 1.0)
        if loc is None:
            return None, None, None
        if n.dot(d) < 0:
            n = -n
        return loc, n.normalized(), dist

    def edge_z(self, fa):
        return table(self.H['edge'], fa) + SEAT

    def _solve_edge(self, az):
        lo, hi = -60.0, 89.0
        d0 = direction(az, 0)
        target = self.edge_z(front_angle(self.c + d0 * .2))
        for _ in range(28):
            mid = (lo + hi) / 2
            loc, _, _ = self.scalp(direction(az, mid))
            if loc is None or loc.z > target:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    def el_edge(self, az):
        az = az % 360
        k0 = int(az // 2) * 2
        return lerp(self.edge_el[k0], self.edge_el[min(360, k0 + 2)], (az - k0) / 2)

    @staticmethod
    def az_el(d):
        d = d.normalized()
        return degrees(atan2(d.y, d.x)), degrees(math.asin(max(-1, min(1, d.z))))

    def v_of(self, d):
        """0 at the rim, 1 at the top pole (negative below the rim)."""
        az, el = self.az_el(d)
        r = self.rim(az)
        return (el - r) / (90 - r)

    def _pt(self, d, lam=1.0):
        d = d.normalized()
        loc, n, dist = self.scalp(d)
        r = self.shell_radius(d)
        if dist is not None:
            r = dist + lam * (max(r, dist + .010) - dist)
        return self.c + d * r

    def surface(self, d, lam=1.0):
        d = d.normalized()
        v = self.v_of(d)
        if v < -.02:
            return None, None, v
        p = self._pt(d, lam)
        e = .01
        a = d.cross(Vector((0, 0, 1)))
        if a.length < 1e-4:
            a = Vector((1, 0, 0))
        a.normalize()
        b = d.cross(a).normalized()
        nn = (self._pt(d + a * e, lam) - p).cross(self._pt(d + b * e, lam) - p)
        if nn.dot(d) < 0:
            nn = -nn
        return p, nn.normalized(), v


CORE = .42      # depth of the dark core that backs up the gaps between locks


def part_mask(H, p):
    """1 on a visible part line at the front of the head, 0 elsewhere."""
    PS = H.get('part_skin')
    if not PS:
        return 0.0
    c = V(*H['center'])
    w = PS['width'] * (1 + PS['flare'] * smooth(c.z + .10, c.z + .03, p.z))
    across = math.exp(-((p.x - H['flow']['part_x']) / w) ** 2)
    along = smooth(c.y + PS['back'], c.y + PS['back'] - .05, p.y)
    return across * along


def build_under_volume(vol, G, name, material, top_z=None):
    """Dark cap: underside from the hairline out to the rim, then the shell."""
    N, M, U = 144, 30, 5
    vs, fs = [], []
    for i in range(U + M):
        for j in range(N):
            az = 360 * j / N
            rim_d = direction(az, vol.rim(az))
            pr = vol._pt(rim_d, CORE)
            if i < U:
                loc, n, dist = vol.scalp(direction(az, vol.el_edge(az)))
                pe = (loc - n * .003) if loc is not None else pr
                s = i / U
                p = pe.lerp(pr, s) - Vector((0, 0, .008 * sin(pi * s)))
            else:
                v = ((i - U) / (M - 1)) ** 1.2 * .99
                p = vol._pt(direction(az, lerp(vol.rim(az), 90, v)), CORE)
            if top_z is not None and p.z > top_z:
                p = vol.c + (p - vol.c) * max(.2, (top_z - vol.c.z) / max(1e-4, p.z - vol.c.z))
            m = part_mask(vol.H, p)
            if m > .02:                     # sink the core under the skin along the part
                d = (p - vol.c).normalized()
                loc, n, dist = vol.scalp(d)
                if loc is not None:
                    p = p.lerp(loc - n * .006, smooth(.02, .5, m))
            vs.append(p)
    pole = vol._pt(Vector((0, 0, 1)), CORE)
    if top_z is not None:
        pole.z = min(pole.z, top_z)
    vs.append(pole)
    pole = len(vs) - 1
    R = U + M
    for i in range(R - 1):
        for j in range(N):
            a = i * N + j
            b = i * N + (j + 1) % N
            fs.append((a, b, b + N, a + N))
    for j in range(N):
        fs.append(((R - 1) * N + j, (R - 1) * N + (j + 1) % N, pole))
    return G['mesh'](name, vs, fs, material, 'head')


class Flow:
    """Direction field on the hair: radial from a whorl, or away from a part."""

    def __init__(self, vol, H):
        self.vol = vol
        self.F = H['flow']
        if self.F['type'] == 'whorl':
            self.w = direction(*self.F['whorl'])
        else:
            self.w = direction(*self.F['crown'])

    def at(self, p, n):
        F = self.F
        d = (p - self.vol.c).normalized()
        away = d - self.w
        dist = away.length
        away -= n * away.dot(n)
        if away.length < 1e-6:
            away = Vector((0, -1, 0)) - n * n.dot(Vector((0, -1, 0)))
        away.normalize()
        fa = front_angle(p)
        if F['type'] == 'whorl':
            spin = n.cross(away)
            f = away + spin * F['swirl'] * math.exp(-(dist / .55) ** 2)
        elif F['type'] == 'down':
            side = 1.0 if p.x >= F.get('part_x', 0.0) else -1.0
            f = Vector((side * F.get('lateral', .1), 0, -1))
        else:
            # in front of the crown: away from the part line and down;
            # behind it: radial from the crown
            frontness = smooth(.10, -.06, p.y - self.vol.c.y)
            side = 1.0 if p.x >= F['part_x'] else -1.0
            lateral = Vector((side, 0, 0))
            f = (lateral * F['lateral'] + Vector((0, 0, -1)) * F['down'] + Vector((0, 1, 0)) * F.get('back', 0.0)) * frontness \
                + away * (1 - frontness)
        fwd = Vector((0, -1, -.25))
        fwd -= n * fwd.dot(n)
        f += fwd * F['fringe_pull'] * (1 - smooth(25, 75, fa))
        f -= n * f.dot(n)
        if f.length < 1e-6:
            f = away
        return f.normalized()


class Body:
    """Stack of ellipses (final z) the long hair must stay outside of."""

    def __init__(self, rings):
        self.rings = sorted(rings)

    def push(self, p, margin=.012):
        zf = p.z - SEAT
        rs = self.rings
        if zf < rs[0][0] or zf > rs[-1][0]:
            return p
        for (z0, rx0, ry0, c0), (z1, rx1, ry1, c1) in zip(rs, rs[1:]):
            if z0 <= zf <= z1:
                t = (zf - z0) / (z1 - z0)
                rx, ry, cy = lerp(rx0, rx1, t) + margin, lerp(ry0, ry1, t) + margin, lerp(c0, c1, t)
                break
        q = Vector((p.x, p.y - cy))
        r = sqrt((q.x / rx) ** 2 + (q.y / ry) ** 2)
        if r < 1:
            if r < 1e-6:
                q = Vector((0, 1))
                r = 1 / ry
            p = Vector((p.x / r, cy + q.y / r, p.z))
        return p


class LockBuilder:
    """Flat tapered locks.  Each lock grows out of the scalp to its own layer of
    the shell (crown locks outermost, so they cover the roots below), lies
    along that layer like a shingle (optionally wavy), leaves it at the rim or
    after its lie length, then flicks outward in a C-curl -- or, for long
    hair, falls under gravity outside the body."""
    K = 10                      # ring vertices (14 before round 10)
    DS = .006                   # path step (the shape is grown at this step)
    RING_LEN, RING_TURN = .013, 9.0      # round 10: a ring every 13 mm, sooner where the lock turns

    def __init__(self, vol, flow, H, rng, body=None):
        self.vol, self.flow, self.P, self.rng = vol, flow, H, rng
        self.body = body
        self.vs, self.fs, self.uv, self.tone = [], [], [], []
        self.items, self.vinfo, self.tag = [], [], None      # physics chains (round 6)
        self.count = 0
        self.stats = {'rim': 0, 'front': 0}

    def keep_out(self, p, margin):
        d = p - self.vol.c
        _, _, dist = self.vol.scalp(d)
        below_head = self.body is not None and p.z < 1.29 + SEAT
        if dist is not None and d.length < dist + margin and not below_head:
            p = self.vol.c + d.normalized() * (dist + margin)
        if self.body is not None:
            p = self.body.push(p)
        return p

    def path(self, root_d, kind, lam, start_dir=None, long_end=None):
        P, rng, DS = self.P, self.rng, self.DS
        vol = self.vol
        lie = rng.uniform(*P['lie'][kind])
        flick = rng.uniform(*P['flick'][kind])
        curl = rng.uniform(*P['curl'][kind])
        bend = rng.uniform(*P['bend']) * (P['bend_sign'] if 'bend_sign' in P else rng.choice([-1, 1]))
        grav = P['gravity'][kind]
        alpha = radians(rng.uniform(*P['rise_angle']))
        wave_amp, wave_len = P['wave']
        wave_phase = rng.uniform(0, 2 * pi) if wave_amp else 0.0
        steer = P.get('steer', 0.0)
        top_z = (P['hat_top'] + SEAT) if 'hat_top' in P else None
        loc, sn, dist = vol.scalp(root_d)
        fa_root = front_angle(loc)
        p = loc - sn * .004
        f = self.flow.at(loc, sn) if start_dir is None else start_dir - sn * start_dir.dot(sn)
        f = rotate(f.normalized(), sn, radians(rng.uniform(-P['jitter'], P['jitter'])))
        pts, frames = [p.copy()], [(sn.copy(), -f)]
        # rise out of the scalp to the layer
        H0 = max(.004, (vol._pt(root_d, lam) - loc).length) if P.get('rise_fixed') else None
        s = 0.0
        while s < .14:
            d = (p - vol.c).normalized()
            sl, sn, sd = vol.scalp(d)
            tgt = vol._pt(d, lam)
            Hh = H0 if H0 is not None else max(.004, (tgt - sl).length)
            h = (p - sl).dot(sn)
            if h >= Hh * .97 or (s > .01 and vol.v_of(d) < .0):
                break
            f -= sn * f.dot(sn)
            f.normalize()
            th = alpha + (pi / 2 - alpha) * smooth(0, 1, max(0, h) / Hh) ** .8
            dv = sn * cos(th) + f * sin(th)
            p = p + dv * DS
            s += DS
            pts.append(p.copy())
            frames.append((dv.copy(), (sn * sin(th) - f * cos(th)).normalized()))
        vis = len(pts) - 1
        # lie along the layer
        rise = P['rise'] * rng.uniform(.6, 1.2)
        off0 = rng.uniform(-.0015, .0015)
        n = sn
        s_lie = 0.0
        stable = P.get('stable_lie', False)
        base = p.copy()
        while s_lie < lie:
            q = (base if stable else p) + f * DS
            sp, nn_, vv = vol.surface(q - vol.c, lam)
            if sp is None or vv < .01:
                self.stats['rim'] += 1
                break
            if kind != 'fringe' and nn_.y < P['front_stop'] and s_lie > .02:
                self.stats['front'] += 1
                break
            q = sp + nn_ * (rise * (s_lie / lie) + off0)
            if top_z is not None and q.z > top_z:
                q.z = top_z
            nf = (sp - base) if stable else (q - p)
            base = sp
            nf -= nn_ * nf.dot(nn_)
            if nf.length > 1e-8:
                f = nf.normalized()
            if steer > 0:
                f = f + self.flow.at(sp, nn_) * steer
                f -= nn_ * f.dot(nn_)
                f.normalize()
            f = rotate(f, nn_, (bend + wave_amp * sin(2 * pi * s_lie / wave_len + wave_phase)) * DS)
            n = nn_
            p = q
            s_lie += DS
            pts.append(p.copy())
            frames.append((f.copy(), n.copy()))
        lie_end = len(pts) - 1
        out = (p - vol.c).normalized()
        axis = f.cross(out)
        if axis.length < 1e-6:
            axis = f.cross(Vector((0, 0, 1)))
        axis.normalize()
        if long_end is not None:
            # long hair: fall under strong gravity, outside the head and body
            L = P['long']
            ds = L['ds']
            k = 0
            while p.z > long_end + SEAT and k < 160:
                k += 1
                g = L['gravity'] * ds * max(0.0, 1 - max(0.0, -f.z))
                f = rotate(f, f.cross(Vector((0, 0, -1))), g)
                if 'split' in L and p.z < L['split_z'] + SEAT:
                    if fa_root < L['split']:
                        # over the shoulder, then straight down the front
                        target = Vector((0, -L['front'] * smooth(L['front_y'] - .03, L['front_y'], p.y), -1))
                    else:
                        target = Vector((-p.x * L['pull'], L['back'], -1))  # one curtain down the back
                    f = f.lerp(target.normalized(), .35).normalized()
                f = rotate(f, out, (wave_amp * .4 * sin(2 * pi * k * ds / wave_len + wave_phase)) * ds)
                f.normalize()
                q = self.keep_out(p + f * ds, P['gap'] + .004)
                moved = q - p
                if moved.length > 1e-7:
                    f = f.lerp(moved.normalized(), .5).normalized()   # slide along the body
                p = q
                radial = Vector((p.x, p.y - .02, 0))
                if radial.length > 1e-6:
                    radial.normalize()
                    if radial.y < .2:                       # face-framing hair: show its broad side
                        radial = (radial + Vector((0, -.8, 0))).normalized()
                    n = n.lerp(radial, .35)
                n = n - f * n.dot(f)
                if n.length < 1e-6:
                    n = out
                n.normalize()
                pts.append(p.copy())
                frames.append((f.copy(), n.copy()))
            steps = max(4, int(flick / DS))
        else:
            steps = max(4, int(flick / DS))
        for i in range(steps):
            u = (i + .5) / steps
            g = grav * DS * max(0.0, 1 - max(0.0, -f.z)) * (1 - u)
            f = rotate(f, f.cross(Vector((0, 0, -1))), g)
            f = rotate(f, axis, radians(curl) * (1.35 - .7 * u) / steps)
            f = rotate(f, out, -bend * DS * 1.2)
            dvec = p - vol.c
            _, _, sdist = vol.scalp(dvec)
            if sdist is not None:
                clear = dvec.length - sdist
                if clear < .022:
                    away = f.cross((p - vol.c).normalized())
                    if away.length > 1e-6:
                        f = rotate(f, away, radians(14) * (.022 - clear) / .022)
            f.normalize()
            p = self.keep_out(p + f * DS, P['gap'])
            n = n - f * n.dot(f)
            if n.length < 1e-6:
                n = out
            n.normalize()
            pts.append(p.copy())
            frames.append((f.copy(), n.copy()))
        return pts, frames, vis, lie_end

    def add(self, root_d, kind, lam, start_dir=None, long_end=None, width=None):
        P, rng = self.P, self.rng
        W = (width if width is not None else rng.uniform(*P['width'])) * (.8 + .25 * lam)
        TH = rng.uniform(*P['thick'])
        twist = radians(rng.uniform(-P['twist'], P['twist']))
        pts, frames, vis, lie_end = self.path(root_d, kind, lam, start_dir, long_end)
        if len(pts) < 6:
            return
        nr = len(pts) - 1
        t0 = max(vis / nr + .05, .85 * lie_end / nr) if long_end is None else max(vis / nr + .05, .80)
        if long_end is not None:
            twist = 0.0
        keep = self._rings(pts, frames, vis)
        self._skin([pts[i] for i in keep], [frames[i] for i in keep], W, TH, twist, rng.uniform(-.12, .12), vis / nr, t0,
                   .35 if long_end is None else .10, P.get('tip', 1.0),
                   P.get('cup', .14) * (.4 if long_end is not None else 1.0),
                   P.get('round', .8), P.get('under', .25), ts=[i / nr for i in keep])
        sl = [0.0]
        for a, b in zip(pts, pts[1:]):
            sl.append(sl[-1] + (b - a).length)
        it = dict(pts=pts, s=sl, L=sl[-1], group=self.tag or ('bang' if kind == 'fringe' else 'hang'), lam=lam, W=W,
                  TH=TH, x_root=pts[0].x)
        self.items.append(it)
        for j, i in enumerate(keep):
            self.vinfo.extend([(it, sl[i])] * (1 if j == len(keep) - 1 else self.K))
        self.count += 1

    def _rings(self, pts, frames, vis):
        """Path points that get a ring (round 10, triangle budget): one every
        RING_LEN, sooner where the lock bends or rolls more than RING_TURN
        degrees; the root, the end of the rise and the last two always."""
        keep = [0]
        run = turn = 0.0
        last = len(pts) - 1
        for i in range(1, last):
            run += (pts[i] - pts[i - 1]).length
            turn += max(degrees(frames[i - 1][0].angle(frames[i][0], 0.0)), degrees(frames[i - 1][1].angle(frames[i][1], 0.0)))
            if i in (vis, last - 1) or run >= self.RING_LEN - 1e-9 or turn >= self.RING_TURN:
                keep.append(i)
                run = turn = 0.0
        keep.append(last)
        return keep

    def _skin(self, pts, frames, W, TH, twist, shift, tv, t0, narrow=.35, tip=1.0, cupk=.14,
              round_=.8, under=.25, ts=None):
        K = self.K
        base = len(self.vs)
        nr = len(pts)
        ts = ts or [i / (nr - 1) for i in range(nr)]
        for i in range(nr):
            t = ts[i]
            if i == nr - 1:
                self.vs.append(pts[i])
                self.uv.append((1.0, .5))
                continue
            f, n = frames[i]
            a = f.cross(n)
            if a.length < 1e-8:
                a = f.cross(Vector((0, 0, 1)))
            a.normalize()
            n = a.cross(f).normalized()
            ang = twist * t * t
            a2 = rotate(a, f, ang)
            n2 = rotate(n, f, ang)
            full = .45 + .55 * smooth(0, max(.02, tv), t)
            k = (t - tv) / max(.05, 1 - tv)
            k0 = (t0 - tv) / max(.05, 1 - tv)
            if t <= tv:
                taper = 1.0
            elif t < t0:
                taper = 1 - narrow * k ** 1.2
            else:
                taper = (1 - narrow * k0 ** 1.2) * ((1 - t) / (1 - t0)) ** tip
            w = W * full * taper
            th = TH * (.6 + .4 * full) * max(.12, taper ** .6)
            cup = cupk * w
            for kk in range(K):
                ang2 = 2 * pi * kk / K
                uu, vv = cos(ang2), sin(ang2)
                x = .5 * w * uu
                y = (th * .5 * vv ** round_ if vv > 0 else th * under * vv) - cup * (uu * uu - .35)
                self.vs.append(pts[i] + a2 * x + n2 * y)
                self.uv.append((t, kk / K))
        for i in range(nr - 2):
            for kk in range(K):
                a = base + i * K + kk
                b = base + i * K + (kk + 1) % K
                self.fs.append((a, a + K, b + K, b))
                top = sin(2 * pi * (kk + .5) / K) > 0
                self.tone.append(self._tone((ts[i] + ts[i + 1]) / 2, top, shift))
        last = base + (nr - 2) * K
        tip = base + (nr - 1) * K
        for kk in range(K):
            self.fs.append((last + (kk + 1) % K, last + kk, tip))
            self.tone.append(self._tone(1, sin(2 * pi * (kk + .5) / K) > 0, shift))
        self.fs.append(tuple(base + kk for kk in range(K)))
        self.tone.append(0)

    @staticmethod
    def _tone(t, top, shift):
        x = (.08 + .22 * t) if not top else (.28 + .58 * smooth(0, .9, t))
        return max(0, min(6, round(6 * (x + shift))))


# ======================================================================
#  Materials
# ======================================================================
def hair_material(G, name, color, sheen, rough=.38, spec=.42, ao_min=.18):
    """Strand bands along each lock (UV U runs root->tip), darker crevices,
    narrow tinted anisotropic highlight.  The export keeps the flat tone."""
    m = G['mat'](name, color, rough)
    nt = m.node_tree
    L = nt.links.new
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Specular IOR Level'].default_value = spec
    if 'Specular Tint' in bsdf.inputs:
        bsdf.inputs['Specular Tint'].default_value = (*sheen, 1)
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UVMap'
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 42.0
    wave.inputs['Distortion'].default_value = 2.5
    wave.inputs['Detail'].default_value = 2.0
    L(uv.outputs['UV'], wave.inputs['Vector'])
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 6.0
    L(uv.outputs['UV'], noise.inputs['Vector'])
    mixf = nt.nodes.new('ShaderNodeMath')
    mixf.operation = 'MULTIPLY'
    L(wave.outputs['Fac'], mixf.inputs[0])
    L(noise.outputs['Fac'], mixf.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .05
    ramp.color_ramp.elements[0].color = (*[c * .55 for c in color], 1)
    ramp.color_ramp.elements[1].position = .55
    lift = min(1.45, 1 / max(1e-4, max(color)))
    ramp.color_ramp.elements[1].color = (*[c * lift for c in color], 1)
    L(mixf.outputs['Value'], ramp.inputs['Fac'])
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.samples = 8
    ao.inputs['Distance'].default_value = .03
    occ = nt.nodes.new('ShaderNodeMapRange')
    occ.inputs['To Min'].default_value = ao_min
    occ.inputs['To Max'].default_value = 1.0
    L(ao.outputs['AO'], occ.inputs['Value'])
    shade = nt.nodes.new('ShaderNodeVectorMath')
    shade.operation = 'SCALE'
    L(ramp.outputs['Color'], shade.inputs[0])
    L(occ.outputs['Result'], shade.inputs['Scale'])
    L(shade.outputs['Vector'], bsdf.inputs['Base Color'])
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = .8
        tan = nt.nodes.new('ShaderNodeTangent')
        tan.direction_type = 'UV_MAP'
        tan.uv_map = 'UVMap'
        L(tan.outputs['Tangent'], bsdf.inputs['Tangent'])
    return m


def set_uv(ob, uv):
    me = ob.data
    layer = me.uv_layers.new(name='UVMap') if not me.uv_layers else me.uv_layers[0]
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uv[me.loops[li].vertex_index]


def long_weight(p):
    """Long hair: head -> hair_01 -> hair_02 down the sides, hair_back_* behind."""
    zf = p.z - SEAT
    side = 'l' if p.x >= 0 else 'r'
    back = smooth(.07, .02, abs(p.x)) * smooth(.02, .08, p.y)
    up = smooth(1.40, 1.20, zf)
    low = smooth(1.12, .86, zf)
    w = {}

    def add(name, v):
        if v > 1e-4:
            w[name] = w.get(name, 0) + v
    add('head', 1 - up)
    add('hair_01_' + side, up * (1 - low) * (1 - back))
    add('hair_02_' + side, up * low * (1 - back))
    add('hair_back_01', up * (1 - low) * back)
    add('hair_back_02', up * low * back)
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


# ======================================================================
#  Hair cards (realistic strands for Lightning and Ice)
# ======================================================================
# Round 6: the sculpted clumps read as greasy, unwashed hair.  The girls' hair
# is now made of hair cards, as in games: thin strips that follow the same
# guide curves (and bone chains), each mapped to one row of a strand texture
# generated here -- thousands of fine tapered strands with alpha.  Inner layers
# use dense, darker rows; the outer layers airy rows with uneven tips; bangs
# and face-framing locks pointed rows.  Strands run along U (root -> tip).
STRAND_ROWS = [  # strands, width px, length range, wave px, tip taper, darkness, edge margin
    dict(n=520, w=(1.8, 2.8), L=(.94, 1.0), wave=(0, 1.2), taper=.20, dark=.90, edge=.05, even=1.2),   # 0 dense inner
    dict(n=460, w=(1.6, 2.6), L=(.90, 1.0), wave=(.5, 2.0), taper=.25, dark=.92, edge=.05, even=1.3),  # 1 dense
    dict(n=360, w=(1.4, 2.4), L=(.82, 1.0), wave=(.5, 2.5), taper=.30, dark=.86, edge=.08, even=1.6),  # 2 medium
    dict(n=300, w=(1.3, 2.2), L=(.70, 1.0), wave=(.5, 3.0), taper=.35, dark=.93, edge=.10),  # 3 medium, uneven tips
    dict(n=220, w=(1.2, 2.0), L=(.60, 1.0), wave=(1.0, 3.5), taper=.40, dark=1.0, edge=.14),  # 4 airy outer
    dict(n=150, w=(1.1, 1.8), L=(.55, 1.0), wave=(1.0, 4.0), taper=.45, dark=1.0, edge=.18),  # 5 wispy outer
    dict(n=260, w=(1.3, 2.2), L=(.45, 1.0), wave=(.5, 2.5), taper=.50, dark=.95, edge=.12),  # 6 pointed (bangs)
    dict(n=70, w=(1.0, 1.6), L=(.50, 1.0), wave=(2.0, 6.0), taper=.50, dark=1.0, edge=.25)]  # 7 flyaways


def _smooth_np(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def strand_atlas(size=2048, seed=7):
    """Alpha and brightness of the strand atlas (row 0 at the bottom, as Blender
    stores pixels).  Each of the 8 rows is one card type."""
    rows = len(STRAND_ROWS)
    rng = np.random.default_rng(seed)
    hr = size // rows
    A = np.zeros((size, size), np.float32)
    Cc = np.zeros((size, size), np.float32)
    xs = np.arange(size)
    for r, sp in enumerate(STRAND_ROWS):
        y0 = r * hr
        for _ in range(sp['n']):
            e = sp.get('even', 2.2)                  # beta shape: low = strands spread evenly across the card
            yc = (.5 + (rng.beta(e, e) - .5) * (1 - sp['edge'])) * hr
            L = rng.uniform(*sp['L']) * size
            start = rng.uniform(0, .02) * size
            u = xs[(xs >= start) & (xs < min(size, start + L))]
            t = (u - start) / L
            yy = (yc + rng.uniform(*sp['wave']) * np.sin(rng.uniform(.6, 2.2) * 2 * pi / size * u + rng.uniform(0, 2 * pi))
                  + rng.uniform(-.03, .03) * hr * t)
            w = rng.uniform(*sp['w']) * (1 - .75 * _smooth_np(1 - sp['taper'], 1.0, t))
            b = float(np.clip(rng.normal(1.0, .16), .55, 1.45))
            base = np.floor(yy).astype(int)
            for dy in range(-3, 4):
                yi = base + dy
                d = (yi + .5 - yy) / np.maximum(.35, w * .5)
                a = np.exp(-d * d)
                ok = (yi >= 0) & (yi < hr)
                np.add.at(A, (y0 + yi[ok], u[ok]), a[ok])
                np.add.at(Cc, (y0 + yi[ok], u[ok]), a[ok] * b)
        Cc[y0:y0 + hr] *= sp['dark']
    alpha = 1 - np.exp(-1.35 * A)
    bright = np.where(A > 1e-4, Cc / np.maximum(A, 1e-6), .8)
    uu = xs / size
    bright = bright * (.68 + .32 * _smooth_np(0, .18, uu))[None, :]        # root shadow
    alpha = alpha * (1 - .25 * _smooth_np(.92, 1.0, uu))[None, :]           # soft tip fade
    alpha = alpha * (.15 + .85 * _smooth_np(0, .06, uu))[None, :]           # roots fade into the layer below
    return alpha, bright


def hair_card_material(G, title, H):
    """Strand atlas (tinted with the hair colours) + card material.  The PNG is
    written to <kind>/Textures and packed; the export keeps this material."""
    import pathlib
    Cd = H['clumps']['cards']
    alpha, bright = strand_atlas(Cd.get('texture', 2048), Cd.get('seed', 7))
    dark, light = np.array(H['colors']['dark']), np.array(H['colors']['light'])
    k = np.clip((bright - .45) / .9, 0, 1)[..., None]
    rgb = dark[None, None, :] * (1 - k) + light[None, None, :] * k
    px = np.dstack([rgb, alpha[..., None]]).astype(np.float32)
    px[..., :3] = np.where(px[..., :3] <= .0031308, px[..., :3] * 12.92, 1.055 * np.power(px[..., :3], 1 / 2.4) - .055)
    size = px.shape[0]
    name = 'T_%s_HairStrands' % title
    im = bpy.data.images.new(name, width=size, height=size, alpha=True)
    im.colorspace_settings.name = 'sRGB'
    im.pixels.foreach_set(px.ravel())
    folder = pathlib.Path(G['OUT']) / G['KIND'] / 'Textures'
    folder.mkdir(parents=True, exist_ok=True)
    im.filepath_raw = str(folder / (name + '.png'))
    im.file_format = 'PNG'
    im.save()
    im.pack()
    m = bpy.data.materials.new('M_%s_Hair' % title)
    m.use_nodes = True
    m.diffuse_color = (*[float(v) for v in .5 * (dark + light)], 1)
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = im
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UVMap'
    nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    bsdf.inputs['Roughness'].default_value = Cd.get('rough', .42)
    bsdf.inputs['Specular IOR Level'].default_value = Cd.get('spec', .45)
    if 'Specular Tint' in bsdf.inputs:
        bsdf.inputs['Specular Tint'].default_value = (*H['sheen'], 1)
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = .75
        tan = nt.nodes.new('ShaderNodeTangent')
        tan.direction_type = 'UV_MAP'
        tan.uv_map = 'UVMap'
        nt.links.new(tan.outputs['Tangent'], bsdf.inputs['Tangent'])
    tl = Cd.get('translucent', 0.0)
    if tl > 0:
        # Cycles-only output: light hair lets some light through (in Unreal:
        # shading model Two Sided Foliage).  The plain Principled BSDF stays
        # on the 'All' output, which is what the FBX export reads.
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        out.target = 'ALL'
        b2 = nt.nodes.new('ShaderNodeBsdfPrincipled')
        for k in ('Roughness', 'Specular IOR Level', 'Specular Tint', 'Anisotropic'):
            if k in bsdf.inputs and k in b2.inputs:
                b2.inputs[k].default_value = bsdf.inputs[k].default_value
        nt.links.new(tex.outputs['Color'], b2.inputs['Base Color'])
        if 'Anisotropic' in b2.inputs:
            nt.links.new(tan.outputs['Tangent'], b2.inputs['Tangent'])
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
        nt.links.new(tex.outputs['Color'], tr.inputs['Color'])
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = tl
        nt.links.new(b2.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        cut = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Alpha'], cut.inputs[0])
        nt.links.new(clear.outputs[0], cut.inputs[1])
        nt.links.new(mix.outputs[0], cut.inputs[2])
        o2 = nt.nodes.new('ShaderNodeOutputMaterial')
        o2.target = 'CYCLES'
        nt.links.new(cut.outputs[0], o2.inputs['Surface'])
        o2.is_active_output = True
    for attr, val in (('surface_render_method', 'DITHERED'), ('blend_method', 'HASHED')):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    m.use_backface_culling = False
    m['keep_texture'] = True                 # the game export keeps this material and its texture
    G['mats'][m.name] = m
    return m


# ======================================================================
#  Sculpted clump hair with physics chains (Lightning, Ice)
# ======================================================================
# Round 4 laid the girls' hair on one smooth shell and it read as a helmet.
# Their hair is now built from clumps, like the 3d-v2 sheets:
#   * a clump is a bundle of 2-3 rounded strands on one guide curve; the
#     strands overlap at the root and part toward the tips (uneven lengths);
#   * guides run between an inner hull (the skull) and an outer envelope
#     measured on the sheets (Lightning: a big round bob, widest at the
#     cheeks; Ice: hair spreading from under the hat, then falling to the
#     hips), wave in S-curves and end in flips (bob) or long tapered tips;
#   * Lightning's side hair is tucked behind the ears (the sheets show them);
#   * every clump hangs from a bone chain hair_<group>_NN that Unreal can
#     simulate (AnimDynamics, Kawaii Physics, rigid bodies).  Vertices are
#     weighted root -> tip along their chain, blended with the neighbouring
#     chain and with the head near the roots (max 4 influences).
OLD_HAIR_BONES = ('hair_01_l', 'hair_02_l', 'hair_01_r', 'hair_02_r', 'hair_back_01', 'hair_back_02')


def signed_front_angle(p, cy):
    """0 at the front, +90 character's left (+X), +-180 back, -90 right."""
    return degrees(atan2(p.x, -(p.y - cy)))


def resample(pts, ds):
    """Points every ds along the polyline (first and last kept)."""
    out = [pts[0].copy()]
    need = ds
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        if seg < 1e-9:
            continue
        pos = 0.0
        while seg - pos >= need:
            pos += need
            out.append(a.lerp(b, pos / seg))
            need = ds
        need -= seg - pos
    if (out[-1] - pts[-1]).length > ds * .3:
        out.append(pts[-1].copy())
    else:
        out[-1] = pts[-1].copy()
    return out


class Sections:
    """Closed surface from horizontal superellipse sections around a centre c:
    rows (dz, X, Yf, Yb) = height above c, half-width, front and back reach
    (metres).  Below the lowest row the last section continues straight down.
    radius(d) = distance from c to the surface along d (table lookup)."""
    RES = 2.0

    def __init__(self, c, rows, power=2.2, cap=.06):
        self.c = c.copy()
        rows = sorted(rows)
        lo = rows[0]
        # rounded closing cap under the lowest section
        rows = [(lo[0] - cap * (1 - cos(a)), lo[1] * max(.05, sin(a)), lo[2] * max(.05, sin(a)),
                 lo[3] * max(.05, sin(a))) for a in (.25, .6, 1.0, 1.3)] + rows
        rows = sorted(rows)
        self.bottom = rows[0][0]
        self.top = rows[-1][0]
        fx = mono_cubic([(r[0], r[1]) for r in rows])
        ff = mono_cubic([(r[0], r[2]) for r in rows])
        fb = mono_cubic([(r[0], r[3]) for r in rows])
        self.z0 = rows[0][0] - .8
        zz = np.arange(self.z0, self.top + .002, .001)
        cz = np.clip(zz, rows[0][0], self.top)
        self.X = np.array([max(.002, fx(z)) for z in cz])
        self.F = np.array([max(.002, ff(z)) for z in cz])
        self.B = np.array([max(.002, fb(z)) for z in cz])
        self.n = len(zz)
        self.pw = power
        az = np.radians(np.arange(-180, 180 + self.RES, self.RES))
        el = np.radians(np.arange(-90, 90 + self.RES, self.RES))
        A, L = np.meshgrid(az, el, indexing='ij')
        D = np.stack([np.cos(L) * np.cos(A), np.cos(L) * np.sin(A), np.sin(L)], -1).reshape(-1, 3)
        lo = np.zeros(len(D))
        hi = np.full(len(D), 1.2)
        for _ in range(32):
            mid = (lo + hi) / 2
            ins = self.inside_np(D * mid[:, None])
            lo = np.where(ins, mid, lo)
            hi = np.where(ins, hi, mid)
        self.R = ((lo + hi) / 2).reshape(A.shape)

    def inside_np(self, q):
        i = np.clip(np.round((q[:, 2] - self.z0) / .001).astype(int), 0, self.n - 1)
        Y = np.where(q[:, 1] < 0, self.F[i], self.B[i])
        v = (np.abs(q[:, 0]) / self.X[i]) ** self.pw + (np.abs(q[:, 1]) / Y) ** self.pw
        return (v < 1) & (q[:, 2] <= self.top) & (q[:, 2] >= self.bottom)

    def hradius(self, u, dz):
        """Horizontal distance from the hair axis to the surface at height dz
        in the horizontal direction u (radians from +X toward +Y)."""
        i = max(0, min(self.n - 1, int(round((dz - self.z0) / .001))))
        cu, su = cos(u), sin(u)
        Y = self.F[i] if su < 0 else self.B[i]
        return 1.0 / ((abs(cu) / self.X[i]) ** self.pw + (abs(su) / Y) ** self.pw) ** (1.0 / self.pw)

    def radius(self, d):
        L = d.length
        az = degrees(atan2(d.y, d.x))
        el = degrees(math.asin(max(-1.0, min(1.0, d.z / max(1e-9, L)))))
        fa, fe = (az + 180) / self.RES, (el + 90) / self.RES
        R = self.R
        i0 = max(0, min(R.shape[0] - 2, int(fa)))
        j0 = max(0, min(R.shape[1] - 2, int(fe)))
        u, v = fa - i0, fe - j0
        return ((R[i0, j0] * (1 - u) + R[i0 + 1, j0] * u) * (1 - v) +
                (R[i0, j0 + 1] * (1 - u) + R[i0 + 1, j0 + 1] * u) * v)


def cranium_rows(S, c, off=.004):
    """Inner hull: the skull ellipsoid (plus off), continued straight down
    below its equator."""
    C = S['cranium']
    (cx, cy, cz), (ax, ay, az) = C['center'], C['axes']
    base = cz + SEAT - c.z
    shift = c.y - cy
    rows = []
    for k in range(17):
        t = k / 16
        s = sqrt(max(0.0, 1 - t * t))
        rows.append((base + az * t, ax * s + off, max(.003, ay * s + off + shift), max(.003, ay * s + off - shift)))
    for dz, k in ((-.10, .97), (-.20, .86), (-.28, .72)):
        rows.append((base + dz, ax * k + off, ay * k + off + shift, ay * k + off - shift))
    return rows


class ClumpHair:
    """Guides, sculpted strands, bone chains and weights for one hairstyle
    (STYLES[kind]['hair']['clumps'])."""
    DS = .006

    def __init__(self, G, S, vol, flow, rng, body=None):
        self.G, self.S = G, S
        self.H = S['hair']
        self.C = C = self.H['clumps']
        self.vol, self.flow, self.rng, self.body = vol, flow, rng, body
        self.c = vol.c.copy()
        self.env = Sections(self.c, C['envelope'], C.get('power', 2.2))
        self.inner = Sections(self.c, cranium_rows(S, self.c), 2.0)
        self.top_z = (self.H['hat_top'] + SEAT) if 'hat_top' in self.H else None
        self.items = []
        self.ear = None
        if 'tuck' in C:
            T = C['tuck']
            O = G['HEAD_O']
            Ea = S['ear']
            self.ear = dict(x=T.get('x', .09), y=O.y + Ea.get('dy', 0.0) + .55 * Ea['width'] + T.get('margin', .010),
                            z_top=O.z - Ea['dz'] + .5 * Ea['height'] + T.get('above', .012))

    # ---------------------------------------------------------- surfaces
    def layer(self, d, lam):
        d = d.normalized()
        ri = self.inner.radius(d)
        loc, n, dist = self.vol.scalp(d)
        if dist is not None:
            ri = max(ri, dist + .003)
        ro = max(self.env.radius(d), ri + self.C.get('min_thick', .010))
        return self.c + d * (ri + lam * (ro - ri))

    def keep_out(self, p, margin=.004):
        d = p - self.c
        _, _, dist = self.vol.scalp(d)
        if dist is not None and d.length < dist + margin:
            p = self.c + d.normalized() * (dist + margin)
        if self.body is not None:
            p = self.body.push(p, self.C.get('body_gap', .012))
        return p

    def tuck_push(self, q):
        """Keep hair behind the ear: above the ear the allowed front edge
        slopes forward (a ramp the hair slides back along), from the ear top
        down it is the ear's back edge."""
        T = self.ear
        if T is None or abs(q.x) < T['x']:
            return q
        ramp = T.get('ramp', .07)
        y_min = T['y'] - ramp * smooth(T['z_top'], T['z_top'] + ramp, q.z) - 9 * smooth(T['z_top'] + ramp, T['z_top'] + ramp + .001, q.z)
        if q.y >= y_min:
            return q
        w = smooth(.09, .14, abs(q.x))
        return Vector((q.x, lerp(q.y, y_min, w), q.z))

    def flow_at(self, p, n):
        """Hair direction: the shared flow (away from the part / crown), turned
        backward on the sides ('sweep_back': degrees by front angle) so the
        hair passes over and behind the ears in one diagonal stroke."""
        f = self.flow.at(p, n)
        sb = self.C.get('sweep_back')
        if sb:
            hi = self.C.get('sweep_top', .10)
            ang = radians(table(sb, front_angle(p))) * smooth(self.c.z + hi, self.c.z + hi - .08, p.z)
            side = n.cross(f)
            if ang > 1e-4 and side.length > 1e-6:
                f = rotate(f, n, ang if side.y >= 0 else -ang)
        return f

    def tuck_steer(self, p):
        T = self.ear
        if T is None or abs(p.x) < T['x'] or p.y > T['y'] + .03:
            return Vector()
        return Vector((0, 1.8 * smooth(T['z_top'] + .07, T['z_top'], p.z), 0))

    # ---------------------------------------------------------- guides
    def rise(self, root_d, f0, lam, P, z_stop=-9.0):
        vol, c, DS = self.vol, self.c, self.DS
        loc, sn, dist = vol.scalp(root_d)
        if loc is None:
            return None, None
        p = loc - sn * .002
        f = (f0 - sn * f0.dot(sn)) if f0 is not None else self.flow.at(loc, sn)
        if f.length < 1e-6:
            f = self.flow.at(loc, sn)
        f.normalize()
        pts = [p.copy()]
        Hh = max(.003, (self.layer(root_d, lam) - loc).length)
        alpha = radians(min(75.0, max(self.rng.uniform(*P.get('rise_angle', (18, 35))), 10 + 900 * max(0.0, Hh - .03))))
        for _ in range(60):
            if p.z < z_stop:
                break
            d = (p - c).normalized()
            sl, n2, _ = vol.scalp(d)
            if sl is None:
                break
            h = (p - sl).dot(n2)
            if h >= Hh * .95:
                break
            f -= n2 * f.dot(n2)
            f.normalize()
            th = alpha + (pi / 2 - alpha) * smooth(0, 1, max(0.0, h) / Hh) ** .8
            p = p + (n2 * cos(th) + f * sin(th)) * DS
            pts.append(p.copy())
        return pts, f

    def walk(self, pts, f, lam, z_end, P, tuck=True):
        """Run along layer lam (flow-steered, swelling in and out, tucked
        behind the ears) until below z_end.  P['lam_end'] / P['settle']: the
        layer eases to lam_end over the first 'settle' metres (bangs settle
        onto the forehead)."""
        c, DS = self.c, self.DS
        p = pts[-1]
        steer = P.get('steer', .35)
        sw_a, sw_l = P.get('swell', (0.0, .1))
        ph = self.rng.uniform(0, 2 * pi)
        bias = Vector(P.get('bias', (0, 0, 0)))
        lam_end, settle = P.get('lam_end', lam), P.get('settle', 1.0)
        s = 0.0
        while p.z > z_end and s < P.get('maxlen', .6):
            base = lerp(lam, lam_end, smooth(0, settle, s))
            lam_s = min(1.08, max(.05, base + sw_a * smooth(0, .05, s) * sin(2 * pi * s / sw_l + ph)))
            q = self.layer(p + f * DS - c, lam_s)
            if self.top_z is not None and q.z > self.top_z:
                q.z = self.top_z
            if tuck:
                q = self.tuck_push(q)
            mv = q - p
            if mv.length < 1e-6:
                break
            if mv.length > 3 * DS:                    # never jump: move toward the layer
                q = p + mv.normalized() * 3 * DS
                mv = q - p
            n = (q - c).normalized()
            nf = mv.normalized() + self.flow_at(q, n) * steer + bias
            if tuck and self.C.get('tuck_steer', False):
                nf += self.tuck_steer(q)
            nf -= n * nf.dot(n)
            if nf.length < 1e-6:
                break
            f = nf.normalized()
            p = q
            pts.append(p.copy())
            s += mv.length
        return pts, f

    def wave(self, pts, i0, amp, lz, z_top, phase, tuck=True):
        """Lateral S-wave over the head surface as a function of height, so
        neighbouring clumps wave together (phase is mirrored left/right)."""
        if amp <= 0 or len(pts) < i0 + 3:
            return pts
        c = self.c
        out = [p.copy() for p in pts[:i0 + 1]]
        for i in range(i0 + 1, len(pts)):
            p = pts[i]
            t = pts[min(i + 1, len(pts) - 1)] - pts[i - 1]
            n = p - c
            b = t.cross(n)
            if b.length < 1e-9:
                out.append(p.copy())
                continue
            b.normalize()
            g = smooth(z_top, z_top - .05, p.z) * (1 - .8 * smooth(.09, .0, abs(p.x)) * smooth(.0, .10, p.y - c.y))
            q = p + b * (amp * g * sin(2 * pi * (z_top - p.z) / lz + phase))
            q = c + (q - c).normalized() * n.length
            out.append(self.tuck_push(q) if tuck else q)
        return out

    def wave_phase(self, x):
        W = self.C
        ph = W.get('wave_phase', 0.0) + (0.0 if x >= 0 else pi)
        return ph + self.rng.uniform(-W.get('phase_jitter', .35), W.get('phase_jitter', .35))

    def skirt(self, pts, lam, z_end, phase, P):
        """Hanging part of the bob, built around the hair axis: the height
        falls to z_end; the angle around the head eases from where the cap
        lock ended to its place behind the ear (and forward again under the
        ear), then waves in an S; the radius follows layer lam between the
        inner hull and the envelope, swelling a little in and out."""
        c, rng = self.c, self.rng
        Sk = P['skirt']
        p0 = pts[-1]
        a0 = signed_front_angle(p0, c.y)
        side = 1.0 if a0 >= 0 else -1.0
        a_lo = Sk.get('from', 45.0)
        z0 = p0.z
        T = self.ear
        amp = radians(rng.uniform(*P['wave_amp']))
        lz = rng.uniform(*P['wave_len'])
        sw_a, sw_l = P.get('swell', (0.0, .1))
        sph = rng.uniform(0, 2 * pi)
        if P.get('lock_deg'):
            # locks: neighbouring cards in one sector around the head wave and
            # swell together, so the bob reads as distinct wavy locks
            k = math.floor((a0 + 360.0) / P['lock_deg'])
            g = (k * .6180339887) % 1.0
            amp = radians(lerp(*P['wave_amp'], g) * rng.uniform(.85, 1.15))
            lz = lerp(*P['wave_len'], (k * .3819660113) % 1.0)
            phase = 2 * pi * ((k * .7548776662) % 1.0) + rng.uniform(-.25, .25)
            sph = 2 * pi * ((k * .5698402910) % 1.0) + rng.uniform(-.3, .3)
        ease = Sk.get('ease', .05)
        w = Sk.get('soft', 12.0)
        r0 = Vector((p0.x - c.x, p0.y - c.y, 0)).length
        out = []
        n = max(3, int((z0 - z_end) / (self.DS * .9)))
        for k in range(1, n + 1):
            z = z0 - (z0 - z_end) * k / n
            drop = z0 - z
            # where this height's hair may start (front angle), behind the ears
            if T is not None:
                a_min = table(Sk['front'], z - T['z_top'])
            else:
                a_min = a_lo
            aa = abs(a0)
            mapped =a_min + w * math.log1p(math.exp(min(30.0, (aa - a_min) / w)))   # soft max(aa, a_min)
            a = lerp(aa, max(aa, mapped), smooth(0, ease, drop))
            a = side * min(180.0, a)
            g = smooth(0, .05, drop) * (1 - .8 * smooth(150, 178, abs(a)))
            a += side * degrees(amp * g * sin(2 * pi * drop / lz + phase))
            u = radians(a - 90.0)
            dz = z - c.z
            lam_z = min(1.06, max(.05, lam + sw_a * smooth(0, .05, drop) * sin(2 * pi * drop / sw_l + sph)))
            ri = self.inner.hradius(u, dz)
            ro = max(self.env.hradius(u, dz), ri + self.C.get('min_thick', .010))
            r = ri + lam_z * (ro - ri)
            r = lerp(r0, r, smooth(0, ease * .6, drop))
            q = Vector((c.x + r * cos(u), c.y + r * sin(u), z))
            out.append(self.keep_out(q, .006))
        return pts + out

    def flip(self, pts, flick, curl, gravity=0.0):
        """End curl: + turns the tip outward (away from the head axis) and up,
        - tucks it in."""
        DS = self.DS
        p = pts[-1].copy()
        f = (pts[-1] - pts[max(0, len(pts) - 4)])
        f = f.normalized() if f.length > 1e-9 else Vector((0, 0, -1))
        out = Vector((p.x - self.c.x, p.y - self.c.y, 0))
        out = out.normalized() if out.length > 1e-6 else Vector((0, 1, 0))
        axis = f.cross(out)
        if axis.length < 1e-6:
            axis = f.cross(Vector((1, 0, 0)))
        axis.normalize()
        steps = max(3, int(flick / DS))
        for i in range(steps):
            u = (i + .5) / steps
            f = rotate(f, axis, radians(curl) * (.4 + 1.2 * u) / steps)
            if gravity:
                f = rotate(f, f.cross(Vector((0, 0, -1))), gravity * DS * (1 - u))
            f.normalize()
            p = self.keep_out(p + f * DS)
            pts.append(p.copy())
        return pts

    def fall(self, pts, f, z_end, P, split=None):
        """Free fall under gravity from the last point, outside head and body.
        split: None, 'front' (over the shoulder, down the front) or 'back'."""
        L = P
        ds = L.get('ds', self.DS)
        g = L.get('gravity', 8.0)
        sw_a, sw_l = L.get('fall_wave', (0.0, .2))
        ph = self.rng.uniform(0, 2 * pi)
        p = pts[-1].copy()
        k = 0
        while p.z > z_end and k < 500:
            k += 1
            f = rotate(f, f.cross(Vector((0, 0, -1))), g * ds * max(0.0, 1 - max(0.0, -f.z)))
            if split is not None and p.z < L.get('split_z', 9) + SEAT:
                if split == 'front':
                    target = Vector((0, -L['front'] * smooth(L['front_y'] - .03, L['front_y'], p.y), -1))
                else:
                    target = Vector((-p.x * L['pull'], L['back'], -1))
                f = f.lerp(target.normalized(), .35)
            if sw_a:
                side = Vector((-f.y, f.x, 0))
                if side.length > 1e-6:
                    f = f + side.normalized() * (sw_a * cos(2 * pi * k * ds / sw_l + ph)) * ds * 2 * pi / sw_l
            f.normalize()
            q = self.keep_out(p + f * ds, L.get('margin', .006))
            mv = q - p
            if mv.length > 1e-7:
                f = f.lerp(mv.normalized(), .5).normalized()
            p = q
            pts.append(p.copy())
        return pts, f

    # ---------------------------------------------------------- clumps
    def add(self, pts, group, lam, W, TH, x_root=0.0, split=None, P=None):
        if pts is None or len(pts) < 4:
            return
        P = P or self.C
        g = resample(pts, P.get('ring', .008))
        if len(g) < 3:
            return
        s = [0.0]
        for a, b in zip(g, g[1:]):
            s.append(s[-1] + (b - a).length)
        self.items.append(dict(pts=g, s=s, L=s[-1], group=group, lam=lam, W=W, TH=TH, x_root=x_root,
                               split=split, P=P))

    def grow_main(self):
        """Roots over the scalp (dart throwing); crown roots lie on outer
        layers.  Bob: run down the envelope, wave, flip.  Long hair: run to
        the release height, then fall (front strands over the shoulders)."""
        C, H, vol, rng = self.C, self.H, self.vol, self.rng
        roots = []
        tries = 0
        while tries < 12000 and len(roots) < C.get('max_roots', 400):
            tries += 1
            az = rng.uniform(0, 360)
            e = vol.el_edge(az)
            v = rng.random() ** .9
            d = direction(az, lerp(e + 2, 89, v))
            loc, n, dist = vol.scalp(d)
            if loc is None or (self.top_z is not None and loc.z > self.top_z - .004):
                continue
            fa = front_angle(loc)
            if all((loc - q).length > C['spacing'] * (.9 if fa < 60 else 1.0) for _, q, _ in roots):
                roots.append((d, loc, v))
        skip_fa, skip_v = C['skip_front']
        st = C.get('skip_temple')
        lam_lo, lam_hi = C['lam']
        base = C.get('cards', {}).get('base_layer')
        for k, (d, loc, v) in enumerate(roots):
            fa = front_angle(loc)
            if fa < skip_fa and v < skip_v:
                continue
            if st and st[0] < fa < st[1] and v < st[2]:
                continue
            lam = max(.15, min(1.0, lam_lo + (lam_hi - lam_lo) * v ** .7 + rng.uniform(-.06, .06)))
            W = rng.uniform(*C['width']) * (.85 + .25 * lam)
            TH = rng.uniform(*C['thick'])
            self.grow_one(d, loc, lam, W, TH)
            if base and k % base.get('every', 2) == 0:
                # dense, dark card close to the scalp along the same flow
                self.grow_one(d, loc, rng.uniform(*base['lam']), W * base.get('wide', 1.3), TH, True)
        return len(roots)

    def grow_one(self, d, loc, lam, W, TH, base=False, f0=None, rise_P=None):
        """One guide from a scalp root: rise onto layer lam, then (long hair)
        walk to the release height and fall, or (bob) cap walk, skirt and end
        curl.  f0 / rise_P: start direction and rise parameters (crown)."""
        C, rng = self.C, self.rng
        long = C.get('long')
        fa = front_angle(loc)
        z_stop = (long['release'] if long else table(C['bottom'], fa)) + SEAT + .03
        pts, f = self.rise(d, f0, lam, rise_P or C, z_stop)
        if pts is None:
            return
        i0 = len(pts) - 1
        if long:
            split = 'front' if fa < long['split'] else 'back'
            z_rel = long['release'] + SEAT + rng.uniform(-.015, .015)
            pts, f = self.walk(pts, f, lam, z_rel, C, split == 'back')
            pts = self.wave(pts, i0, rng.uniform(*C['wave_amp']), rng.uniform(*C['wave_len']),
                            C['release'] + SEAT + .03, self.wave_phase(loc.x), split == 'back')
            end = lerp(long['front_end'], long['back_end'], smooth(60, 160, fa)) + rng.uniform(-.06, .06)
            if split == 'back':
                end += long.get('layer_drop', .10) * (1 - lam)     # under layers end higher
            pts, f = self.fall(pts, f, end + SEAT, long, split)
            self.add(pts, 'long_' + split, lam, W, TH, loc.x, split)
            self.items[-1]['base'] = base
            return
        z_end = table(C['bottom'], fa) + SEAT + rng.uniform(*C.get('bottom_jitter', (-.012, .018)))
        z_end += C.get('layer_lift', .0) * (1 - lam)
        if 'skirt' in C:
            Sk = C['skirt']
            # cap: along the layer down to z_cap
            z_cap = Sk['cap'] + SEAT
            if pts[-1].z > z_cap:
                pts, f = self.walk(pts, f, lam, z_cap, C, False)
            if abs(signed_front_angle(pts[-1], self.c.y)) < Sk['under_sweep']:
                # over the temple: ends tucked under the sweep locks (rigid);
                # roots low beside the ear would only stand out as a band
                if loc.z < z_cap + Sk.get('cap_root_min', -9.0):
                    return
                pts = self.flip(pts, .02, Sk.get('cap_curl', -35))
                self.add(pts, 'cap', min(lam, .85), W, TH, loc.x)
                if self.items and self.items[-1]['pts'] is not None:
                    self.items[-1]['base'] = base
                return
            if lam < Sk.get('ear_inner_lam', 0.0) and abs(signed_front_angle(pts[-1], self.c.y)) < Sk.get('ear_inner_deg', 0.0):
                return                                   # inner layers behind the ear only show their edges
            pts = self.skirt(pts, lam, z_end, self.wave_phase(pts[-1].x), C)
        else:
            pts, f = self.walk(pts, f, lam, z_end, C)
            pts = self.wave(pts, i0, rng.uniform(*C['wave_amp']), rng.uniform(*C['wave_len']),
                            C['release'] + SEAT + .03, self.wave_phase(loc.x))
        flick = rng.uniform(*C['flick'])
        if lam < C.get('inner_lam', 0.0):
            curl = rng.uniform(*C['inner_curl'])     # inner layers: no hooks inside the bob
        elif rng.random() < C.get('flip_out', .7):
            curl = rng.uniform(*C['curl_out'])
        else:
            curl = rng.uniform(*C['curl_in'])
            flick *= .6
        pts = self.flip(pts, flick, curl, C.get('flip_gravity', 0.0))
        n0 = len(self.items)
        self.add(pts, 'hang', lam, W, TH, loc.x)
        if len(self.items) > n0:
            self.items[-1]['base'] = base

    def grow_whorl(self):
        Wh = self.C.get('whorl')
        if not Wh:
            return
        rng = self.rng
        wd = direction(*self.H['flow']['crown'])
        e1 = wd.cross(Vector((0, 0, 1))).normalized()
        e2 = wd.cross(e1).normalized()
        for k in range(Wh['count']):
            a = 2 * pi * (k + rng.uniform(-.2, .2)) / Wh['count']
            ek = e1 * cos(a) + e2 * sin(a)
            d = (wd + ek * Wh.get('offset', .06)).normalized()
            lam = Wh.get('lam', .97)
            if Wh.get('full'):
                # crown hair: radiates from the whorl and runs on down like the
                # rest of the hair (no ledge where short whorl cards would end)
                loc, _, _ = self.vol.scalp(d)
                if loc is not None:
                    self.grow_one(d, loc, lam, rng.uniform(*Wh['width']), rng.uniform(*self.C['thick']),
                                  f0=ek, rise_P=dict(self.C, rise_angle=(6, 12)))
                continue
            pts, f = self.rise(d, ek, lam, dict(self.C, rise_angle=(6, 12)))
            if pts is None:
                continue
            P = dict(self.C, maxlen=rng.uniform(*Wh['length']), swell=(0.0, .1), steer=.15, sweep_back=None,
                     lam_end=Wh.get('lam_end', lam), settle=Wh.get('settle', 1.0))
            pts, f = self.walk(pts, ek, lam, -9.0, P, False)
            self.add(pts, 'whorl', lam, rng.uniform(*Wh['width']), rng.uniform(*self.C['thick']) * .8, 0.0)

    def grow_sweeps(self):
        """Broad locks from the part over the temples, passing above the ear and
        ending behind it: each is a smooth curve in (angle around the head,
        height) through start / middle / end, on layer lam."""
        Sw = self.C.get('sweeps')
        if not Sw:
            return
        c, rng = self.c, self.rng
        for side, a0, z0, a1, z1, a2, z2, wid, lam, curl in Sw['locks']:
            n = 60
            pts = []
            for k in range(n + 1):
                t = k / n
                # quadratic Bezier through the middle point (control chosen so it passes there)
                am = 2 * a1 - .5 * (a0 + a2)
                zm = 2 * z1 - .5 * (z0 + z2)
                a = (1 - t) ** 2 * a0 + 2 * t * (1 - t) * am + t * t * a2
                z = (1 - t) ** 2 * z0 + 2 * t * (1 - t) * zm + t * t * z2 + SEAT
                u = radians(side * a - 90.0)
                dz = z - c.z
                ri = self.inner.hradius(u, dz)
                ro = max(self.env.hradius(u, dz), ri + self.C.get('min_thick', .010))
                lam_t = lerp(Sw.get('lam_root', .35), lam, smooth(0, .18, t))
                r = ri + lam_t * (ro - ri)
                pts.append(self.keep_out(Vector((c.x + r * cos(u), c.y + r * sin(u), z)), .005))
            pts = self.flip(pts, rng.uniform(*Sw.get('flick', (.02, .03))), curl)
            self.add(pts, 'sweep', lam, wid, rng.uniform(*Sw.get('thick', (.016, .022))), side * .2)

    def grow_bangs(self):
        C, rng = self.C, self.rng
        B = C['bangs']
        rx, rz = B['root']
        for lock in B['locks']:
            x, lift, z_end, sweep, wid = lock[:5]
            curl = lock[5] if len(lock) > 5 else rng.uniform(*B.get('curl', (-30, -10)))
            root = self.c + Vector((x * .55, rx, rz + lift))
            d = (root - self.c).normalized()
            f0 = Vector((sweep, -B.get('forward', 1.0), -B.get('down', .5)))
            P = dict(C, steer=B.get('steer', .15), swell=(0.0, .1), bias=(sweep * B.get('bias', .3), 0, -B.get('fall', .5)),
                     lam_end=B.get('lam_end', B.get('lam', .96)), settle=B.get('settle', 1.0),
                     maxlen=B.get('maxlen', .16), sweep_back=None)
            lam = B.get('lam', .96)
            pts, f = self.rise(d, f0, lam, P)
            if pts is None:
                continue
            i0 = len(pts) - 1
            pts, f = self.walk(pts, f, lam, z_end + SEAT, P, B.get('tuck', False))
            pts = self.wave(pts, i0, B.get('wave', .004), B.get('wave_len', .12), pts[i0].z,
                            rng.uniform(0, 2 * pi), False)
            pts = self.flip(pts, rng.uniform(*B.get('flick', (.020, .030))), curl)
            self.add(pts, 'bang', lam, wid, rng.uniform(*B.get('thick', (.010, .015))), root.x,
                     P=dict(self.C, tip=B.get('tip', self.C.get('tip', .8)), taper_from=B.get('taper_from', .55)))

    def grow_curtain(self):
        """Bangs as designed curves: each lock runs from a root on the scalp
        behind the front hairline to a tip on the forehead, bowing sideways;
        it lifts off the scalp at the root (volume over the hairline) and
        settles onto the forehead toward the tip.  Lock = (root x, root
        elevation (deg, from the hair centre toward the front), tip x, tip
        height, sideways bow, width, gap at the root, gap at the tip, curl,
        layer)."""
        C, rng, c, vol = self.C, self.rng, self.c, self.vol
        B = C['curtain']
        X = Vector((1, 0, 0))
        for lock in B['locks']:
            xr, er, xt, zt, bend, wid, g0, g1, curl, lam = lock
            xt += rng.uniform(-.004, .004)
            zt += rng.uniform(-.004, .004)
            d0 = Vector((xr, -.2 * cos(radians(er)), .2 * sin(radians(er)))).normalized()
            d1 = Vector((xt, -.2, zt + SEAT - c.z)).normalized()
            n = 48
            pts = []
            for k in range(n + 1):
                t = k / n
                d = d0.slerp(d1, t)
                # the sideways travel happens on the forehead (where it shows), not over the top
                dx = (d1.x - d0.x) * (smooth(B.get('sweep_from', .2), 1.0, t) - t)
                d = (d + X * (dx + bend * sin(pi * t) * (.5 + t))).normalized()
                loc, nn, dist = vol.scalp(d)
                if dist is None:
                    continue
                gap = lerp(g0, g1, smooth(.15, 1.0, t)) * smooth(0, .12, t) ** .5 + .0015
                q = c + d * (dist + gap)
                if self.top_z is not None and q.z > self.top_z:
                    q.z = self.top_z
                pts.append(q)
            if len(pts) < 6:
                continue
            pts = self.flip(pts, rng.uniform(*B.get('flick', (.008, .012))), curl)
            self.add(pts, 'bang', lam, wid, rng.uniform(*B.get('thick', (.010, .014))), xr,
                     P=dict(self.C, tip=B.get('tip', .7), taper_from=B.get('taper_from', .55),
                            card_tip=B.get('card_tip', self.C['cards'].get('tip_narrow', .35))))

    def grow_wisps(self):
        C, rng, vol = self.C, self.rng, self.vol
        Wp = C['wisps']
        for side, fa, z_end, wid, curl in Wp['locks']:
            az = (-90 + fa) if side > 0 else (-90 - fa)
            e = vol.el_edge(az % 360)
            d = direction(az, e + Wp.get('above', 3.0))
            P = dict(C, rise_angle=(55, 70))
            pts, f = self.rise(d, Vector((0, -.25, -1)), Wp.get('lam', .25), P)
            if pts is None:
                continue
            Pf = dict(gravity=Wp.get('gravity', 10.0), margin=Wp.get('margin', .007), fall_wave=(.004, .10))
            pts, f = self.fall(pts, Vector((0, -.15, -1)).normalized(), z_end + SEAT, Pf)
            pts = self.flip(pts, Wp.get('flick', .03), curl)
            self.add(pts, 'front', .3, wid, rng.uniform(*Wp.get('thick', (.007, .010))), side * .1)

    def grow_flyaways(self):
        C, rng = self.C, self.rng
        Fy = C.get('flyaways')
        if not Fy:
            return
        for k in range(Fy['count']):
            az = rng.uniform(0, 360)
            if 60 < (az % 360) < 120 and False:
                continue
            d = direction(az, rng.uniform(*Fy.get('el', (50, 78))))
            pts, f = self.rise(d, None, 1.0, dict(C, rise_angle=(30, 50)))
            if pts is None:
                continue
            pts, f = self.walk(pts, f, 1.0, -9, dict(C, maxlen=rng.uniform(.03, .06), swell=(0.0, .1)))
            out = (pts[-1] - self.c).normalized()
            pts, f = self.fall(pts, (f + out * .8).normalized(), pts[-1].z - rng.uniform(*Fy['length']),
                               dict(gravity=Fy.get('gravity', 6.0), margin=.01))
            pts = self.flip(pts, .02, rng.uniform(*Fy['curl']))
            self.add(pts, 'fly', 1.0, Fy['width'], Fy['width'] * .6, 0.0)

    # ---------------------------------------------------------- chains
    def attach_length(self, it):
        """Arclength where the clump leaves the head (its chain takes over)."""
        C = self.C
        g, s = it['pts'], it['s']
        if it['group'] == 'bang':
            z_a = g[0].z - C.get('bangs', C.get('curtain', {})).get('attach', .025)
        elif it['group'] == 'front':
            z_a = g[0].z - .025
        else:
            z_a = C['release'] + SEAT
        for p, si in zip(g, s):
            if p.z < z_a:
                return max(si, .012)
        return s[-1] * .5

    def assign(self, it, chains):
        """[(chain name, weight)] for a clump."""
        g = it['pts']
        grp = it['group']
        cy = self.c.y
        if grp in ('fly', 'whorl', 'cap'):
            return []
        if grp in ('front', 'long_front'):
            side = 'l' if it['x_root'] > 0 else 'r'
            names = [ch['name'] for ch in chains if ch['group'] == 'front' and ch['name'].endswith(side)]
            return [(names[0], 1.0)] if names else []
        if grp == 'bang':
            cs = sorted([ch for ch in chains if ch['group'] == 'bang'], key=lambda ch: ch['x'])
            x = it['x_root']
            if not cs:
                return []
            if x <= cs[0]['x']:
                return [(cs[0]['name'], 1.0)]
            for a, b in zip(cs, cs[1:]):
                if x <= b['x']:
                    t = (x - a['x']) / (b['x'] - a['x'])
                    return [(a['name'], 1 - t), (b['name'], t)]
            return [(cs[-1]['name'], 1.0)]
        # hanging hair: by the angle where it leaves the head
        sa = self.attach_length(it)
        p = next((q for q, si in zip(g, it['s']) if si >= sa), g[-1])
        ang = signed_front_angle(p, cy)
        cs = sorted([ch for ch in chains if ch['group'] == 'hang'], key=lambda ch: ch['angle'])
        if not cs:
            return []
        angs = [ch['angle'] for ch in cs]
        # cyclic bracket across the back (+180 / -180)
        ext = [(a - 360, ch) for a, ch in zip(angs, cs)] + list(zip(angs, cs)) + [(a + 360, ch) for a, ch in zip(angs, cs)]
        for (a0, c0), (a1, c1) in zip(ext, ext[1:]):
            if a0 <= ang <= a1:
                if c0 is c1:
                    return [(c0['name'], 1.0)]
                gap = a1 - a0
                if gap > C_MAX_GAP:
                    # open gap (e.g. the face): stick to the nearer chain
                    return [((c0 if ang - a0 < a1 - ang else c1)['name'], 1.0)]
                t = smooth(0, 1, (ang - a0) / gap)
                return [(c0['name'], 1 - t), (c1['name'], t)]
        return [(cs[0]['name'], 1.0)]

    def build_chains(self):
        """Bone chains from the clumps they carry; returns chain specs with
        their bone names (placed in G['bones'])."""
        bones = self.G['bones']
        for n in OLD_HAIR_BONES:
            bones.pop(n, None)
        chains = [dict(ch) for ch in self.C['chains']]
        for it in self.items:
            it['sa'] = self.attach_length(it)
            it['chains'] = self.assign(it, chains)
        made = []
        for ch in chains:
            members = [(w, it) for it in self.items for nm, w in it['chains'] if nm == ch['name'] and w > .5]
            if not members:
                continue
            members.sort(key=lambda m: (-m[1]['lam'], -m[0], -m[1]['L']))
            use = [it for w, it in members[:max(3, len(members) // 3)]]
            nb = ch['bones']
            J = []
            for k in range(nb + 1):
                u = k / nb
                acc = Vector()
                for it in use:
                    sa, L = it['sa'], it['L']
                    target = sa + u * (L - sa) * ch.get('reach', .92)
                    g, s = it['pts'], it['s']
                    j = 0
                    while j < len(s) - 2 and s[j + 1] < target:
                        j += 1
                    t = (target - s[j]) / max(1e-9, s[j + 1] - s[j])
                    acc += g[j].lerp(g[j + 1], max(0.0, min(1.0, t)))
                J.append(acc / len(use))
            names = []
            parent = 'head'
            for k in range(nb):
                nm = 'hair_%s_%02d' % (ch['name'], k + 1)
                h, t = J[k], J[k + 1]
                if (t - h).length < .008:
                    t = h + (t - h).normalized() * .008 if (t - h).length > 1e-6 else h + Vector((0, 0, -.008))
                bones[nm] = (h.copy(), t.copy(), parent)
                parent = nm
                names.append(nm)
            ch['bone_names'] = names
            made.append(ch)
        self.chains = {ch['name']: ch for ch in made}
        for it in self.items:
            it['chains'] = [(n, w) for n, w in it['chains'] if n in self.chains]
            tot = sum(w for _, w in it['chains'])
            if tot > 1e-6:
                it['chains'] = [(n, w / tot) for n, w in it['chains']]
        return made

    def ring_weights(self, it, s):
        """Bone weights at arclength s of a clump."""
        sa, L = it['sa'], it['L']
        wh = 1.0 - smooth(sa - .004, sa + .03, s)
        w = {}
        if not it['chains']:
            return {'head': 1.0}
        if wh > 1e-4:
            w['head'] = wh
        u = max(0.0, min(1.0, (s - sa) / max(.02, L - sa)))
        for nm, wc in it['chains']:
            names = self.chains[nm]['bone_names']
            nb = len(names)
            x = u * nb - .5
            k0 = math.floor(x)
            fr = x - k0
            for k, wk in ((k0, 1 - fr), (k0 + 1, fr)):
                kk = max(0, min(nb - 1, k))
                v = (1 - wh) * wc * wk
                if v > 1e-5:
                    w[names[kk]] = w.get(names[kk], 0.0) + v
        top = sorted(w.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(v for _, v in top)
        return {k: v / tot for k, v in top}

    # ---------------------------------------------------------- meshes
    def skin_item(self, it, out, K=None):
        """Bundle of 2-3 overlapping rounded strands along the clump guide;
        they part toward the tip and end at different lengths."""
        rng, P = self.rng, it['P']
        K = K or P.get('K', 10)
        g, s, L = it['pts'], it['s'], it['L']
        nr = len(g)
        T = [(g[min(i + 1, nr - 1)] - g[max(i - 1, 0)]).normalized() for i in range(nr)]
        N = []
        for i in range(nr):
            away = g[i] - self.c
            if i == 0:
                n = away
            else:
                n = N[-1].lerp(away.normalized(), .15)
            n = n - T[i] * n.dot(T[i])
            if n.length < 1e-6:
                n = Vector((0, 0, 1)) - T[i] * T[i].z
            N.append(n.normalized())
        Bn = [T[i].cross(N[i]).normalized() for i in range(nr)]
        W, TH = it['W'], it['TH']
        grp = it['group']
        if grp in ('fly', 'whorl', 'cap', 'bang') or W < .016:
            nstr = 1
        else:
            nstr = 3 if rng.random() < P.get('three', .45) else 2
        longest = rng.randrange(nstr)
        tip_pow = P.get('tip', .8)
        t0 = P.get('taper_from', .62)
        spread = P.get('part', .45)
        for j in range(nstr):
            o = (j - (nstr - 1) / 2) / nstr if nstr > 1 else 0.0
            e = 1.0 if j == longest else rng.uniform(*P.get('strand_len', (.78, .95)))
            wj = W / nstr * (P.get('overlap', 1.6) if nstr > 1 else 1.0)
            tj = TH * (rng.uniform(.82, 1.0) if nstr > 1 else 1.0)
            lift = TH * (.18 if abs(o) < .2 else -.04)
            wander = rng.uniform(-.12, .18) * W
            i_end = max(2, int(round(e * (nr - 1))))
            base = len(out['vs'])
            shift = rng.uniform(-.12, .12)
            for i in range(i_end + 1):
                t = s[i] / L
                te = i / i_end
                sep = (1 - spread) + spread * smooth(.35, 1.0, t)
                ctr = g[i] + Bn[i] * (W * o * sep + wander * smooth(.6, 1.0, t) * (1 if o >= 0 else -1)) + N[i] * lift
                if i == i_end:
                    out['vs'].append(ctr)
                    out['uv'].append((1.0, .5))
                    out['info'].append((it, s[i]))
                    continue
                full = P.get('root_w', .80) + (1 - P.get('root_w', .80)) * smooth(0, P.get('w_peak', .08), t)
                leaf = 1 + (P.get('widen', 1.0) - 1) * smooth(.30, .70, t)
                taper = 1.0 if te < t0 else ((1 - te) / (1 - t0)) ** tip_pow
                w = wj * full * leaf * taper
                th = tj * (.65 + .35 * full) * max(.15, taper ** .6)
                cup = P.get('cup', .08) * w
                for kk in range(K):
                    a = 2 * pi * kk / K
                    uu, vv = cos(a), sin(a)
                    x = .5 * w * uu
                    y = (th * .5 * vv ** P.get('round', .6) if vv > 0 else th * P.get('under', .4) * vv) - cup * (uu * uu - .35)
                    out['vs'].append(ctr + Bn[i] * x + N[i] * y)
                    out['uv'].append((t, kk / K))
                    out['info'].append((it, s[i]))
            for i in range(i_end - 1):
                for kk in range(K):
                    a = base + i * K + kk
                    b = base + i * K + (kk + 1) % K
                    out['fs'].append((a, a + K, b + K, b))
                    out['tone'].append(LockBuilder._tone(s[i] / L, sin(2 * pi * (kk + .5) / K) > 0, shift))
            last = base + (i_end - 1) * K
            tipv = base + i_end * K
            for kk in range(K):
                out['fs'].append((last + (kk + 1) % K, last + kk, tipv))
                out['tone'].append(LockBuilder._tone(1, sin(2 * pi * (kk + .5) / K) > 0, shift))
            out['fs'].append(tuple(base + kk for kk in range(K)))
            out['tone'].append(0)

    def frames(self, g):
        """Tangent, outward normal (parallel-transported) and side vector along a guide."""
        nr = len(g)
        T = [(g[min(i + 1, nr - 1)] - g[max(i - 1, 0)]).normalized() for i in range(nr)]
        N = []
        for i in range(nr):
            away = g[i] - self.c
            flat = Vector((away.x, away.y, 0))
            if flat.length > 1e-6:
                away = away.normalized().lerp(flat.normalized(), smooth(.0, -.08, away.z))
            n = away if i == 0 else N[-1].lerp(away.normalized(), .15)
            n = n - T[i] * n.dot(T[i])
            if n.length < 1e-6:
                n = Vector((0, 0, 1)) - T[i] * T[i].z
            N.append(n.normalized())
        return T, N, [T[i].cross(N[i]).normalized() for i in range(nr)]

    def card_row(self, it):
        """Strand-atlas row for a card: dense dark rows inside, airy rows outside."""
        rng, grp, lam = self.rng, it['group'], it['lam']
        if it.get('base'):
            return 0
        if grp == 'fly':
            return 7
        if grp == 'bang':
            return rng.choice((6, 6, 3))
        if grp == 'front':
            return rng.choice((6, 5))
        if grp == 'sweep':
            return rng.choice((2, 3, 3))
        if lam < .5:
            return rng.choice((0, 1))
        if lam < .82:
            return rng.choice((1, 2, 3))
        return rng.choice((2, 3, 4, 4, 5))

    def skin_card(self, it, out):
        """Hair card(s) along the guide: strips 3 vertices wide, bowed outward,
        U along the hair (root 0 -> tip 1), V across one atlas row.  Bangs,
        face-framing locks and sweeps are split into 2 side-by-side cards."""
        Cd, rng = self.C['cards'], self.rng
        rows = len(STRAND_ROWS)
        g, s, L = it['pts'], it['s'], it['L']
        T, N, Bn = self.frames(g)
        nsplit = Cd.get('split', {}).get(it['group'], 1)
        W = it['W'] * Cd.get('width_scale', 1.0)
        for j in range(nsplit):
            off = (j - (nsplit - 1) / 2) * W / nsplit * Cd.get('split_spread', .55)
            wj = W / nsplit * (1.3 if nsplit > 1 else 1.0)
            keep = 1.0 if j == 0 else rng.uniform(.82, .97)
            i_end = max(2, int(round(keep * (len(g) - 1))))
            Lj = s[i_end]
            row = self.card_row(it)
            v0, v1 = (row + .03) / rows, (row + .97) / rows
            if rng.random() < .5:
                v0, v1 = v1, v0                         # mirrored strands: less repetition
            base = len(out['vs'])
            tn = it['P'].get('card_tip', Cd.get('tip_narrow', .35))
            # twist: cards turned about the hair direction away from the layer
            # (seen from the front, long hair at the sides shows strands, not edges)
            tw = radians(Cd.get('twist', {}).get(it['group'], 0.0))
            if tw:
                tw *= rng.uniform(-1, 1)
            rows_ = self.card_rows(g, N, i_end)
            for i in rows_:
                t = s[i] / Lj
                w = wj * (Cd.get('root_w', .75) + (1 - Cd.get('root_w', .75)) * smooth(0, .15, t)) \
                    * (1 - tn * smooth(.65, 1.0, t))
                bow = Cd.get('bow', .16) * w
                ctr = g[i] + Bn[i] * off
                th = tw * smooth(0, .25, t)
                side = Bn[i] * cos(th) + N[i] * sin(th)
                up = N[i] * cos(th) - Bn[i] * sin(th)
                for a, lift in ((-1, 0.0), (0, 1.0), (1, 0.0)):
                    out['vs'].append(ctr + side * (a * w / 2) + up * (bow * lift))
                    out['uv'].append((min(1.0, t), lerp(v0, v1, (a + 1) / 2)))
                    out['info'].append((it, s[i]))
            for i in range(len(rows_) - 1):
                for k in range(2):
                    a = base + i * 3 + k
                    out['fs'].append((a, a + 3, a + 4, a + 1))
                    out['tone'].append(0)

    CARD_LEN, CARD_TURN = .028, 6.0      # round 10 (triangle budget): a card row every 28 mm, sooner where it turns

    def card_rows(self, g, N, i_end):
        """Guide points that get a card row: the root and the next point, the
        last two, and in between one every CARD_LEN or wherever the guide (or
        the card's facing) has turned by CARD_TURN degrees."""
        keep = [0]
        run = turn = 0.0
        for i in range(1, i_end):
            run += (g[i] - g[i - 1]).length
            turn += max(degrees((g[i] - g[i - 1]).angle(g[i + 1] - g[i], 0.0)), degrees(N[i - 1].angle(N[i], 0.0)))
            if i in (1, i_end - 1) or run >= self.CARD_LEN - 1e-9 or turn >= self.CARD_TURN:
                keep.append(i)
                run = turn = 0.0
        keep.append(i_end)
        return keep

    def build_core(self, name, material, card_material=None):
        """Dark core under the clumps (fills the gaps; keeps the scalp hidden)."""
        C, vol = self.C, self.vol
        core = C.get('core', .12)
        z_b = C.get('core_bottom', 1.30) + SEAT
        N, M = 120, 26
        vs, fs = [], []
        for j in range(N):
            az = 360 * j / N
            d0 = direction(az, 0)
            fa = front_angle(self.c + d0 * .2)
            e_edge = vol.el_edge(az)
            lo, hi = -70.0, e_edge
            lam = core if not isinstance(core, list) else table(core, 0.0)
            for _ in range(24):
                mid = (lo + hi) / 2
                if self.layer(direction(az, mid), lam).z < z_b:
                    lo = mid
                else:
                    hi = mid
            e_low = lerp(e_edge, hi, smooth(C.get('core_front', (100, 125))[0], C.get('core_front', (100, 125))[1], fa))
            front_k = lerp(C.get('core_face', 1.0), 1.0, smooth(25, 75, fa))   # hug the scalp over the forehead
            for i in range(M):
                el = lerp(e_low, 88.0, (i / (M - 1)) ** 1.15)
                lam = (core if not isinstance(core, list) else table(core, el)) * lerp(front_k, 1.0, smooth(55, 85, el))
                p = self.layer(direction(az, el), lam)
                if self.top_z is not None and p.z > self.top_z:
                    p = Vector((p.x, p.y, self.top_z))
                vs.append(p)
        vs.append(self.layer(Vector((0, 0, 1)), core if not isinstance(core, list) else table(core, 90.0)))
        pole = len(vs) - 1
        for j in range(N):
            for i in range(M - 1):
                a = j * M + i
                b = ((j + 1) % N) * M + i
                fs.append((a, b, b + 1, a + 1))
            fs.append((j * M + M - 1, ((j + 1) % N) * M + M - 1, pole))
        Cd = C.get('cards')
        if Cd is None:
            return self.G['mesh'](name, vs, fs, material, 'head')
        # hair cards: the core is an opaque layer of the dense strand row
        # (strands running down from the crown, mirrored tiles around the head)
        ob = self.G['mesh'](name, vs, fs, card_material, 'head')
        rows = len(STRAND_ROWS)
        v0, v1 = .30 / rows, .70 / rows
        tiles = 2 * (Cd.get('core_tiles', 30) // 2)
        uv = []
        for j in range(N):
            ph = (j / N * tiles) % 2.0
            tri = ph if ph <= 1.0 else 2.0 - ph
            for i in range(M):
                uv.append((lerp(.85, .10, i / (M - 1)), lerp(v0, v1, tri)))
        uv.append((.10, lerp(v0, v1, .5)))
        set_uv(ob, uv)
        return ob

    def emit(self, title, tones):
        """Mesh objects (fringe / wisps / clumps), tone materials, UVs and
        per-vertex chain weights."""
        G = self.G
        cats = {'bang': 'hair fringe clumps', 'front': 'hair face-framing locks', 'fly': 'hair flyaways', 'whorl': 'hair clumps',
                'cap': 'hair clumps', 'sweep': 'hair clumps',
                'hang': 'hair clumps', 'long_front': 'hair front locks', 'long_back': 'hair clumps'}
        cards = 'cards' in self.C
        if cards:
            cats = {k: v.replace('clumps', 'cards').replace('locks', 'cards') for k, v in cats.items()}
        outs = {}
        kidx = {id(it): k for k, it in enumerate(self.items)}
        for it in self.items:
            nm = cats[it['group']]
            o = outs.setdefault(nm, dict(vs=[], fs=[], uv=[], tone=[], info=[]))
            if cards:
                self.skin_card(it, o)
            else:
                self.skin_item(it, o)
        made = []
        for nm, o in outs.items():
            if not o['fs']:
                continue
            ob = G['mesh']('%s %s' % (title, nm), o['vs'], o['fs'], tones[min(3, len(tones) - 1)].name, 'head')
            me = ob.data
            me.materials.clear()
            for m in tones:
                me.materials.append(m)
            for poly, t in zip(me.polygons, o['tone']):
                poly.material_index = t
            set_uv(ob, o['uv'])
            # strand index and arc length per vertex (resolve_hair_cloth)
            G.setdefault('HAIR_INFO', {})[ob.name] = [(kidx[id(it)], s) for it, s in o['info']]
            ob.vertex_groups.clear()
            groups = {}
            cache = {}
            for vi, (it, s) in enumerate(o['info']):
                key = (id(it), round(s, 4))
                w = cache.get(key)
                if w is None:
                    w = cache[key] = self.ring_weights(it, s)
                for bn, val in w.items():
                    gobj = groups.get(bn)
                    if gobj is None:
                        gobj = groups[bn] = ob.vertex_groups.new(name=bn)
                    gobj.add([vi], val, 'REPLACE')
            made.append(ob)
        return made

    def build(self, title, tones, core_material):
        n_roots = self.grow_main()
        self.grow_whorl()
        self.grow_sweeps()
        if 'curtain' in self.C:
            self.grow_curtain()
        elif 'bangs' in self.C:
            self.grow_bangs()
        if 'wisps' in self.C:
            self.grow_wisps()
        self.grow_flyaways()
        chains = self.build_chains()
        self.build_core(title + ' hair under-volume', core_material, tones[0].name)
        obs = self.emit(title, tones)
        counts = {}
        for it in self.items:
            counts[it['group']] = counts.get(it['group'], 0) + 1
        nv = sum(len(o.data.vertices) for o in obs)
        print('HAIR_CLUMPS %s roots=%d clumps=%s chains=%s verts=%d' % (
            title, n_roots, counts, {c['name']: len(c['bone_names']) for c in chains}, nv))
        return chains


C_MAX_GAP = 150.0      # degrees: wider gaps between hanging chains are not blended (the face)


class LockChains(ClumpHair):
    """Physics chains for the boys' locks (LockBuilder): the first part of
    each lock stays on the head, the rest follows its chain."""

    def __init__(self, G, c, C, items):
        self.G, self.c, self.C, self.items = G, c, C, items
        self.rng = random.Random(5)

    def attach_length(self, it):
        return max(.008, it['L'] * self.C.get('attach_frac', .35))

    def assign(self, it, chains):
        own = [ch for ch in chains if ch['group'] == it['group'] and ch['group'] not in ('hang', 'front', 'bang')]
        if own:
            return [(own[0]['name'], 1.0)]
        return ClumpHair.assign(self, it, chains)


def lock_chains(G, H, vol, builders, obs):
    """Bone chains + per-vertex weights for LockBuilder hair (STYLES hair['chains'])."""
    items = [it for b in builders.values() for it in b.items]
    C = dict(chains=H['chains'], attach_frac=H.get('chain_attach', .35))
    lc = LockChains(G, vol.c, C, items)
    chains = lc.build_chains()
    for kind_, ob in obs.items():
        b = builders[kind_]
        ob.vertex_groups.clear()
        groups, cache = {}, {}
        for vi, (it, sl) in enumerate(b.vinfo):
            key = (id(it), round(sl, 4))
            w = cache.get(key)
            if w is None:
                w = cache[key] = lc.ring_weights(it, sl)
            for bn, val in w.items():
                g = groups.get(bn)
                if g is None:
                    g = groups[bn] = ob.vertex_groups.new(name=bn)
                g.add([vi], val, 'REPLACE')
    print('HAIR_LOCK_CHAINS', {ch['name']: len(ch['bone_names']) for ch in chains})
    return chains


# ======================================================================
#  Driver
# ======================================================================
def build_head(G):
    kind = G['KIND']
    S = STYLES[kind]
    H = S['hair']
    F = S['face']
    rng = random.Random(H['seed'])
    skin_material(G, S)
    eyes = [o for o in G['parts'] if o.name.startswith('Eye white')]
    ez = sum(sum(v.co.z for v in o.data.vertices) / len(o.data.vertices) for o in eyes) / len(eyes)
    O = build_head_mesh(G, S, ez)
    G['HEAD_O'], G['HEAD_E'] = O.copy(), S['head']['E']
    bvh = bvh_of(G['faceob'])
    G['facebvh'] = bvh
    L = face_landmarks(G, S, O, bvh)
    B = F['brow']
    L['brow'] = dict(x=.5 * (B['inner'][0] + B['outer'][0]), z=ez + .5 * (B['inner'][1] + B['outer'][1]))
    G['NOSE_TIP'] = L['nose']
    slit = cut_mouth(G, S, L)                       # the mouth can open (round 6)
    bvh = bvh_of(G['faceob'])
    G['facebvh'] = bvh
    weight_head(G, L, S, slit)
    place_face_bones(G, L, bvh)
    build_mouth(G, S, L, bvh, slit)
    rebuild_eyes_and_brows(G, F, ez)
    join_lids_into_face(G)
    Ear = dict(S['ear'], center=(0.0, O.y + S['ear'].get('dy', 0.0), ez - SEAT - S['ear']['dz']))
    G['EAR_LOBES'] = build_ears(G, Ear, bvh)
    vol = HairVolume(H, bvh)
    flow = Flow(vol, H)
    shade_scalp(G, S)
    add_blush(G, F, ez)
    title = kind.title()
    c = H['colors']
    G['mat'](title + ' hair under-volume', c['base'], .75)
    top_z = (H['hat_top'] + SEAT) if 'hat_top' in H else None
    if 'clumps' not in H:
        build_under_volume(vol, G, title + ' hair under-volume', title + ' hair under-volume', top_z)
    if 'clumps' in H and 'cards' in H['clumps']:
        tones = [hair_card_material(G, title, H)]
    else:
        tones = [hair_material(G, '%s hair tone %d' % (title, j),
                               tuple(lerp(c['dark'][k], c['light'][k], j / 6) for k in range(3)), H['sheen'],
                               spec=H.get('spec', .42), ao_min=H.get('ao_min', .18))
                 for j in range(7)]
    body = Body(H['body']) if 'body' in H else None
    if 'clumps' in H:
        G['HAIR_CHAINS'] = ClumpHair(G, S, vol, flow, rng, body).build(title, tones, title + ' hair under-volume')
        return

    # Roots on the scalp above the hairline (dart throwing).  Locks rooted
    # nearer the crown lie on outer layers, so they cover the roots below.
    roots = []
    tries = 0
    while tries < 9000 and len(roots) < 600:
        tries += 1
        az = rng.uniform(0, 360)
        e = vol.el_edge(az)
        vs_ = rng.random() ** .9
        d = direction(az, lerp(e + 2, 89, vs_))
        loc, n, dist = vol.scalp(d)
        if loc is None:
            continue
        if top_z is not None and loc.z > top_z:
            continue
        fa = front_angle(loc)
        sp = H['spacing'] * (.85 if fa < 45 else 1.0)
        if all((loc - q).length > sp for _, q, _ in roots):
            roots.append((d, loc, vs_))
    builders = {k: LockBuilder(vol, flow, H, rng, body) for k in ('fringe', 'top', 'side', 'back')}
    skip_fa, skip_v = H['skip_front']
    long = H.get('long')
    for d, loc, vs_ in roots:
        fa = front_angle(loc)
        if fa < skip_fa and vs_ < skip_v:
            continue                                    # explicit fringe below
        elif vs_ > H['top_v'] and long is None:
            kind_ = 'top'
            lam = min(1.0, .80 + .20 * vs_ + rng.uniform(-.03, .03))
        else:
            kind_ = 'side' if fa < 130 else 'back'
            lam = .50 + .45 * vs_ ** .8 + rng.uniform(-.05, .05)
        end = None
        if long is not None:
            end = lerp(long['front_end'], long['back_end'], smooth(60, 160, fa)) + rng.uniform(-.05, .05)
        builders[kind_].add(d, kind_, max(.45, min(1.0, lam)), long_end=end)
    if 'part_locks' in H:
        # locks rooted just across the part, lying away from it, close the part
        PL = H['part_locks']
        px = H['flow']['part_x']
        for side in (1, -1):
            for k in range(PL['count']):
                t = (k + .5) / PL['count']
                phi = radians(lerp(PL['phi'][0], PL['phi'][1], t))
                d = Vector((0, -cos(phi), sin(phi)))
                loc, n, dist = vol.scalp(d)
                if loc is None:
                    continue
                root = Vector((px - side * PL['cross'], loc.y, loc.z))
                d = (root - vol.c).normalized()
                kind_ = PL['kind']
                start = Vector((side, PL['back'] * t, -PL['down']))
                builders[kind_].add(d, kind_, 1.0, start, width=rng.uniform(*PL['width']))
    if H['whorl_locks']:
        wd = direction(*(H['flow'].get('whorl') or H['flow']['crown']))
        e1 = wd.cross(Vector((0, 0, 1))).normalized()
        e2 = wd.cross(e1).normalized()
        b = builders['top']
        if 'whorl' in H:
            Wh = H['whorl']
            b.P = dict(H, lie={'top': Wh['lie']}, flick={'top': Wh['flick']}, curl={'top': Wh['curl']})
        for k in range(H['whorl_locks']):
            a = 2 * pi * k / H['whorl_locks']
            ek = e1 * cos(a) + e2 * sin(a)
            b.add((wd - ek * .10).normalized(), 'top', .995, ek)
        b.P = H
    # Fringe: separate pointed locks with uneven lengths, tips turning aside.
    fr = H['fringe']
    rx, rz = fr['root']
    for k, lock in enumerate(fr['locks']):
        x, lift, drop, turn, wid = lock[:5]
        root_ = vol.c + Vector((x * .55, rx, rz + lift))
        d = (root_ - vol.c).normalized()
        b = builders['fringe']
        bend = radians(abs(turn)) / (drop * 1.2)
        b.P = dict(H, lie={'fringe': (.10, .12)}, flick={'fringe': (drop, drop + .006)}, width=(wid, wid * 1.05),
                   curl={'fringe': fr.get('curl', (14, 26))}, jitter=4, bend=(bend, bend * 1.05),
                   bend_sign=(1 if turn > 0 else -1))
        sd = None
        if 'dir' in fr:
            lat, fwd, dn = fr['dir']
            if len(lock) > 5:
                lat = lock[5]
            sd = Vector(((1 if turn > 0 else -1) * lat if fr.get('mirror', True) else lat, -fwd, -dn))
        b.add(d, 'fringe', fr['layer'], sd)
        b.P = H
    # Extras
    if 'ahoge' in H:
        A = H['ahoge']
        b = builders['top']
        b.P = dict(H, lie={'top': (.012, .015)}, flick={'top': (A['length'], A['length'] + .005)},
                   curl={'top': (A['curl'], A['curl'] + 5)}, rise_angle=(2, 6), jitter=0)
        b.tag = 'ahoge'
        b.add(direction(*A['root']), 'top', 1.0, Vector(A['lean']).normalized(), width=A['width'])
        b.tag = None
        b.P = H
    if 'flyaways' in H:
        Fy = H['flyaways']
        b = builders['top']
        for k in range(Fy['count']):
            b.P = dict(H, lie={'top': (.03, .06)}, flick={'top': Fy['length']}, curl={'top': Fy['curl']},
                       rise_angle=(25, 45))
            az = rng.uniform(0, 360)
            b.add(direction(az, rng.uniform(55, 80)), 'top', 1.0, width=Fy['width'])
        b.P = H
    names = {'fringe': 'hair fringe locks', 'top': 'hair crown locks', 'side': 'hair side locks', 'back': 'hair back locks'}
    lock_obs = {}
    for kind_, b in builders.items():
        if not b.fs:
            continue
        if long is not None and kind_ in ('side', 'back', 'top'):
            w = long_weight
        else:
            w = 'head'
        ob = G['mesh']('%s %s' % (title, names[kind_]), b.vs, b.fs, '%s hair tone 3' % title, w)
        me = ob.data
        me.materials.clear()
        for m in tones:
            me.materials.append(m)
        for poly, t in zip(me.polygons, b.tone):
            poly.material_index = t
        set_uv(ob, b.uv)
        lock_obs[kind_] = ob
    if 'chains' in H:
        G['HAIR_CHAINS'] = lock_chains(G, H, vol, builders, lock_obs)
    print('HAIR_V5 %s roots=%d locks=%s stops=%s' % (kind, len(roots), {k: b.count for k, b in builders.items()},
                                                    {k: b.stats for k, b in builders.items()}))


# ======================================================================
#  Body proportions
# ======================================================================
# Measured on the approved sheets against the eye height (sole -> eye line):
# the V5 heads were ~20% too big for the bodies, the shoulders ~5 cm and the
# waist ~8 cm too low, the collars sat 5 cm under the chin (the "long neck")
# and the bind-pose arms were spread ~40 deg instead of ~27 deg.
# The knots are shared by all four wizards so their skeletons keep one shape.
PROPORTIONS = dict(
    # z_old -> z_new for everything below the head (monotone cubic through
    # the knots; slope 1 above the last one): legs kept, waist and shoulders
    # raised, collar brought up under the chin
    knots=[(0.0, 0.0), (0.43, 0.43), (0.70, 0.705), (0.80, 0.90), (1.14, 1.19), (1.205, 1.27), (1.40, 1.465)],
    arm_drop=14.0,              # degrees: bind-pose arms closer to the body
    neck_blend=(1.15, 1.30),    # z_old band: neck goes from body to head transform
    hair_blend=(1.10, 1.30),    # z_old band: long hair goes from head to body transform
)
# Round 9: arm layout measured on the 3d-v2 sheets (final space).  The shoulder
# joint sits 4 cm below its remapped height (the arms used to start level with
# the collar: everybody looked like they were shrugging), the upper arm is short
# and hangs close to the body, the forearm angles out, the hands are a bit
# bigger.  upper / fore: (degrees from vertical, length in m).
ARM_POSE = {
    'default': dict(out=0.0, drop=.042, upper=(23.0, .158), fore=(31.0, .203), hand=1.12),
    'wind': dict(out=.004, upper=(25.0, .155), fore=(30.0, .203)),
}


def _seg_tf(H, T, H2, T2, ramp=0.0):
    """Map the old bone H->T onto the new bone H2->T2: rotation plus a stretch
    along the bone.  With ramp > 0 nothing above the head is stretched and the
    stretch reaches full strength ramp m down the bone (a round shoulder stays
    round).  Returns (f, R)."""
    d = (T - H).normalized()
    L, L2 = (T - H).length, (T2 - H2).length
    R = d.rotation_difference((T2 - H2).normalized()).to_matrix()
    k = (L2 - ramp / 2) / (L - ramp / 2)

    def g(a):
        if ramp <= 0:
            return a * k
        if a <= 0:
            return a
        if a <= ramp:
            return a + (k - 1) * a * a / (2 * ramp)
        return ramp * (1 + k) / 2 + k * (a - ramp)

    def f(p):
        rel = p - H
        ax = rel.dot(d)
        return H2 + R @ (rel + d * (g(ax) - ax))
    return f, R


def mono_cubic(knots):
    """Monotone (Fritsch-Carlson) cubic through the knots, linear outside."""
    xs = [k[0] for k in knots]
    ys = [k[1] for k in knots]
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [((d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0.0) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9:
            t = 3 / sqrt(s)
            m[i], m[i + 1] = t * a * d[i], t * b * d[i]

    def f(x):
        if x <= xs[0]:
            return ys[0] + m[0] * (x - xs[0])
        if x >= xs[-1]:
            return ys[-1] + m[-1] * (x - xs[-1])
        for i in range(n - 1):
            if x <= xs[i + 1]:
                h = xs[i + 1] - xs[i]
                t = (x - xs[i]) / h
                return ((2 * t ** 3 - 3 * t * t + 1) * ys[i] + (t ** 3 - 2 * t * t + t) * h * m[i]
                        + (-2 * t ** 3 + 3 * t * t) * ys[i + 1] + (t ** 3 - t * t) * h * m[i + 1])
    return f


def head_scale(kind):
    return STYLES[kind]['proportion']['head']


ARM_BONES = ('upperarm_', 'lowerarm_', 'hand_', 'thumb_', 'index_', 'middle_', 'ring_', 'pinky_')
HAT_PARTS = ('Wide hat brim', 'Hat brim edge', 'Bent hat crown', 'Hat scarf band', 'Hat scarf knot', 'Hat clasp')


def apply_proportions(G):
    """Re-proportion the finished model (all parts and bones) before rigging.
    Head: uniform scale about the eye line (eye height kept).  Body: vertical
    remap B(z) and torso width W(z).  Arms: rigid, rotated toward the body
    about the shoulder joint and carried with it.  Neck and long hair blend
    between the head and body transforms."""
    kind = G['KIND']
    S = STYLES[kind]
    Pp = S['proportion']
    parts, bones = G['parts'], G['bones']
    B = mono_cubic(PROPORTIONS['knots'])
    Wx = mono_cubic(Pp.get('width', [(0.0, 1.0), (1.0, 1.0)]))
    sh = Pp['head']
    eyes = [o for o in parts if o.name.startswith('Eye white')]
    ez = sum(sum(v.co.z for v in o.data.vertices) / len(o.data.vertices) for o in eyes) / len(eyes)
    pivot = Vector((0.0, 0.0, ez))

    def t_body(p):
        w = max(.5, min(1.5, Wx(p.z)))
        return Vector((p.x * w, p.y * (1 - .5 * (1 - w)), B(p.z)))

    def t_head(p):
        return pivot + (p - pivot) * sh

    # arms: every arm bone gets its own move onto the round-9 layout (ARM_POSE);
    # arm vertices blend the moves by their bone weights
    AP = dict(ARM_POSE['default'], **ARM_POSE.get(kind, {}))
    arm_tf, arm_final = {}, {}
    for s, sg in (('l', 1), ('r', -1)):
        J, E, Wr = (Vector(bones[n + s][0]) for n in ('upperarm_', 'lowerarm_', 'hand_'))
        J2 = t_body(J) + Vector((sg * AP['out'], 0.0, -AP['drop']))
        (au, lu), (af, lf) = AP['upper'], AP['fore']
        E2 = J2 + Vector((sg * sin(radians(au)) * lu, E.y - J.y, -cos(radians(au)) * lu))
        W2 = E2 + Vector((sg * sin(radians(af)) * lf, Wr.y - E.y, -cos(radians(af)) * lf))
        fu, _ = _seg_tf(J, E, J2, E2, ramp=.06)
        ff, Rf = _seg_tf(E, Wr, E2, W2)
        arm_tf[s] = {'upper': fu, 'fore': ff,
                     'hand': lambda p, Wr=Wr, W2=W2, Rf=Rf, hs=AP['hand']: W2 + Rf @ ((p - Wr) * hs)}
        arm_final[s] = (J2, E2, W2)
    G['ARM_FINAL'] = arm_final

    def arm_seg(n):
        return 'upper' if n.startswith('upperarm_') else ('fore' if n.startswith('lowerarm_') else 'hand')

    def blend(p, lo, hi, head_on_top=True):
        w = max(0.0, min(1.0, (p.z - lo) / (hi - lo)))
        if not head_on_top:
            w = 1 - w
        return t_body(p).lerp(t_head(p), w)

    # long hair hangs over the body and blends into the body transform; a bob
    # (clump hair without 'long') moves with the head only
    Hh = S['hair']
    hair_blends = 'long' in Hh or ('clumps' in Hh and 'long' in Hh['clumps'])
    hat_s = Pp.get('hat')
    hat_base = None
    if hat_s:
        crown = next((o for o in parts if o.name.startswith('Bent hat crown')), None)
        if crown:
            hat_base = Vector((0.0, .024, min(v.co.z for v in crown.data.vertices)))
    for ob in parts:
        names = [g.name for g in ob.vertex_groups]
        idx = {g.index: g.name for g in ob.vertex_groups}
        headpart = bool(names) and all(n == 'head' or n.startswith(('face_', 'hair_')) for n in names)
        longhair = headpart and hair_blends and any(n.startswith('hair_') for n in names)
        hat = hat_base is not None and headpart and (ob.name.startswith(HAT_PARTS) or ob.name.startswith('Tassel'))
        kbs = list(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else []
        for v in ob.data.vertices:
            p = v.co.copy()
            if kbs:                               # morph targets: head parts only (affine head transform)
                assert headpart and not longhair and not hat, ob.name
                for kb in kbs:
                    kb.data[v.index].co = t_head(kb.data[v.index].co.copy())
            if hat:
                q = t_head(hat_base) + (p - hat_base) * hat_s
            elif longhair:
                lo, hi = PROPORTIONS['hair_blend']
                q = blend(p, lo, hi)
            elif headpart:
                q = t_head(p)
            elif ob.name == 'Neck':
                lo, hi = PROPORTIONS['neck_blend']
                q = blend(p, lo, hi)
            else:
                wb = {}
                for g in v.groups:
                    n = idx[g.group]
                    if n.startswith(ARM_BONES) and g.weight > 0:
                        ws = wb.setdefault(n[-1], {})
                        ws[arm_seg(n)] = ws.get(arm_seg(n), 0.0) + g.weight
                q = t_body(p)
                if wb:
                    s = max(wb, key=lambda k: sum(wb[k].values()))
                    a = sum(wb[s].values())
                    pa = sum((arm_tf[s][sg_](p) * w for sg_, w in wb[s].items()), Vector()) / a
                    q = q.lerp(pa, min(1.0, a))
            v.co = q
        ob.data.update()
    head_bone_head = Vector(bones['head'][0])
    for name, (h, t, parent) in list(bones.items()):
        h, t = Vector(h), Vector(t)
        if name == 'head' or name.startswith('face_'):
            h2, t2 = t_head(h), t_head(t)
        elif name.startswith('hair_') and not hair_blends:
            h2, t2 = t_head(h), t_head(t)
        elif name.startswith('hair_'):
            lo, hi = PROPORTIONS['hair_blend']
            h2, t2 = blend(h, lo, hi), blend(t, lo, hi)
        elif name.startswith(ARM_BONES):
            f = arm_tf[name[-1]][arm_seg(name)]
            h2, t2 = f(h), f(t)
        elif name.startswith('clavicle_'):
            h2, t2 = t_body(h), arm_final[name[-1]][0]
        elif name == 'neck_01':
            h2, t2 = t_body(h), t_head(head_bone_head)
        else:
            h2, t2 = t_body(h), t_body(t)
        bones[name] = (h2, t2, parent)
    Nk = Pp.get('neck')
    if Nk and 'HEAD_O' in G:
        old = next((o for o in parts if o.name == 'Neck'), None)
        if old is not None:
            parts.remove(old)
            bpy.data.objects.remove(old, do_unlink=True)
        O2 = t_head(G['HEAD_O'])
        E2 = G['HEAD_E'] * sh
        cy = O2.y + Nk['dy'] * E2
        zt = O2.z - .45 * E2                      # well inside the head: no gap under the jaw
        zb = B(1.10)                              # inside the collar / torso
        zn0 = Vector(bones['neck_01'][0]).z
        r, ry = Nk['r'] * E2, Nk['ry'] * E2
        rings = [(zb, r * 1.30, ry * 1.20, cy + .006), (.5 * (zb + zn0), r * 1.08, ry * 1.05, cy + .003),
                 (zn0, r, ry, cy), (zt - .02, r * .98, ry * .98, cy), (zt, r * .85, ry * .85, cy)]
        G['loft']('Neck', rings, 'Skin',
                  lambda p: G['chainweight'](p, [(zn0 - .015, 'spine_03'), (zn0 + .02, 'neck_01'), (zt - .03, 'head')]), 32)
    print('PROPORTIONS_APPLIED %s head=%.3f eye=%.3f' % (kind, sh, ez))


def resolve_hair_cloth(G, margin=.010, ease=.08):
    """Final space (after the clothes and arms are in place): long hair stays
    outside them.  Rays from outside toward the body axis give the outermost
    cloth radius around the body (by angle and height); each strand is pushed
    out radially by what it needs, the push is kept further down the strand
    (the hair hangs over the obstacle) and eased in above it (ease m)."""
    info = G.get('HAIR_INFO')
    Hh = STYLES[G['KIND']]['hair']
    if not info or not ('long' in Hh or 'long' in Hh.get('clumps', {})):
        return
    from mathutils.bvhtree import BVHTree
    parts = G['parts']
    hair = [o for o in parts if o.name in info]
    verts, polys = [], []
    for ob in parts:
        names = [g.name for g in ob.vertex_groups]
        if ob in hair or not names or all(n == 'head' or n.startswith(('face_', 'hair_')) for n in names):
            continue
        off = len(verts)
        verts.extend(v.co.copy() for v in ob.data.vertices)
        polys.extend([off + i for i in p.vertices] for p in ob.data.polygons)
    bvh = BVHTree.FromPolygons(verts, polys)
    NT, z0, z1, dz = 240, .30, 1.34, .006
    NZ = int(round((z1 - z0) / dz)) + 1
    Rf = np.zeros((NZ, NT))
    for i in range(NZ):
        z = z0 + i * dz
        for j in range(NT):
            th = 2 * pi * j / NT
            d = Vector((cos(th), sin(th), 0.0))
            loc, nrm, idx, dist = bvh.ray_cast(Vector((0.0, 0.0, z)) + d * 1.5, -d, 1.5)
            if loc is not None:
                Rf[i, j] = Vector((loc.x, loc.y)).length

    def need(p):
        if not (z0 <= p.z <= z1):
            return 0.0
        fi = (p.z - z0) / dz
        fj = (atan2(p.y, p.x) % (2 * pi)) / (2 * pi) * NT
        i0, j0 = min(NZ - 2, int(fi)), int(fj) % NT
        u, v = fi - i0, fj - int(fj)
        j1 = (j0 + 1) % NT
        r = ((1 - u) * ((1 - v) * Rf[i0, j0] + v * Rf[i0, j1]) + u * ((1 - v) * Rf[i0 + 1, j0] + v * Rf[i0 + 1, j1]))
        # the cloth radius right around the point, not between two samples
        r = max(r, Rf[i0, j0], Rf[i0, j1], Rf[i0 + 1, j0], Rf[i0 + 1, j1]) if r > 0 else 0.0
        if r <= 0:
            return 0.0
        return max(0.0, r + margin - Vector((p.x, p.y)).length)
    moved = 0
    worst = 0.0
    for ob in hair:
        me = ob.data
        inf = info[ob.name]
        strands = {}
        for v, (k, s) in zip(me.vertices, inf):
            n = need(v.co)
            if n > 0:
                strands.setdefault(k, []).append((s, n))
        if not strands:
            continue
        for v, (k, s) in zip(me.vertices, inf):
            hits = strands.get(k)
            if not hits:
                continue
            push = 0.0
            for s1, n in hits:
                push = max(push, n * smooth(s1 - ease, s1, s))
            if push > 0:
                rd = Vector((v.co.x, v.co.y, 0.0))
                if rd.length > 1e-6:
                    v.co += rd.normalized() * push
                    moved += 1
                    worst = max(worst, push)
        me.update()
    print('HAIR_CLOTH %s moved=%d worst=%.3f' % (G['KIND'], moved, worst))


# ======================================================================
#  Head review (look-dev)
# ======================================================================
REVIEW_FRAME = {'default': (1.48, .64), 'ice': (1.60, .92)}    # camera centre z, ortho size


def studio_light(scene):
    """Soft neutral studio (like the turnaround sheets).  Replaces any lights,
    neutral grey world, and a colour transform that keeps skin tones (AgX
    turned the skin grey)."""
    for ob in [o for o in scene.objects if o.type == 'LIGHT']:
        bpy.data.objects.remove(ob, do_unlink=True)
    if hasattr(scene, 'cycles'):
        scene.cycles.transparent_max_bounces = 128      # layered hair cards
    for name, loc, power, size in [('Key', (-2.5, -4, 4), 210, 4), ('Fill', (3, -3, 2), 140, 4),
                                   ('Rim', (1.5, 3, 3.5), 140, 3)]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        ob = bpy.context.object
        ob.name = name
        ob.data.energy = power
        ob.data.shape = 'DISK'
        ob.data.size = size
        ob.rotation_euler = (Vector((0, 0, 1.2)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Studio World')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (.62, .62, .64, 1)
    bg.inputs[1].default_value = .38
    names = [e.identifier for e in scene.view_settings.bl_rna.properties['view_transform'].enum_items]
    scene.view_settings.view_transform = 'Khronos PBR Neutral' if 'Khronos PBR Neutral' in names else 'Standard'
    scene.view_settings.look = 'None'


def head_review(G, folder, views=('front', 'side', 'back', 'three_quarter')):
    """Fast look-dev renders of the head only (no body, rig or export)."""
    import sys, json
    parts = G['parts']
    scene = bpy.context.scene

    def aim(ob, p):
        ob.rotation_euler = (Vector(p) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    CZ, ORTHO = REVIEW_FRAME.get(G['KIND'], REVIEW_FRAME['default'])
    faceob = G['faceob']
    fv = [v.co for v in faceob.data.vertices]
    eyes = [o for o in parts if o.name.startswith('Eye white')]
    ez = sum(sum(v.co.z for v in o.data.vertices) / len(o.data.vertices) for o in eyes) / len(eyes)
    chin = min((p for p in fv if abs(p.x) < .012 and p.y < -.02), key=lambda p: p.z)
    nose = min((p for p in fv if abs(p.x) < .01 and abs(p.z - (ez - .05)) < .03), key=lambda p: p.y)
    folder.mkdir(parents=True, exist_ok=True)
    marks = dict(eye_z=ez, chin_z=chin.z, nose_y=nose.y, nose_z=nose.z, skull_top=max(p.z for p in fv),
                 center=CZ, ortho=ORTHO, res=900)
    (folder / 'landmarks.json').write_text(json.dumps(marks, indent=1))
    bpy.ops.object.camera_add(location=(0, -4, CZ))
    cam = bpy.context.object
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ORTHO
    scene.camera = cam
    studio_light(scene)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = int(G.get('REVIEW_SAMPLES', 24))
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    locs = {'front': (0, -4, CZ), 'side': (4, 0, CZ), 'back': (0, 4, CZ), 'three_quarter': (2.3, -3.3, CZ + .06)}
    for label in views:
        cam.location = locs[label]
        aim(cam, (0, 0, CZ))
        scene.render.filepath = str(folder / (label + '.png'))
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / ('%s_Head_V5_Review.blend' % G['KIND'].title())))
    print('HEAD_REVIEW_COMPLETE')
    sys.exit(0)
