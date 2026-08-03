"""
Single source of truth for pricing and duration estimation.
bookings/utils.py used to duplicate this with its own haversine-only copy -- don't
reintroduce that. Everything routes through here.
"""

VEHICLE_RATES_PER_KM = {
    "boda": 2000,
    "pickup": 3000,
    "lorry": 6000,
}

AVERAGE_SPEED_KMH = {
    "boda": 35,
    "pickup": 30,
    "lorry": 25,
}

ITEM_FEES = {
    "sofa": 10000,
    "bed": 15000,
    "fridge": 15000,
    "table": 5000,
    "chairs": 5000,
    "boxes": 3000,
    "mattress": 8000,
    "tv": 5000,
}

BASE_FEE = 5000
LOADING_BUFFER_MINUTES = 20  # time to load/unload goods, added to every job's occupied window


def calculate_system_price(distance_km, vehicle_type="pickup", items=None, passenger_count=0):
    items = items or []
    vehicle_type = str(vehicle_type).lower()
    rate = VEHICLE_RATES_PER_KM.get(vehicle_type, VEHICLE_RATES_PER_KM["pickup"])
    distance_cost = float(distance_km) * rate

    items_cost = 0
    for it in items:
        if isinstance(it, dict):
            name = it.get('item_type') or it.get('name') or it.get('type') or ''
        else:
            name = str(it)
        name = name.lower().strip()
        matched = False
        for key, fee in ITEM_FEES.items():
            if key in name:
                items_cost += fee
                matched = True
                break
        if not matched and name:
            items_cost += 3000

    passenger_fee = int(passenger_count or 0) * 2000

    return int(distance_cost + items_cost + passenger_fee + BASE_FEE)


def estimate_duration_minutes(distance_km, vehicle_type="pickup", routing_duration_minutes=None):
    """
    Prefer the routing engine's real duration (Google/OSRM) when we have it.
    Fall back to distance / average-speed when we only have a haversine estimate.
    Always add a loading/unloading buffer -- this is the window used to block
    double-booking, so it needs to be generous rather than optimistic.
    """
    if routing_duration_minutes:
        travel_minutes = float(routing_duration_minutes)
    else:
        speed = AVERAGE_SPEED_KMH.get(str(vehicle_type).lower(), AVERAGE_SPEED_KMH["pickup"])
        travel_minutes = (float(distance_km) / speed) * 60

    return int(round(travel_minutes + LOADING_BUFFER_MINUTES))
