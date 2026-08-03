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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} ({self.status})"


class BookingOccurrence(models.Model):
    """One scheduled date for a recurring organization booking (e.g. Monday's school run).
    Each occurrence can be assigned its own driver from the org's roster."""
    STATUS = [
        ('scheduled', 'Scheduled'),
        ('assigned', 'Driver Assigned'),
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

    class Meta:
        ordering = ['occurrence_date']

    def __str__(self):
        return f"Occurrence for Booking #{self.booking_id} on {self.occurrence_date:%Y-%m-%d}"


class BookingItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=50)  # Fridge, Bed, Box
    quantity = models.IntegerField(default=1)


class DriverBid(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='bids')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bid_amount = models.IntegerField()
    message = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['bid_amount']


class ChatMessage(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='chats')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
