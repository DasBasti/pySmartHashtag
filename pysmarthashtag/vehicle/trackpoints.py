"""Per-trip GPS trackpoint models for pysmarthashtag.

The Smart cloud exposes a per-trip GPS trail at
``/vehicle-history-service/journal-service/vehicle/status/history/{vin}``
on the same ``apiv2.ecloudeu.com`` host as journalLogV4. The endpoint
returns a list of ``{lat, lon}`` samples scaled in **milliarcseconds**
(divide by 3,600,000 for WGS84 decimal degrees — same scaling as
:class:`pysmarthashtag.vehicle.position.Position`).

Unlike ``journalLogV4``, this endpoint does NOT require the
``grant_journal_authorization`` per-session handshake — calling that
defensively before every fetch would burn an extra cloud round-trip and
risks transient ``7065`` errors on back-to-back grants.

Cloud reports the list newest-first (``pagination.direction = "desc"``);
:meth:`pysmarthashtag.account.SmartAccount.get_trip_trackpoints`
reverses to chronological order before returning, so consumers don't
need to know the wire format.
"""

from dataclasses import dataclass
from typing import Any, Optional

# The cloud reports lat/lon as integer milliarcseconds. Convert to decimal
# degrees with ``mas / 3_600_000`` — same scaling already used by
# :class:`pysmarthashtag.vehicle.position.Position`.
_MAS_PER_DEGREE = 3_600_000.0


@dataclass(frozen=True)
class Trackpoint:
    """One GPS sample from a trip's recorded track.

    The cloud's per-point payload is *only* lat/lon — no timestamp, no
    SoC, no speed, no heading, no altitude. Both fields are nullable so a
    degraded cloud entry whose ``position`` block is missing one or both
    axes can still be recorded as a placeholder sample (sequence
    integrity matters more than per-point completeness — one bad sample
    shouldn't drop the rest of the trip).
    """

    lat: Optional[float] = None
    """Latitude in decimal degrees (cloud reports milliarcseconds; we
    divide by 3,600,000)."""

    lon: Optional[float] = None
    """Longitude in decimal degrees, same scaling as :attr:`lat`."""


@dataclass(frozen=True)
class TripTrackpoints:
    """All GPS trackpoints for one trip, as returned by the history endpoint.

    :attr:`points` is in *chronological* order — index 0 is the trip's
    start sample, the last index is the end. The cloud transmits the
    list reverse-chronologically (``pagination.direction = "desc"``);
    :meth:`pysmarthashtag.account.SmartAccount.get_trip_trackpoints`
    reverses at the wrapper boundary so callers don't need to know the
    wire format.

    :attr:`total_size` is the cloud's reported ``totleSize`` (sic — same
    typo as journalLogV4). The default ``page_size=500`` matches the cap
    the cloud advertises in its own ``pagination`` block; if a future
    trip ever exceeds that, the wrapper logs a WARNING and the caller
    still receives the truncated head.
    """

    points: list[Trackpoint]
    """Trackpoints in chronological order (cloud sends desc; we reverse)."""

    total_size: int = 0
    """Cloud-reported total points for this trip (``data.pagination.totleSize``)."""


def _trackpoint_from_cloud(item: Any) -> Trackpoint:
    """Map one ``data.list`` entry to a :class:`Trackpoint`.

    Defensive against degraded shapes: a missing ``basicVehicleStatus``
    or ``position`` block, or an entry that isn't a dict at all, yields
    ``Trackpoint(lat=None, lon=None)`` rather than raising.
    """
    if not isinstance(item, dict):
        return Trackpoint()
    basic = item.get("basicVehicleStatus") or {}
    position = basic.get("position") if isinstance(basic, dict) else None
    if not isinstance(position, dict):
        return Trackpoint()
    lat_mas = position.get("latitude")
    lon_mas = position.get("longitude")
    lat = lat_mas / _MAS_PER_DEGREE if isinstance(lat_mas, (int, float)) else None
    lon = lon_mas / _MAS_PER_DEGREE if isinstance(lon_mas, (int, float)) else None
    return Trackpoint(lat=lat, lon=lon)


def parse_trackpoints_response(response_data: Any) -> TripTrackpoints:
    """Build a :class:`TripTrackpoints` from a journal-service ``history`` body.

    ``response_data`` is the full JSON dict returned by the endpoint
    (``code`` / ``message`` / ``data``). Three benign-empty shapes all
    map to ``TripTrackpoints(points=[], total_size=0)``:

    * ``code: "1000"`` with ``data.list = []`` and ``totleSize: 0``
      (cloud has no GPS trail for this trip)
    * ``code: "1000"`` with ``data: null`` (alternate cloud-side empty)
    * ``code: "8153"`` ("data unavailable" — propagates as
      :class:`httpx.HTTPStatusError` from the SDK; the caller catches
      it and falls back to this empty shape)

    Cloud direction is ``desc`` (newest first); the returned
    :attr:`TripTrackpoints.points` are reversed to chronological so
    every consumer sees the same orientation.
    """
    if not isinstance(response_data, dict):
        return TripTrackpoints(points=[], total_size=0)
    data = response_data.get("data")
    if not isinstance(data, dict):
        return TripTrackpoints(points=[], total_size=0)
    items_raw = data.get("list")
    items = items_raw if isinstance(items_raw, list) else []
    pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
    total_raw = pagination.get("totleSize") if isinstance(pagination, dict) else None
    total_size = int(total_raw) if isinstance(total_raw, (int, float)) else len(items)

    if not items:
        return TripTrackpoints(points=[], total_size=total_size)

    # Cloud sends ``direction: "desc"`` (newest-first). Reverse here so
    # callers always see chronological samples — don't double-reverse
    # downstream.
    points = [_trackpoint_from_cloud(item) for item in reversed(items)]
    return TripTrackpoints(points=points, total_size=total_size)
