from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [('customer', 'Customer'), ('driver', 'Driver'), ('org_admin', 'Organization Admin')]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    phone_number = models.CharField(max_length=15, unique=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

class User(AbstractUser):
    ROLE_CHOICES = [('customer', 'Customer'), ('driver', 'Driver'), ('org_admin', 'Organization Admin')]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    phone_number = models.CharField(max_length=15, unique=True)

    REQUIRED_FIELDS = ['phone_number']   # <- add this line

    def __str__(self):
        return f"{self.username} ({self.role})"
class DriverProfile(models.Model):
    VEHICLE_CHOICES = [('boda', 'Boda Boda'), ('pickup', 'Pickup'), ('lorry', 'Lorry 3 ton')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    license_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES, default='pickup')
    vehicle_number = models.CharField(max_length=20, unique=True)
    is_online = models.BooleanField(default=False)
    current_lat = models.FloatField(null=True, blank=True)
    current_lng = models.FloatField(null=True, blank=True)
    rating = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user.username} - {self.vehicle_type}"
