from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


HouseSystem = Literal["PLACIDUS", "WHOLE_SIGN", "KOCH", "EQUAL", "VEDIC_EQUAL"]
AstroSystem = Literal["WESTERN", "VEDIC", "BOTH"]


class NatalRequest(BaseModel):
    birth_datetime_utc: datetime = Field(
        description="Birth date+time in UTC (ISO 8601)."
    )
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    house_system: HouseSystem = "PLACIDUS"
    system: AstroSystem = "BOTH"
    unknown_time: bool = False


class PlanetPosition(BaseModel):
    name: str
    longitude_deg: float
    latitude_deg: float
    speed_deg_per_day: float
    sign: str
    house: int | None = None


class NatalResponse(BaseModel):
    schema_version: str = "1"
    computed_at: datetime
    input_hash: str
    house_system: HouseSystem
    system: AstroSystem
    planets: list[PlanetPosition]
    houses: list[float]  # 12 cusps in degrees
    ascendant_deg: float
    midheaven_deg: float


class TransitRequest(BaseModel):
    """Snapshot of where the planets are at a given moment."""
    moment_utc: datetime = Field(description="Timestamp to compute the planet positions at.")


class TransitResponse(BaseModel):
    schema_version: str = "1"
    computed_at: datetime
    moment_utc: datetime
    planets: list[PlanetPosition]


# ============================================================
# VEDIC (sidereal / Lahiri)
# ============================================================

class VedicRequest(BaseModel):
    """Inputs for a Vedic chart — sidereal Lahiri longitudes,
    nakshatras, Vimshottari dasha, D9 Navamsa, Manglik flag."""
    birth_datetime_utc: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class VedicPlanetPosition(BaseModel):
    name: str
    sidereal_long: float
    sidereal_sign: str
    sign_idx: int
    house: int | None = None
    nakshatra: str
    nakshatra_idx: int
    pada: int
    nakshatra_lord: str
    speed_deg_per_day: float
    retrograde: bool
    navamsa_sign: str


class DashaPeriod(BaseModel):
    lord: str
    start: datetime
    end: datetime


class DashaInfo(BaseModel):
    mahadasha: DashaPeriod
    antardasha: DashaPeriod
    upcoming_mahadashas: list[DashaPeriod]


class VedicResponse(BaseModel):
    schema_version: str = "1"
    computed_at: datetime
    ayanamsha_deg: float
    ayanamsha_name: str = "Lahiri"
    sidereal_ascendant: float
    ascendant_sign: str
    planets: list[VedicPlanetPosition]
    dasha: DashaInfo
    is_manglik: bool
    manglik_reason: str
