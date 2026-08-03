from django.contrib import admin
from .models import Organization, OrganizationDriver, OrganizationBid


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'phone_number', 'is_active', 'created_at')


@admin.register(OrganizationDriver)
class OrganizationDriverAdmin(admin.ModelAdmin):
    list_display = ('organization', 'driver', 'is_active', 'joined_at')


@admin.register(OrganizationBid)
class OrganizationBidAdmin(admin.ModelAdmin):
    list_display = ('booking', 'driver', 'bid_amount', 'status', 'created_at')
    list_filter = ('status',)
