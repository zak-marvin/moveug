from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'total_amount', 'commission_15', 'driver_earnings',
                     'collection_status', 'disbursement_status', 'created_at')
