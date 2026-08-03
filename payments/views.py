from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from .models import Payment
from .momo_service import request_to_pay, get_collection_status, transfer_to_driver


class InitiatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if booking.customer_id != request.user.id:
            return Response({"error": "Only the customer who made this booking can pay for it."}, status=403)
        if not booking.final_price:
            return Response({"error": "Booking has no final price yet."}, status=400)

        total = booking.final_price
        commission = int(total * 0.15)
        driver_earn = total - commission

        payment, _ = Payment.objects.get_or_create(
            booking=booking,
            defaults={"total_amount": total, "commission_15": commission, "driver_earnings": driver_earn},
        )

        customer_phone = request.data.get("phone", request.user.phone_number)
        result = request_to_pay(total, customer_phone, external_id=booking.id)
        payment.collection_reference_id = result["reference_id"]
        payment.save(update_fields=['collection_reference_id'])

        return Response({
            "message": "MoMo prompt sent to customer",
            "reference_id": result["reference_id"],
            "simulated": result.get("simulated", False),
        })


class CheckPaymentStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if request.user.id not in (booking.customer_id, booking.selected_driver_id):
            return Response({"error": "Not authorized to view this payment."}, status=403)

        payment = getattr(booking, 'payment', None)
        if not payment:
            return Response({"error": "No payment has been initiated for this booking yet."}, status=404)

        status_res = get_collection_status(str(payment.collection_reference_id))
        payment_status = status_res.get("status", "PENDING")
        payment.collection_status = payment_status
        payment.save(update_fields=['collection_status'])

        if payment_status == "SUCCESSFUL" and payment.disbursement_status != "SUCCESSFUL":
            driver_profile = getattr(booking.selected_driver, 'driver_profile', None)
            driver_phone = booking.selected_driver.phone_number if booking.selected_driver else None
            if driver_phone:
                transfer_res = transfer_to_driver(payment.driver_earnings, driver_phone)
                payment.disbursement_reference_id = transfer_res["reference_id"]
                payment.disbursement_status = "PENDING"
                payment.save(update_fields=['disbursement_reference_id', 'disbursement_status'])
                return Response({"payment_status": payment_status, "driver_payout_initiated": True})

        return Response({"payment_status": payment_status, **status_res})
