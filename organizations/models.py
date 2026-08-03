from django.conf import settings
from django.db import models


class Organization(models.Model):
    """A company that runs its own fleet of drivers on scheduled jobs
    (e.g. a school doing daily student transport, a shop doing recurring deliveries)."""
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_organizations')
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganizationDriver(models.Model):
    """Roster membership: which drivers belong to which organization's fleet."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roster')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization_memberships')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'driver')

    def __str__(self):
        return f"{self.driver} @ {self.organization}"


class OrganizationBid(models.Model):
    """Mini-bidding among an organization's own roster drivers for a recurring
    scheduled job (Booking.is_recurring=True, organization set). Separate from
    bookings.DriverBid, which is the open-marketplace bidding -- roster drivers
    only compete against each other here, never the general public."""
    STATUS = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]

    booking = models.ForeignKey('bookings.Booking', on_delete=models.CASCADE, related_name='organization_bids')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bid_amount = models.IntegerField(help_text="Price per scheduled run/occurrence")
    message = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('booking', 'driver')
        ordering = ['bid_amount']

    def __str__(self):
        return f"{self.driver} bid {self.bid_amount} on booking #{self.booking_id} ({self.status})"
