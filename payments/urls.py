from django.urls import path
from .views import InitiatePaymentView, CheckPaymentStatusView

urlpatterns = [
    path('<int:booking_id>/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('<int:booking_id>/status/', CheckPaymentStatusView.as_view(), name='payment-status'),
]
