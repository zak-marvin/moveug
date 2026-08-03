"""
Double-booking protection.

A driver is "occupied" on a Booking from booking.move_date for booking.estimated_duration_minutes,
and on a BookingOccurrence from occurrence.occurrence_date for that occurrence's parent
booking.estimated_duration_minutes. Before assigning a driver to *anything* (accepting a bid,
or assigning them to a scheduled org occurrence), we check for time-window overlap against
every other active job that driver is already on, across BOTH tables.
"""
from datetime import timedelta

# Statuses where the driver is genuinely tied up (not yet delivered/cancelled).
ACTIVE_BOOKING_STATUSES = ['accepted', 'picked', 'on_the_way']
ACTIVE_OCCURRENCE_STATUSES = ['assigned']


def _windows_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def get_driver_conflicts(driver, start_time, end_time, exclude_booking_id=None, exclude_occurrence_id=None):
    """
    Returns a list of conflicting jobs (empty list = no conflict = safe to assign).
    Import models lazily to avoid app-loading order issues.
    """
    from .models import Booking, BookingOccurrence

    conflicts = []

    booking_qs = Booking.objects.filter(selected_driver=driver, status__in=ACTIVE_BOOKING_STATUSES)
    if exclude_booking_id:
        booking_qs = booking_qs.exclude(id=exclude_booking_id)
    for b in booking_qs:
        b_start = b.move_date
        b_end = b_start + timedelta(minutes=b.estimated_duration_minutes or 30)
        if _windows_overlap(start_time, end_time, b_start, b_end):
            conflicts.append({
                "type": "booking",
                "id": b.id,
                "starts": b_start,
                "ends": b_end,
                "detail": f"Driver already assigned to booking #{b.id} ({b.pickup_address} -> {b.dropoff_address})",
            })

    occurrence_qs = BookingOccurrence.objects.filter(
        assigned_driver=driver, status__in=ACTIVE_OCCURRENCE_STATUSES
    ).select_related('booking')
    if exclude_occurrence_id:
        occurrence_qs = occurrence_qs.exclude(id=exclude_occurrence_id)
    for o in occurrence_qs:
        o_start = o.occurrence_date
        o_end = o_start + timedelta(minutes=o.booking.estimated_duration_minutes or 30)
        if _windows_overlap(start_time, end_time, o_start, o_end):
            conflicts.append({
                "type": "occurrence",
                "id": o.id,
                "booking_id": o.booking_id,
                "starts": o_start,
                "ends": o_end,
                "detail": f"Driver already scheduled for occurrence #{o.id} of booking #{o.booking_id}",
            })

    return conflicts


def get_job_window(move_date, estimated_duration_minutes):
    return move_date, move_date + timedelta(minutes=estimated_duration_minutes or 30)
