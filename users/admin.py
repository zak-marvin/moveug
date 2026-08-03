from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, DriverProfile


@admin.register(User)
class MoveUGUserAdmin(UserAdmin):
    list_display = ('username', 'phone_number', 'role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('MoveUG', {'fields': ('role', 'phone_number')}),
    )


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'vehicle_number', 'is_online', 'rating')
    list_filter = ('vehicle_type', 'is_online')
