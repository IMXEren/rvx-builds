"""IP Geolocation API."""

import contextlib
from dataclasses import dataclass
from typing import ClassVar, Self

import requests


@dataclass
class IPGeolocationInfo:
    """IP Geolocation object."""

    _instance: ClassVar[Self | None] = None

    ip: str
    city: str
    region: str
    country_name: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str
    utc_offset: str  # +HHMM or -HHMM

    def diff_utc_local_in_minutes(self) -> int:
        """The difference in minutes, between the UTC time zone and the local time zone."""
        return -self.utc_offset_in_minutes()

    def utc_offset_in_minutes(self) -> int:
        """Convert +HHMM/-HHMM into +minutes or -minutes."""
        sign = 1 if self.utc_offset[0] == "+" else -1
        hours = int(self.utc_offset[1:3])
        mins = int(self.utc_offset[3:5])
        return sign * (hours * 60 + mins)

    @classmethod
    def get_info(cls: type[Self], *, refresh: bool = False) -> Self | None:
        """
        Get the ip gelocation info.

        Returns cached instance if available, unless refresh=True.
        """
        if cls._instance is not None and not refresh:
            return cls._instance

        with contextlib.suppress(requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            r = requests.get(
                "https://ipapi.co/json/",
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (HTML, like Gecko)"
                    " Chrome/143.0.0.0 Safari/537.36",
                    "Content-Type": "application/json",
                },
            )
            r = r.json()
            if r.get("error", False):
                raise RuntimeError(r)
            new_instance = cls(
                ip=r["ip"],
                city=r["city"],
                region=r["region"],
                country_name=r["country_name"],
                country_code=r["country_code"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                timezone=r["timezone"],
                utc_offset=r["utc_offset"],
            )
            cls._instance = new_instance
            return new_instance
        return None
