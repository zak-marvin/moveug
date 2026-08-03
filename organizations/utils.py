"""
Turns a "days + time per week" schedule description into concrete occurrence
datetimes. This is what lets an org owner say "Mon/Wed/Fri at 7:00am for 4 weeks"
instead of typing out every individual date.
"""
from datetime import datetime, timedelta, time as dt_time

from django.utils import timezone

DAY_NAME_TO_INT = {
    'mon': 0, 'monday': 0,
    'tue': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2,
    'thu': 3, 'thursday': 3,
    'fri': 4, 'friday': 4,
    'sat': 5, 'saturday': 5,
    'sun': 6, 'sunday': 6,
}


def generate_weekly_occurrences(start_date, weeks, days_of_week, time_of_day):
    """
    start_date: date object -- first day of the scheduling window
    weeks: int -- how many weeks forward to generate
    days_of_week: list of day names, e.g. ["mon", "wed", "fri"]
    time_of_day: "HH:MM" string, e.g. "07:00"
    Returns a sorted list of timezone-aware datetimes.
    Raises KeyError if a day name isn't recognized.
    """
    hour, minute = (int(p) for p in time_of_day.split(':')[:2])
    day_ints = {DAY_NAME_TO_INT[d.strip().lower()] for d in days_of_week}

    occurrences = []
    for offset in range(weeks * 7):
        d = start_date + timedelta(days=offset)
        if d.weekday() in day_ints:
            naive = datetime.combine(d, dt_time(hour, minute))
            occurrences.append(timezone.make_aware(naive) if timezone.is_naive(naive) else naive)
    return sorted(occurrences)
