"""
Single source of truth for distance calculation.
Order of preference: Google Distance Matrix (real road + traffic) -> OSRM (free road routing) -> haversine estimate.
Every other app (bookings, organizations) must go through get_distance_km() -- do not
reimplement distance logic elsewhere, that's how this drifted out of sync last time.
"""
import math
import requests
from django.conf import settings


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance. Used only as a last-resort fallback."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _google_distance_km(lat1, lon1, lat2, lon2):
    google_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    if not google_key:
        return None
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{lat1},{lon1}",
            "destinations": f"{lat2},{lon2}",
            "key": google_key,
        }
        r = requests.get(url, params=params, timeout=8).json()
        if r.get('status') == 'OK' and r['rows'][0]['elements'][0]['status'] == 'OK':
            element = r['rows'][0]['elements'][0]
            return {
                "km": element['distance']['value'] / 1000.0,
                "duration_minutes": element['duration']['value'] / 60.0,
                "source": "google",
            }
    except Exception:
        pass
    return None


def _osrm_distance_km(lat1, lon1, lat2, lon2):
    servers = [
        f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false",
        f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false",
    ]
    for url in servers:
        try:
            res = requests.get(url, timeout=10).json()
            if res.get('code') == 'Ok':
                route = res['routes'][0]
                return {
                    "km": route['distance'] / 1000.0,
                    "duration_minutes": route['duration'] / 60.0,
                    "source": "osrm",
                }
        except Exception:
            continue
    return None


def get_distance_km(lat1, lon1, lat2, lon2):
    """
    Returns dict: {"km": float, "duration_minutes": float|None, "source": str}
    duration_minutes is the routing engine's own travel-time estimate when available
    (Google/OSRM); it's None for the haversine fallback since we don't have real
    road-speed data there -- callers should use core.pricing.estimate_duration_minutes
    instead in that case.
    """
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)

    google = _google_distance_km(lat1, lon1, lat2, lon2)
    if google:
        return google

    osrm = _osrm_distance_km(lat1, lon1, lat2, lon2)
    if osrm:
        return osrm

    straight = haversine_km(lat1, lon1, lat2, lon2)
    return {"km": straight * 1.4, "duration_minutes": None, "source": "haversine_estimate"}


def is_within_range(lat1, lon1, lat2, lon2, max_km=0.5):
    """Straight-line proximity check -- used to confirm a driver's phone is actually
    near the pickup/dropoff point before letting them advance a job's status.
    Deliberately uses haversine (not the routed distance) since we just need "are you
    standing here", not "how far by road". max_km should be generous enough to absorb
    normal GPS drift/parking distance, not tight enough to block legitimate use."""
    return haversine_km(lat1, lon1, lat2, lon2) <= max_km
