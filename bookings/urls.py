from django.urls import path
from .views import (CreateBookingWithPriceView, AvailableJobsView, MyBookingsView, BookingDetailView,
                     PlaceBidView, MyBidView, EditBidView, ListBidsView, AcceptBidView,
                     ChatView, UpdateStatusView)

urlpatterns = [
    path('create/', CreateBookingWithPriceView.as_view(), name='create-booking'),
    path('jobs/', AvailableJobsView.as_view(), name='available-jobs'),
    path('mine/', MyBookingsView.as_view(), name='my-bookings'),
    path('<int:booking_id>/', BookingDetailView.as_view(), name='booking-detail'),
    path('<int:booking_id>/bids/', ListBidsView.as_view(), name='list-bids'),
    path('<int:booking_id>/bid/', PlaceBidView.as_view(), name='place-bid'),
    path('<int:booking_id>/bid/mine/', MyBidView.as_view(), name='my-bid'),
    path('<int:booking_id>/bid/<int:bid_id>/', EditBidView.as_view(), name='edit-bid'),
    path('<int:booking_id>/accept/<int:bid_id>/', AcceptBidView.as_view(), name='accept-bid'),
    path('<int:booking_id>/accept/', AcceptBidView.as_view(), name='accept-bid-alt'),
    path('<int:booking_id>/chat/', ChatView.as_view(), name='chat'),
    path('<int:booking_id>/status/', UpdateStatusView.as_view(), name='update-status'),
]
