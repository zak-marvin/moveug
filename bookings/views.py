from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.maps_service import get_distance_km
from core.pricing import calculate_system_price, estimate_duration_minutes
from .models import Booking, BookingItem, DriverBid, ChatMessage
from .serializers import BookingSerializer, DriverBidSerializer, ChatMessageSerializer
from .utils import get_driver_conflicts, get_job_window


class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'customer'


class IsDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'driver'


class CreateBookingWithPriceView(APIView):
    """Open-marketplace booking (not tied to an organization). Computes distance via
    core.maps_service (Google -> OSRM -> haversine fallback, in that order), then price
    and the estimated occupied-duration window used later for double-booking checks."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data

        required = ['pickup_lat', 'pickup_lng', 'dropoff_lat', 'dropoff_lng']
        missing = [f for f in required if data.get(f) in (None, '')]
        if missing:
            return Response({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

        distance_result = get_distance_km(
            data.get('pickup_lat'), data.get('pickup_lng'),
            data.get('dropoff_lat'), data.get('dropoff_lng'),
        )
        distance_km = distance_result['km']
        vehicle_type = data.get('vehicle_type', 'pickup')

        items = data.get('items', [])
        system_price = calculate_system_price(
            distance_km=distance_km,
            vehicle_type=vehicle_type,
            items=items,
            passenger_count=data.get('passenger_count', 0),
        )
        duration_minutes = estimate_duration_minutes(
            distance_km, vehicle_type, routing_duration_minutes=distance_result.get('duration_minutes')
        )

        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        move_date_raw = data.get('move_date')
        move_date = parse_datetime(move_date_raw) if move_date_raw else None
        if move_date is None:
            move_date = timezone.now()

        booking = Booking.objects.create(
            customer=request.user,
            pickup_lat=data.get('pickup_lat'),
            pickup_lng=data.get('pickup_lng'),
            dropoff_lat=data.get('dropoff_lat'),
            dropoff_lng=data.get('dropoff_lng'),
            pickup_address=data.get('pickup_address') or f"{data.get('pickup_lat')},{data.get('pickup_lng')}",
            dropoff_address=data.get('dropoff_address') or f"{data.get('dropoff_lat')},{data.get('dropoff_lng')}",
            distance_km=distance_km,
            distance_source=distance_result['source'],
            estimated_duration_minutes=duration_minutes,
            system_price=system_price,
            final_price=system_price,
            vehicle_type=vehicle_type,
            move_type=data.get('move_type', 'goods_only'),
            passenger_count=data.get('passenger_count', 0),
            status='bidding',
            move_date=move_date,
        )
        for item in items:
            if isinstance(item, dict):
                BookingItem.objects.create(booking=booking, item_type=item.get('item_type', ''),
                                            quantity=item.get('quantity', 1))
            else:
                BookingItem.objects.create(booking=booking, item_type=str(item), quantity=1)

        return Response({
            "message": "System price calculated",
            "booking_id": booking.id,
            "id": booking.id,
            "distance_km": round(distance_km, 2),
            "distance_source": distance_result['source'],
            "estimated_duration_minutes": duration_minutes,
            "system_price": int(system_price),
            "pickup_address": booking.pickup_address,
            "dropoff_address": booking.dropoff_address,
            "status": booking.status,
        }, status=201)


class AvailableJobsView(APIView):
    """Open marketplace jobs available for any driver to bid on (organization jobs
    are assigned directly via the organizations app instead). Each job includes
    the requesting driver's own bid on it, if any -- so the client can separate
    "not yet bid" from "already bid" without extra requests."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        jobs = Booking.objects.filter(status='bidding', organization__isnull=True).order_by('-id')[:50]
        results = []
        for job in jobs:
            my_bid = None
            if request.user.role == 'driver':
                my_bid = DriverBid.objects.filter(booking=job, driver=request.user).first()
            results.append({
                "booking": BookingSerializer(job).data,
                "my_bid": DriverBidSerializer(my_bid).data if my_bid else None,
            })
        return Response(results)


class MyBookingsView(APIView):
    """The customer's own posted marketplace jobs (org schedules are managed via
    the organizations endpoints instead, not shown here)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(customer=request.user, organization__isnull=True)
        return Response(BookingSerializer(bookings, many=True).data)


class BookingDetailView(APIView):
    """Single booking, for the customer who owns it or the driver assigned to it."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if request.user.id not in (booking.customer_id, booking.selected_driver_id):
            return Response({"error": "Not authorized to view this booking."}, status=403)
        return Response(BookingSerializer(booking).data)


class PlaceBidView(APIView):
    """Creates a driver's FIRST bid on a booking. If they already have one,
    points them at the edit endpoint instead of silently duplicating it."""
    permission_classes = [IsDriver]

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if booking.status != 'bidding':
            return Response({"error": "Bidding closed for this booking."}, status=400)
        bid_amount = request.data.get('bid_amount')
        if not bid_amount:
            return Response({"error": "bid_amount is required."}, status=400)

        existing = DriverBid.objects.filter(booking=booking, driver=request.user).first()
        if existing:
            return Response({
                "error": "You've already bid on this job -- edit your existing bid instead.",
                "bid_id": existing.id,
            }, status=400)

        bid = DriverBid.objects.create(
            booking=booking,
            driver=request.user,
            bid_amount=bid_amount,
            message=request.data.get('message', ''),
        )
        return Response(DriverBidSerializer(bid).data, status=201)


class MyBidView(APIView):
    """Driver's own bid on a specific booking -- powers the 'my bid' page where
    they can see accepted/rejected status and edit the price while still pending."""
    permission_classes = [IsDriver]

    def get(self, request, booking_id):
        bid = get_object_or_404(DriverBid, booking_id=booking_id, driver=request.user)
        return Response(DriverBidSerializer(bid).data)


class EditBidView(APIView):
    """Edit the price/message on your own bid. Only while the booking is still
    open for bidding -- once a driver's been accepted (or someone else has),
    the numbers are locked in."""
    permission_classes = [IsDriver]

    def patch(self, request, booking_id, bid_id):
        bid = get_object_or_404(DriverBid, id=bid_id, booking_id=booking_id)
        if bid.driver_id != request.user.id:
            return Response({"error": "This isn't your bid."}, status=403)
        if bid.booking.status != 'bidding':
            return Response({"error": "Bidding has closed on this job -- the price can't be changed anymore."},
                             status=400)
        bid_amount = request.data.get('bid_amount')
        if bid_amount:
            bid.bid_amount = bid_amount
        if 'message' in request.data:
            bid.message = request.data.get('message', '')
        bid.save(update_fields=['bid_amount', 'message'])
        return Response(DriverBidSerializer(bid).data)


class ListBidsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        bids = DriverBid.objects.filter(booking_id=booking_id).order_by('bid_amount')
        return Response(DriverBidSerializer(bids, many=True).data)


class AcceptBidView(APIView):
    """Only the booking's customer can accept a bid. This is where double-booking
    is actually enforced: we compute the job's occupied time window and check it
    against every other active job the chosen driver already has. Accepting one
    bid marks every other bid on this booking as rejected."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id, bid_id=None):
        booking = get_object_or_404(Booking, id=booking_id)
        if booking.customer_id != request.user.id:
            return Response({"error": "Only the customer who created this booking can accept a bid."}, status=403)

        bid_id = bid_id or request.data.get('bid_id')
        if not bid_id:
            return Response({"error": "bid_id required"}, status=400)
        bid = get_object_or_404(DriverBid, id=bid_id, booking=booking)

        start, end = get_job_window(booking.move_date, booking.estimated_duration_minutes)
        conflicts = get_driver_conflicts(bid.driver, start, end, exclude_booking_id=booking.id)
        if conflicts:
            return Response({
                "error": "This driver is already booked during that time window.",
                "conflicts": conflicts,
            }, status=409)

        booking.selected_driver = bid.driver
        booking.final_price = bid.bid_amount
        booking.status = 'accepted'
        booking.save(update_fields=['selected_driver', 'final_price', 'status'])

        bid.status = 'accepted'
        bid.save(update_fields=['status'])
        DriverBid.objects.filter(booking=booking).exclude(id=bid.id).update(status='rejected')

        return Response({
            "message": f"Accepted {bid.driver.username}",
            "driver": bid.driver.username,
            "final_price": booking.final_price,
            "status": booking.status,
        })


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        msgs = ChatMessage.objects.filter(booking_id=booking_id)
        return Response(ChatMessageSerializer(msgs, many=True).data)

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if request.user.id not in (booking.customer_id, booking.selected_driver_id):
            return Response({"error": "Only the customer or assigned driver can chat on this booking."}, status=403)
        message = request.data.get('message')
        if not message:
            return Response({"error": "message is required."}, status=400)
        msg = ChatMessage.objects.create(booking=booking, sender=request.user, message=message)
        return Response(ChatMessageSerializer(msg).data, status=201)


class UpdateStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if request.user.id not in (booking.customer_id, booking.selected_driver_id):
            return Response({"error": "Only the customer or assigned driver can update this booking."}, status=403)
        new_status = request.data.get('status')
        valid_statuses = [s[0] for s in Booking.STATUS]
        if new_status not in valid_statuses:
            return Response({"error": f"status must be one of {valid_statuses}"}, status=400)
        booking.status = new_status
        booking.save(update_fields=['status'])
        return Response({"message": f"Status updated to {booking.status}", "status": booking.status})
