"""
Chart computation using Swiss Ephemeris (pyswisseph).

Phase 1 scope: natal chart with Western planets + 12 houses + Ascendant/Midheaven.
Vedic-specific math (nakshatras, dashas, divisional charts) lands incrementally.
"""

import hashlib
import json
from datetime import datetime, timezone

import swisseph as swe

from .schemas import HouseSystem, NatalRequest, NatalResponse, PlanetPosition


# Chiron and other asteroids need external SE data files (e.g. seas_18.se1)
# which aren't bundled with pyswisseph. Add them when we ship ephemeris data.
PLANETS = [
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS),
    ("Mars", swe.MARS),
    ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN),
    ("Uranus", swe.URANUS),
    ("Neptune", swe.NEPTUNE),
    ("Pluto", swe.PLUTO),
    ("MeanNode", swe.MEAN_NODE),
]

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

HOUSE_SYSTEM_CODES: dict[HouseSystem, str] = {
    "PLACIDUS": "P",
    "WHOLE_SIGN": "W",
    "KOCH": "K",
    "EQUAL": "E",
    "VEDIC_EQUAL": "E",  # placeholder; refine when Vedic ayanamsha lands
}


def _sign_for(longitude_deg: float) -> str:
    return SIGNS[int(longitude_deg // 30) % 12]


def _house_for(longitude_deg: float, cusps: list[float]) -> int:
    # cusps is 12 entries, each the start of houses 1..12 in degrees.
    # Find which span [cusps[i], cusps[(i+1) % 12]] contains the longitude.
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if start <= end:
            if start <= longitude_deg < end:
                return i + 1
        else:
            # wraps past 360
            if longitude_deg >= start or longitude_deg < end:
                return i + 1
    return 12


def _input_hash(req: NatalRequest) -> str:
    payload = req.model_dump(mode="json")
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def compute_natal(req: NatalRequest) -> NatalResponse:
    dt = req.birth_datetime_utc.astimezone(timezone.utc)
    jd = swe.julday(
        dt.year,
        dt.month,
        dt.day,
        dt.hour + dt.minute / 60 + dt.second / 3600,
    )

    # Use Moshier ephemeris (built-in, no .se1 data files needed). Accuracy
    # is ~0.01° vs Swiss Ephemeris — well within tolerance for astrology.
    # Switch to FLG_SWIEPH once we ship the SE data files in the image.
    flags = swe.FLG_MOSEPH | swe.FLG_SPEED

    planets: list[PlanetPosition] = []
    cusps_raw, ascmc = swe.houses(
        jd,
        req.latitude,
        req.longitude,
        HOUSE_SYSTEM_CODES[req.house_system],
    )
    cusps = list(cusps_raw)  # 12 entries

    for name, code in PLANETS:
        result, _ret = swe.calc_ut(jd, code, flags)
        lon, lat, _dist, lon_speed, _lat_speed, _dist_speed = result
        planets.append(
            PlanetPosition(
                name=name,
                longitude_deg=lon % 360,
                latitude_deg=lat,
                speed_deg_per_day=lon_speed,
                sign=_sign_for(lon),
                house=_house_for(lon % 360, cusps),
            )
        )

    return NatalResponse(
        computed_at=datetime.now(timezone.utc),
        input_hash=_input_hash(req),
        house_system=req.house_system,
        system=req.system,
        planets=planets,
        houses=cusps,
        ascendant_deg=ascmc[0],
        midheaven_deg=ascmc[1],
    )
