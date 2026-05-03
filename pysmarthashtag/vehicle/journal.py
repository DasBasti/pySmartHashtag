"""Trip journal models for pysmarthashtag.

The Smart cloud exposes a per-vehicle trip log at
``/geelyTCAccess/tcservices/vehicle/status/journalLogV4/{vin}`` whose
response carries an array of trips with start/end timestamps, distances,
energy figures, speeds, and lat/lon trackpoints, plus optional
server-side reverse-geocoded start/end addresses.

The address fields are nullable: in EU-region accounts the cloud almost
never populates them, so consumers that need street strings should
reverse-geocode client-side from ``start_position`` /
``end_position`` (raw integer lat/lon in milliarcseconds; divide by
3,600,000 for WGS84 decimal degrees).

This module models a single most-recent trip plus a total trip counter,
matching the surface area of the HelloSmart HA integration so consumers
can build sensors on top of it without further parsing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, get_field_as_type

_LOGGER = logging.getLogger(__name__)


def _parse_epoch_ms(value: Any) -> Optional[datetime]:
    """Parse a millisecond epoch into a UTC-aware ``datetime``.

    Tz-aware so HA's TIMESTAMP device class (used by sensor entities that
    expose start/end times) accepts the value — naive datetimes show up
    as ``unavailable``.
    """
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


@dataclass
class TripJournal:
    """The most-recent trip from the vehicle's journal log."""

    trip_id: str = ""
    """Cloud-assigned trip identifier."""

    distance: Optional[ValueWithUnit] = None
    """Trip distance."""

    duration: Optional[int] = None
    """Trip duration in seconds (as the cloud reports it)."""

    energy_consumption: Optional[ValueWithUnit] = None
    """Total energy consumed during the trip."""

    avg_energy_consumption: Optional[ValueWithUnit] = None
    """Average energy consumption (kWh / 100 km)."""

    avg_speed: Optional[ValueWithUnit] = None
    """Average trip speed."""

    max_speed: Optional[ValueWithUnit] = None
    """Maximum trip speed."""

    start_time: Optional[datetime] = None
    """Trip start time."""

    end_time: Optional[datetime] = None
    """Trip end time."""

    regenerated_energy: Optional[ValueWithUnit] = None
    """Energy recovered via regenerative braking."""

    start_address: str = ""
    """Server-side reverse-geocoded address at trip start.

    Nullable: in EU-region accounts the cloud almost never populates this
    field. Use ``start_position`` for the raw lat/lon and reverse-geocode
    client-side if a string is needed.
    """

    end_address: str = ""
    """Server-side reverse-geocoded address at trip end. Same caveat as
    ``start_address`` — usually empty in EU.
    """

    start_position: Optional[tuple[int, int]] = None
    """Trip-start coordinates as ``(latitude, longitude)`` in raw
    milliarcseconds (divide each by 3,600,000 for WGS84 decimal degrees).
    Derived from ``trackpoints[0].position`` in the cloud response.
    Same scaling as :class:`pysmarthashtag.vehicle.position.Position`.
    """

    end_position: Optional[tuple[int, int]] = None
    """Trip-end coordinates as ``(latitude, longitude)`` in raw
    milliarcseconds. Derived from the last entry of ``trackpoints``.
    """

    total_trips: Optional[int] = None
    """Total number of trips known to the cloud (top-level on the response)."""

    @classmethod
    def from_response(cls, response_data: dict) -> Optional["TripJournal"]:
        """Build a TripJournal from a ``journalLogV4`` response body.

        ``response_data`` is the full JSON dict returned by the endpoint,
        i.e. the object containing ``code`` / ``message`` / ``data``.
        The cloud returns ``data.list`` (most-recent first per
        ``data.pagination.sortField/direction``) and
        ``data.pagination.totleSize`` (sic — Geely's typo) for the total
        trip count. Returns ``None`` if the response carries no usable
        journal entry.
        """
        if not isinstance(response_data, dict):
            return None
        journal = response_data.get("data") or {}
        logs = journal.get("list") or []
        pagination = journal.get("pagination") or {}

        total_trips = get_field_as_type(pagination, "totleSize", int)

        if not logs:
            if total_trips is not None:
                # Vehicle has zero recorded trips but cloud responded — return
                # an empty record so consumers can still see total_trips=0.
                return cls(total_trips=total_trips)
            return None

        first = logs[0] or {}
        # The cloud reverse-geocodes addresses asynchronously; the most
        # recent trip often has ``tripStartAddr/tripEndAddr`` = null for
        # minutes to hours after the trip ends. We deliberately surface
        # the empty values rather than splicing addresses from a prior
        # trip — the next refresh will pick them up once the cloud
        # geocoder catches up.

        distance = get_field_as_type(first, "traveledDistance", float)
        # The cloud's ``electricConsumption`` field is the per-trip average
        # in kWh/100km (a 2 km trip showing 25.0 corresponds to ~0.5 kWh
        # consumed — consistent with kWh/100km, not kWh total).
        avg_energy = get_field_as_type(first, "electricConsumption", float)
        avg_speed = get_field_as_type(first, "avgSpeed", float)
        regen = get_field_as_type(first, "regeneratedEnergy", float)

        # Cloud doesn't include duration; compute from start/end timestamps.
        start_ms = get_field_as_type(first, "startTime", int)
        end_ms = get_field_as_type(first, "endTime", int)
        duration_s: Optional[int] = None
        if start_ms is not None and end_ms is not None and end_ms >= start_ms:
            duration_s = (end_ms - start_ms) // 1000

        # Compute total trip energy from avg consumption × distance / 100.
        energy_total: Optional[float] = None
        if avg_energy is not None and distance is not None:
            energy_total = round(avg_energy * distance / 100, 3)

        # Extract first/last trackpoint positions (raw int milliarcseconds).
        trackpoints = first.get("trackpoints") or []
        start_pos: Optional[tuple[int, int]] = None
        end_pos: Optional[tuple[int, int]] = None
        if trackpoints:
            first_tp = (trackpoints[0] or {}).get("position") or {}
            last_tp = (trackpoints[-1] or {}).get("position") or {}
            tp_start_lat = get_field_as_type(first_tp, "latitude", int)
            tp_start_lon = get_field_as_type(first_tp, "longitude", int)
            tp_end_lat = get_field_as_type(last_tp, "latitude", int)
            tp_end_lon = get_field_as_type(last_tp, "longitude", int)
            if tp_start_lat is not None and tp_start_lon is not None:
                start_pos = (tp_start_lat, tp_start_lon)
            if tp_end_lat is not None and tp_end_lon is not None:
                end_pos = (tp_end_lat, tp_end_lon)

        return cls(
            trip_id=str(first.get("tripId", "")),
            distance=ValueWithUnit(distance, "km") if distance is not None else None,
            duration=duration_s,
            energy_consumption=(
                ValueWithUnit(energy_total, "kWh") if energy_total is not None else None
            ),
            avg_energy_consumption=(
                ValueWithUnit(avg_energy, "kWh/100km") if avg_energy is not None else None
            ),
            avg_speed=ValueWithUnit(avg_speed, "km/h") if avg_speed is not None else None,
            max_speed=None,  # Not provided by the cloud; would require trackpoint analysis.
            start_time=_parse_epoch_ms(start_ms),
            end_time=_parse_epoch_ms(end_ms),
            regenerated_energy=(
                ValueWithUnit(regen, "kWh") if regen is not None else None
            ),
            start_address=str(first.get("tripStartAddr", "") or ""),
            end_address=str(first.get("tripEndAddr", "") or ""),
            start_position=start_pos,
            end_position=end_pos,
            total_trips=total_trips,
        )
