"""
propagation.py - Is a licensed TV transmitter likely to matter where you are?

A transmitter lookup lists every station within range, and in a city that is
one on nearly every channel; most are far too weak to notice. This estimates
the field strength a station produces at the looked-up location from only what
the licence says, its effective radiated power and its distance, so that only
stations strong enough to block a channel are masked. It knows nothing about terrain,
antenna height or pattern: it is a rule of thumb, and any row can be ticked or
unticked by hand.

The curve is the typical UHF broadcast case (a tall mast, about 300 m above
average terrain, median conditions), in dB(uV/m) for 1 kW ERP. Close in it
follows free space less ground effects; past the radio horizon it falls much
faster than free space.
"""

import math

# distance km -> field strength dB(uV/m) for 1 kW ERP
_CURVE_1KW = ((1.0, 100.0), (5.0, 82.0), (10.0, 72.0), (20.0, 60.0), (50.0, 38.0),
              (80.0, 20.0), (100.0, 10.0), (160.0, -8.0), (300.0, -30.0))

# --- Which stations are worth a mask -----------------------------------------
#
# A mask means "this channel is blocked", not "a station can be watched here".
# The rules come from comparing a lookup with what an analyzer actually showed
# (New York, 2026): the channels that were strong each had a station of tens to
# hundreds of kW a few km away; the ones that were weak had only low-power
# stations nearby, or full-power ones 85-90 km out.
#
#   * Full-power stations are masked when the estimate reaches BLOCKING_LEVEL,
#     well above the level at which TV is merely receivable (41 dB uV/m).
#   * Low-power stations (at or under the low-power TV limit: 15 kW UHF, 3 kW
#     VHF, whatever the licence class) deliver far less than their ERP suggests:
#     the figure is the peak of a directional beam from a lower, side-mounted
#     antenna. They are masked only when practically next door.
#   * Only licensed stations count (not applications or construction permits).
#   * With no usable ERP, distance alone decides.
BLOCKING_LEVEL_DBUVM = 60.0
LOW_POWER_LEVEL_DBUVM = 100.0
LOW_POWER_ERP_KW_UHF = 15.0
LOW_POWER_ERP_KW_VHF = 3.0
UNKNOWN_POWER_RANGE_KM = 30.0
NOT_ON_AIR_STATUSES = ("APP", "CP", "CP MOD", "STA")     # FCC status codes other than licensed


def field_strength_dbuvm(erp_kw: float, distance_km: float) -> float:
    """Estimated field strength (dB uV/m) of a transmitter of erp_kw at distance_km."""
    d = max(float(distance_km), _CURVE_1KW[0][0])
    pts = _CURVE_1KW
    if d >= pts[-1][0]:
        base = pts[-1][1]
    else:
        for (d0, e0), (d1, e1) in zip(pts[:-1], pts[1:]):
            if d <= d1:
                # straight lines in log distance
                base = e0 + (e1 - e0) * (math.log10(d) - math.log10(d0)) / (math.log10(d1) - math.log10(d0))
                break
    return base + 10.0 * math.log10(max(float(erp_kw), 1e-6))


def is_low_power(erp_kw: float, channel=None) -> bool:
    vhf = isinstance(channel, (int, float)) and channel <= 13
    return float(erp_kw) <= (LOW_POWER_ERP_KW_VHF if vhf else LOW_POWER_ERP_KW_UHF)


def worth_masking(erp, distance_km, channel=None, status=None, low_power_class=True):
    """
    (mask, estimated field strength or None, reason). erp is the licence's ERP
    in kW, status its licence status when the database gives one.

    low_power_class: apply the low-power station rule above. It describes US
    low-power TV (a licence class whose ERP overstates what arrives). European
    networks are built from many relays of a few watts to a few kilowatts that
    do serve their surroundings, so there every transmitter is judged by its
    estimated field strength alone.
    """
    if status and str(status).strip().upper() in NOT_ON_AIR_STATUSES:
        return False, None, "not licensed yet"
    try:
        d = float(distance_km)
    except (TypeError, ValueError):
        return True, None, "distance unknown"
    try:
        p = float(erp)
        if p <= 0:
            raise ValueError
    except (TypeError, ValueError):
        near = d <= UNKNOWN_POWER_RANGE_KM
        return near, None, "power unknown: " + ("near" if near else "far")
    e = field_strength_dbuvm(p, d)
    if low_power_class and is_low_power(p, channel):
        return e >= LOW_POWER_LEVEL_DBUVM, e, "low power"
    return e >= BLOCKING_LEVEL_DBUVM, e, "full power"
