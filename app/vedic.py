"""
Vedic (sidereal) astrology calculations.

Implements:
  - Lahiri-ayanamsha sidereal longitudes for all major planets
  - Nakshatra (lunar mansion), pada, and ruling planet of each placement
  - Vimshottari mahadasha + current antardasha + next 3 upcoming mahadashas
  - D9 Navamsa sign for each planet
  - Manglik flag (Mars in 1, 2, 4, 7, 8, or 12 from sidereal Ascendant)
  - Whole-sign houses from the sidereal Ascendant

All math derived directly from pyswisseph + small tables — no third-party
Vedic library dependency, so Render deploy stays light.
"""

from datetime import datetime, timedelta, timezone

import swisseph as swe

from .schemas import (
    DashaInfo,
    DashaPeriod,
    VedicPlanetPosition,
    VedicRequest,
    VedicResponse,
)


SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# 27 nakshatras, each spanning 13°20' = 13.333333° of the sidereal zodiac.
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

# Repeating cycle of 9 nakshatra lords used for Vimshottari Dasha.
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# Years allotted to each lord's mahadasha (sums to 120).
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

NAK_DEG = 360.0 / 27.0  # 13°20' = 13.3333…
PADA_DEG = NAK_DEG / 4.0  # 3°20'

# Major planets used in the Vedic chart. Order matters — keep the inner
# planets first.
VEDIC_BODIES = [
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS),
    ("Mars", swe.MARS),
    ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN),
    # Rahu = Mean North Node; Ketu = its opposite point. Vedic charts do
    # not use the outer planets (Uranus/Neptune/Pluto) by default.
    ("Rahu", swe.MEAN_NODE),
]


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _to_jd(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + dt.second / 3600)


def _norm(deg: float) -> float:
    return deg % 360.0


def _sign_for(deg: float) -> tuple[int, str]:
    idx = int(_norm(deg) // 30) % 12
    return idx, SIGNS[idx]


def _nakshatra_for(deg: float) -> tuple[int, str, int, str]:
    n = _norm(deg)
    idx = int(n // NAK_DEG) % 27
    within = n - idx * NAK_DEG
    pada = int(within // PADA_DEG) + 1
    lord = NAK_LORDS[idx % 9]
    return idx, NAKSHATRAS[idx], pada, lord


# Movable / Fixed / Dual signs cycle (sign_idx % 3 == 0 / 1 / 2). The
# starting navamsa per type:
#   Movable -> same sign
#   Fixed   -> 9th from sign  (offset 8)
#   Dual    -> 5th from sign  (offset 4)
_NAVAMSA_OFFSET = {0: 0, 1: 8, 2: 4}


def _navamsa_sign(sidereal_deg: float) -> str:
    n = _norm(sidereal_deg)
    sign_idx = int(n // 30)
    pos_in_sign = n - sign_idx * 30
    nav_idx_in_sign = int(pos_in_sign // (30 / 9))  # 0..8
    nav_sign_idx = (sign_idx + _NAVAMSA_OFFSET[sign_idx % 3] + nav_idx_in_sign) % 12
    return SIGNS[nav_sign_idx]


def _whole_sign_house(planet_sign_idx: int, asc_sign_idx: int) -> int:
    # Whole-sign Vedic houses: H1 = sign of Ascendant; planets in same
    # sign go to H1, next sign to H2, etc.
    return ((planet_sign_idx - asc_sign_idx) % 12) + 1


# ----------------------------------------------------------------
# Vimshottari Dasha
# ----------------------------------------------------------------

def _years_to_timedelta(years: float) -> timedelta:
    # Vedic convention: 1 year = 365.25 days.
    return timedelta(days=years * 365.25)


def _vimshottari_at(birth_utc: datetime, moon_long_sidereal: float, at: datetime) -> DashaInfo:
    """Walk Vimshottari periods from birth until `at`, return the
    mahadasha containing `at` plus its current antardasha.
    """
    # 1. Lord at birth + remaining time of birth dasha based on Moon's
    #    position within its nakshatra.
    nak_idx = int(_norm(moon_long_sidereal) // NAK_DEG)
    nak_lord = NAK_LORDS[nak_idx % 9]
    within_nak = _norm(moon_long_sidereal) - nak_idx * NAK_DEG
    fraction_remaining = (NAK_DEG - within_nak) / NAK_DEG
    birth_dasha_full_years = DASHA_YEARS[nak_lord]
    birth_dasha_remaining_years = birth_dasha_full_years * fraction_remaining

    # 2. Walk the dasha sequence forward from birth until we cover `at`.
    current_lord = nak_lord
    cursor = birth_utc
    cursor_end = birth_utc + _years_to_timedelta(birth_dasha_remaining_years)

    # Build a small queue of upcoming dashas after the current one.
    lord_order = NAK_LORDS  # cyclic
    start_idx = lord_order.index(nak_lord)
    next_lords: list[str] = []
    for k in range(1, 9):
        next_lords.append(lord_order[(start_idx + k) % 9])

    # If `at` is within the birth-dasha remaining, we're done.
    if cursor_end >= at:
        maha = DashaPeriod(lord=current_lord, start=cursor, end=cursor_end)
    else:
        # Advance through the remaining lords.
        i = 0
        while True:
            # Next lord starts at cursor_end and lasts its full years.
            next_lord = lord_order[(start_idx + 1 + i) % 9]
            next_start = cursor_end
            next_end = next_start + _years_to_timedelta(DASHA_YEARS[next_lord])
            if next_end >= at:
                current_lord = next_lord
                cursor = next_start
                cursor_end = next_end
                break
            cursor_end = next_end
            i += 1
        maha = DashaPeriod(lord=current_lord, start=cursor, end=cursor_end)

    # 3. Antardasha: the mahadasha period is itself sub-divided into 9
    #    antardashas in lord order starting with the mahadasha lord. Each
    #    antardasha length = (lord_years * mahadasha_years / 120).
    maha_lord_idx = NAK_LORDS.index(maha.lord)
    maha_total_days = (maha.end - maha.start).total_seconds() / 86400.0
    antar_lord = maha.lord
    antar_start = maha.start
    antar_end = antar_start
    for k in range(9):
        candidate_lord = NAK_LORDS[(maha_lord_idx + k) % 9]
        candidate_years = DASHA_YEARS[candidate_lord]
        candidate_days = (candidate_years / 120.0) * maha_total_days * 365.25 / 365.25
        # Simpler: candidate fraction of mahadasha = candidate_years / 120
        candidate_days = (candidate_years / 120.0) * maha_total_days
        candidate_end = antar_start + timedelta(days=candidate_days)
        if candidate_end >= at:
            antar_lord = candidate_lord
            antar_end = candidate_end
            break
        antar_start = candidate_end
    antar = DashaPeriod(lord=antar_lord, start=antar_start, end=antar_end)

    # 4. Three upcoming mahadashas after the current one.
    upcoming: list[DashaPeriod] = []
    cursor = maha.end
    for k in range(1, 4):
        upcoming_lord = lord_order[(NAK_LORDS.index(maha.lord) + k) % 9]
        upcoming_end = cursor + _years_to_timedelta(DASHA_YEARS[upcoming_lord])
        upcoming.append(DashaPeriod(lord=upcoming_lord, start=cursor, end=upcoming_end))
        cursor = upcoming_end

    return DashaInfo(mahadasha=maha, antardasha=antar, upcoming_mahadashas=upcoming)


# ----------------------------------------------------------------
# Main entry
# ----------------------------------------------------------------

# Set ayanamsha mode ONCE at module load. Changing it per-request would
# leak state across concurrent requests in worker reuse scenarios.
swe.set_sid_mode(swe.SIDM_LAHIRI)


def compute_vedic(req: VedicRequest) -> VedicResponse:
    jd = _to_jd(req.birth_datetime_utc)
    flags_sid = swe.FLG_MOSEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    ayanamsha = swe.get_ayanamsa_ut(jd)

    # Sidereal Ascendant via Whole Sign houses — but house calc uses
    # tropical; convert by subtracting ayanamsha.
    cusps_raw, ascmc = swe.houses(jd, req.latitude, req.longitude, b"W")
    asc_tropical = ascmc[0]
    asc_sidereal = _norm(asc_tropical - ayanamsha)
    asc_sign_idx, asc_sign = _sign_for(asc_sidereal)

    planets: list[VedicPlanetPosition] = []
    moon_sid_long = 0.0
    mars_sign_idx: int | None = None

    for name, code in VEDIC_BODIES:
        result, _ret = swe.calc_ut(jd, code, flags_sid)
        long_sid, _lat, _dist, lon_speed, _ls, _ds = result
        long_sid = _norm(long_sid)
        sign_idx, sign = _sign_for(long_sid)
        nak_idx, nak, pada, nak_lord = _nakshatra_for(long_sid)
        nav_sign = _navamsa_sign(long_sid)
        house = _whole_sign_house(sign_idx, asc_sign_idx)

        if name == "Moon":
            moon_sid_long = long_sid
        if name == "Mars":
            mars_sign_idx = sign_idx

        planets.append(VedicPlanetPosition(
            name=name,
            sidereal_long=long_sid,
            sidereal_sign=sign,
            sign_idx=sign_idx,
            house=house,
            nakshatra=nak,
            nakshatra_idx=nak_idx,
            pada=pada,
            nakshatra_lord=nak_lord,
            speed_deg_per_day=lon_speed,
            retrograde=lon_speed < 0,
            navamsa_sign=nav_sign,
        ))

    # Ketu = Rahu + 180°. Compose its row from Rahu's data.
    rahu = next(p for p in planets if p.name == "Rahu")
    ketu_long = _norm(rahu.sidereal_long + 180)
    ketu_sign_idx, ketu_sign = _sign_for(ketu_long)
    ketu_nak_idx, ketu_nak, ketu_pada, ketu_nak_lord = _nakshatra_for(ketu_long)
    ketu_nav = _navamsa_sign(ketu_long)
    planets.append(VedicPlanetPosition(
        name="Ketu",
        sidereal_long=ketu_long,
        sidereal_sign=ketu_sign,
        sign_idx=ketu_sign_idx,
        house=_whole_sign_house(ketu_sign_idx, asc_sign_idx),
        nakshatra=ketu_nak,
        nakshatra_idx=ketu_nak_idx,
        pada=ketu_pada,
        nakshatra_lord=ketu_nak_lord,
        speed_deg_per_day=-rahu.speed_deg_per_day,
        retrograde=not rahu.retrograde,
        navamsa_sign=ketu_nav,
    ))

    # Vimshottari Dasha — current periods at *now* (so the user sees
    # what's active for them today, not what was active at birth).
    now = datetime.now(timezone.utc)
    dasha = _vimshottari_at(req.birth_datetime_utc.astimezone(timezone.utc), moon_sid_long, now)

    # Manglik check: Mars in 1, 2, 4, 7, 8, 12 houses from Lagna.
    is_manglik = False
    manglik_reason = "Mars not in a manglik house"
    if mars_sign_idx is not None:
        mars_house = _whole_sign_house(mars_sign_idx, asc_sign_idx)
        if mars_house in (1, 2, 4, 7, 8, 12):
            is_manglik = True
            manglik_reason = f"Mars in house {mars_house} from sidereal Ascendant"

    return VedicResponse(
        computed_at=datetime.now(timezone.utc),
        ayanamsha_deg=ayanamsha,
        sidereal_ascendant=asc_sidereal,
        ascendant_sign=asc_sign,
        planets=planets,
        dasha=dasha,
        is_manglik=is_manglik,
        manglik_reason=manglik_reason,
    )
