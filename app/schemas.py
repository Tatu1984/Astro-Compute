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
