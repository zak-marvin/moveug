from django.contrib import admin
from .models import Booking, BookingOccurrence, BookingItem, DriverBid, ChatMessage


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'selected_driver', 'organization', 'status', 'move_date', 'final_price')
    list_filter = ('status', 'vehicle_type', 'is_recurring')


@admin.register(BookingOccurrence)
class BookingOccurrenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'occurrence_date', 'assigned_driver', 'status')
    list_filter = ('status',)


admin.site.register(BookingItem)
admin.site.register(DriverBid)
admin.site.register(ChatMessage)
