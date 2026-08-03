from django.db import models


class Payment(models.Model):
    booking = models.OneToOneField('bookings.Booking', on_delete=models.CASCADE, related_name='payment')
    total_amount = models.IntegerField()
    commission_15 = models.IntegerField()
    driver_earnings = models.IntegerField()

    # MoMo Collections (customer -> MoveUG)
    collection_reference_id = models.UUIDField(null=True, blank=True)
    collection_status = models.CharField(max_length=20, default='PENDING')  # PENDING, SUCCESSFUL, FAILED

    # MoMo Disbursements (MoveUG -> driver)
    disbursement_reference_id = models.UUIDField(null=True, blank=True)
    disbursement_status = models.CharField(max_length=20, default='PENDING')

    momo_txn_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for booking #{self.booking_id} ({self.collection_status})"
