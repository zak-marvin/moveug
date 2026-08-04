from django.db import models
from django.conf import settings


class Booking(models.Model):
    MOVE_TYPE = [('goods_only', 'Goods Only'), ('with_passenger', 'With Passenger')]
    VEHICLE_TYPE = [('boda', 'Boda Boda'), ('pickup', 'Pickup'), ('lorry', 'Lorry 3 ton')]
    STATUS = [
        ('bidding', 'Bidding Open'),
        ('accepted', 'Accepted'),
        ('picked', 'Picked Up'),
        ('on_the_way', 'On The Way'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    selected_driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='driver_bookings')

    # Multi-driver organizations: set when this job belongs to a company's own fleet
    # rather than the open marketplace. Recurring jobs generate one BookingOccurrence
    # per scheduled date below, each of which can be assigned a different driver.
    organization = models.ForeignKey('organizations.Organization', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='bookings')
    is_recurring = models.BooleanField(default=False)
    # For org recurring jobs opened to roster mini-bidding: how many driver slots need filling
    # (e.g. 3 vehicles needed to run the same weekly route in parallel, or to split across days).
    drivers_needed = models.PositiveIntegerField(default=1)

    move_type = models.CharField(max_length=15, choices=MOVE_TYPE, default='goods_only')
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE, default='pickup')
    passenger_count = models.IntegerField(default=0)  # for student relocation case

    # Google Maps fields
    pickup_address = models.CharField(max_length=255)
    pickup_lat = models.FloatField()
    pickup_lng = models.FloatField()
    dropoff_address = models.CharField(max_length=255)
    dropoff_lat = models.FloatField()
    dropoff_lng = models.FloatField()

    distance_km = models.FloatField(help_text="From Google Distance Matrix (or fallback)")
    distance_source = models.CharField(max_length=30, blank=True)
    # How long a driver is expected to be tied up on this job (travel + loading buffer).
    # This is the window used to block double-booking -- keep it realistic, not optimistic.
    estimated_duration_minutes = models.IntegerField(default=30)

    system_price = models.IntegerField(null=True, blank=True)  # Branch A price
    final_price = models.IntegerField(null=True, blank=True)  # What customer actually pays

    move_date = models.DateTimeField()
    status = models.CharField(max_length=15, choices=STATUS, default='bidding')
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Pickup/delivery safeguarding ---
    # A driver can't fake "picked up" or "delivered" without the customer physically
    # handing over these codes -- and a customer can't claim "never happened" when
    # they're the only one who could have given the driver the code in the first
    # place. Generated once at booking creation, never shown to the driver directly
    # (see bookings.views.GetBookingOtpView, which only the customer can call).
    pickup_otp = models.CharField(max_length=6, blank=True)
    delivery_otp = models.CharField(max_length=6, blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    on_the_way_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Overlay flag rather than a status value, so 'delivered' (used for payment
    # release elsewhere) stays meaningful even while a dispute is under review.
    is_disputed = models.BooleanField(default=False)
    dispute_reason = models.CharField(max_length=500, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} ({self.status})"


class StatusEvent(models.Model):
    """Immutable audit trail: every status change on a booking, who made it, and
    where they were standing at the time (when the client supplies GPS). This is
    the record you'd point to if a customer and driver disagree about what
    actually happened -- it can't be edited after the fact, only appended to."""
    STATUS_CHOICES = Booking.STATUS + [('disputed', 'Disputed')]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='status_events')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Booking #{self.booking_id} -> {self.status} @ {self.created_at:%Y-%m-%d %H:%M}"


class BookingOccurrence(models.Model):
    """One scheduled date for a recurring organization booking (e.g. Monday's school run).
    Each occurrence can be assigned its own driver from the org's roster."""
    STATUS = [
        ('scheduled', 'Scheduled'),
        ('assigned', 'Driver Assigned'),
        ('picked', 'Picked Up'),
        ('on_the_way', 'On The Way'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='occurrences')
    occurrence_date = models.DateTimeField()
    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='driver_occurrences')
    status = models.CharField(max_length=15, choices=STATUS, default='scheduled')
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Same safeguarding as Booking (see the comment there) -- each occurrence is a
    # separate physical run, so it gets its own codes rather than sharing the parent
    # booking's. Generated when a driver is assigned to this specific date.
    pickup_otp = models.CharField(max_length=6, blank=True)
    delivery_otp = models.CharField(max_length=6, blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    on_the_way_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    is_disputed = models.BooleanField(default=False)
    dispute_reason = models.CharField(max_length=500, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['occurrence_date']

    def __str__(self):
        return f"Occurrence for Booking #{self.booking_id} on {self.occurrence_date:%Y-%m-%d}"


class OccurrenceStatusEvent(models.Model):
    """Same audit-trail idea as StatusEvent, scoped to a single occurrence run."""
    STATUS_CHOICES = BookingOccurrence.STATUS + [('disputed', 'Disputed')]

    occurrence = models.ForeignKey(BookingOccurrence, on_delete=models.CASCADE, related_name='status_events')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Occurrence #{self.occurrence_id} -> {self.status} @ {self.created_at:%Y-%m-%d %H:%M}"


class BookingItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=50)  # Fridge, Bed, Box
    quantity = models.IntegerField(default=1)


class DriverBid(models.Model):
    STATUS = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='bids')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bid_amount = models.IntegerField()
    message = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['bid_amount']
        unique_together = ('booking', 'driver')  # one bid per driver per booking -- edit it, don't duplicate it


class ChatMessage(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='chats')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
