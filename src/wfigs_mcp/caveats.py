from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

SAFETY_CAVEAT = (
    "Wildfire perimeters can lag ground conditions by a day or more and are not "
    "evacuation guidance. Follow local emergency officials and consult InciWeb: "
    "https://inciweb.wildfire.gov"
)


class Freshness(BaseModel):
    data_as_of: datetime
    newest_perimeter_age_hours: float | None
    oldest_perimeter_age_hours: float | None
    caveat: str = SAFETY_CAVEAT


def freshness(data_as_of: datetime, perimeter_times: list[datetime | None]) -> Freshness:
    ages = [
        max(0.0, (data_as_of - value).total_seconds() / 3_600)
        for value in perimeter_times
        if value is not None
    ]
    return Freshness(
        data_as_of=data_as_of,
        newest_perimeter_age_hours=min(ages) if ages else None,
        oldest_perimeter_age_hours=max(ages) if ages else None,
    )
