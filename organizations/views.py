from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.maps_service import get_distance_km
from core.pricing import calculate_system_price, estimate_duration_minutes
from bookings.models import Booking, BookingOccurrence
from bookings.serializers import BookingSerializer, BookingOccurrenceSerializer
from bookings.utils import get_driver_conflicts, get_job_window
from users.models import User
from .models import Organization, OrganizationDriver, OrganizationBid
from .serializers import OrganizationSerializer, OrganizationDriverSerializer, OrganizationBidSerializer
from .utils import generate_weekly_occurrences


def _get_owned_org(request, organization_id):
    org = get_object_or_404(Organization, id=organization_id)
    if org.owner_id != request.user.id:
        return None
    return org


def _is_active_roster_member(organization, driver):
    return OrganizationDriver.objects.filter(organization=organization, driver=driver, is_active=True).exists()


class OrganizationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orgs = Organization.objects.filter(owner=request.user)
        return Response(OrganizationSerializer(orgs, many=True).data)

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save(owner=request.user)
        return Response(OrganizationSerializer(org).data, status=201)


class OrganizationDriverRosterView(APIView):
    """Add/list drivers on an organization's fleet roster. The driver is looked up
    by phone_number (must already have registered with role='driver')."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, organization_id):
        org = _get_owned_org(request, organization_id)
        if not org:
            return Response({"error": "Organization not found or not owned by you."}, status=404)
        roster = OrganizationDriver.objects.filter(organization=org)
        return Response(OrganizationDriverSerializer(roster, many=True).data)

    def post(self, request, organization_id):
        org = _get_owned_org(request, organization_id)
        if not org:
            return Response({"error": "Organization not found or not owned by you."}, status=404)

        phone_number = request.data.get('phone_number')
        driver_id = request.data.get('driver_id')
        driver = None
        if phone_number:
            driver = User.objects.filter(phone_number=phone_number, role='driver').first()
        elif driver_id:
            driver = User.objects.filter(id=driver_id, role='driver').first()

        if not driver:
            return Response({"error": "No driver account found with that phone_number/driver_id "
                                       "(they must register as role='driver' first)."}, status=404)

        membership, created = OrganizationDriver.objects.get_or_create(organization=org, driver=driver)
        if not created:
            membership.is_active = True
            membership.save(update_fields=['is_active'])
        return Response(OrganizationDriverSerializer(membership).data, status=201)


class OrganizationScheduleCreateView(APIView):
    """
    Create a weekly recurring job and open it to mini-bidding among the org's own
    roster. Input describes the schedule the way a dispatcher thinks about it --
    days of the week + a time + how many weeks -- rather than a raw list of dates.

    Body:
      pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, vehicle_type
      days_of_week: ["mon", "wed", "fri"]
      time_of_day: "07:00"
      start_date: "2026-08-04"
      weeks: 4                 (optional, default 4)
      drivers_needed: 2        (optional, default 1)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, organization_id):
        org = _get_owned_org(request, organization_id)
        if not org:
            return Response({"error": "Organization not found or not owned by you."}, status=404)

        data = request.data
        required = ['pickup_lat', 'pickup_lng', 'dropoff_lat', 'dropoff_lng',
                    'days_of_week', 'time_of_day', 'start_date']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

        try:
            start_date = date.fromisoformat(data['start_date'])
        except ValueError:
            return Response({"error": "start_date must be in YYYY-MM-DD format."}, status=400)

        weeks = int(data.get('weeks', 4))
        try:
            occurrence_dates = generate_weekly_occurrences(
                start_date, weeks, data['days_of_week'], data['time_of_day']
            )
        except KeyError as e:
            return Response({"error": f"Unrecognized day name: {e}. Use mon/tue/wed/thu/fri/sat/sun."}, status=400)
        except (ValueError, IndexError):
            return Response({"error": "time_of_day must be in HH:MM format."}, status=400)

        if not occurrence_dates:
            return Response({"error": "No occurrences generated -- check days_of_week/start_date/weeks."}, status=400)

        distance_result = get_distance_km(
            data.get('pickup_lat'), data.get('pickup_lng'),
            data.get('dropoff_lat'), data.get('dropoff_lng'),
        )
        vehicle_type = data.get('vehicle_type', 'pickup')
        system_price = calculate_system_price(
            distance_km=distance_result['km'], vehicle_type=vehicle_type,
            items=data.get('items', []), passenger_count=data.get('passenger_count', 0),
        )
        duration_minutes = estimate_duration_minutes(
            distance_result['km'], vehicle_type, routing_duration_minutes=distance_result.get('duration_minutes')
        )
        drivers_needed = int(data.get('drivers_needed', 1))

        booking = Booking.objects.create(
            customer=request.user,
            organization=org,
            is_recurring=True,
            drivers_needed=drivers_needed,
            pickup_lat=data.get('pickup_lat'), pickup_lng=data.get('pickup_lng'),
            dropoff_lat=data.get('dropoff_lat'), dropoff_lng=data.get('dropoff_lng'),
            pickup_address=data.get('pickup_address') or f"{data.get('pickup_lat')},{data.get('pickup_lng')}",
            dropoff_address=data.get('dropoff_address') or f"{data.get('dropoff_lat')},{data.get('dropoff_lng')}",
            distance_km=distance_result['km'],
            distance_source=distance_result['source'],
            estimated_duration_minutes=duration_minutes,
            system_price=system_price,
            final_price=system_price,
            vehicle_type=vehicle_type,
            move_type=data.get('move_type', 'goods_only'),
            passenger_count=data.get('passenger_count', 0),
            status='bidding',  # open to roster mini-bidding until enough drivers are accepted
            move_date=occurrence_dates[0],
        )

        occurrences = [BookingOccurrence(booking=booking, occurrence_date=d) for d in occurrence_dates]
        BookingOccurrence.objects.bulk_create(occurrences)

        return Response({
            "booking": BookingSerializer(booking).data,
            "occurrences": BookingOccurrenceSerializer(booking.occurrences.all(), many=True).data,
            "days_of_week": data['days_of_week'],
            "time_of_day": data['time_of_day'],
        }, status=201)


class OrganizationScheduleListView(APIView):
    """List all occurrences for an organization (optionally filter by booking)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, organization_id):
        org = _get_owned_org(request, organization_id)
        if not org:
            return Response({"error": "Organization not found or not owned by you."}, status=404)
        occurrences = BookingOccurrence.objects.filter(booking__organization=org)
        booking_id = request.query_params.get('booking_id')
        if booking_id:
            occurrences = occurrences.filter(booking_id=booking_id)
        return Response(BookingOccurrenceSerializer(occurrences, many=True).data)


class OrgOpportunitiesListView(APIView):
    """Roster drivers browse open (status='bidding') recurring jobs for any
    organization they're an active member of -- shows pickup/dropoff, the weekly
    schedule (via its occurrences), and how many driver slots are still open."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'driver':
            return Response({"error": "Only drivers have organization opportunities."}, status=403)
        org_ids = OrganizationDriver.objects.filter(
            driver=request.user, is_active=True
        ).values_list('organization_id', flat=True)
        bookings = Booking.objects.filter(organization_id__in=org_ids, status='bidding', is_recurring=True)

        results = []
        for b in bookings:
            accepted_count = OrganizationBid.objects.filter(booking=b, status='accepted').count()
            my_bid = OrganizationBid.objects.filter(booking=b, driver=request.user).first()
            results.append({
                "booking": BookingSerializer(b).data,
                "drivers_needed": b.drivers_needed,
                "drivers_still_needed": max(b.drivers_needed - accepted_count, 0),
                "my_bid": OrganizationBidSerializer(my_bid).data if my_bid else None,
                "occurrence_dates": [o.occurrence_date for o in b.occurrences.all()[:10]],
            })
        return Response(results)


class OrgBidListCreateView(APIView):
    """Roster drivers place ONE bid per scheduled job; the org owner sees every bid
    to compare. This is the org's own mini-bidding pool -- the general public never
    sees these jobs (that's the marketplace flow in bookings/ instead)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if booking.organization and booking.organization.owner_id == request.user.id:
            bids = OrganizationBid.objects.filter(booking=booking)
        else:
            bids = OrganizationBid.objects.filter(booking=booking, driver=request.user)
        return Response(OrganizationBidSerializer(bids, many=True).data)

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if request.user.role != 'driver':
            return Response({"error": "Only drivers can bid."}, status=403)
        if not booking.organization:
            return Response({"error": "This isn't an organization job."}, status=400)
        if booking.status != 'bidding':
            return Response({"error": "This schedule is no longer open for bidding."}, status=400)
        if not _is_active_roster_member(booking.organization, request.user):
            return Response({"error": "You must be on this organization's roster to bid."}, status=403)

        bid_amount = request.data.get('bid_amount')
        if not bid_amount:
            return Response({"error": "bid_amount is required."}, status=400)
        if OrganizationBid.objects.filter(booking=booking, driver=request.user).exists():
            return Response({"error": "You've already placed a bid on this schedule."}, status=400)

        bid = OrganizationBid.objects.create(
            booking=booking, driver=request.user,
            bid_amount=bid_amount, message=request.data.get('message', ''),
        )
        return Response(OrganizationBidSerializer(bid).data, status=201)


class AcceptOrgBidView(APIView):
    """Owner accepts a roster driver's bid. Once enough bids are accepted to cover
    drivers_needed, the schedule closes (status flips to 'accepted') and any
    remaining pending bids are auto-rejected. Accepting a bid does NOT itself put
    the driver on any calendar date -- that's done afterward, per occurrence, via
    OccurrenceAssignDriverView (which checks the driver won a bid here)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id, bid_id):
        booking = get_object_or_404(Booking, id=booking_id)
        if not booking.organization or booking.organization.owner_id != request.user.id:
            return Response({"error": "Only the organization's owner can accept bids."}, status=403)
        if booking.status != 'bidding':
            return Response({"error": "This schedule is not open for bidding anymore."}, status=400)

        bid = get_object_or_404(OrganizationBid, id=bid_id, booking=booking)
        accepted_count = OrganizationBid.objects.filter(booking=booking, status='accepted').count()
        if accepted_count >= booking.drivers_needed:
            return Response({"error": f"Already have all {booking.drivers_needed} driver(s) needed."}, status=400)

        bid.status = 'accepted'
        bid.save(update_fields=['status'])
        accepted_count += 1

        if accepted_count >= booking.drivers_needed:
            booking.status = 'accepted'  # fully staffed, bidding closes
            booking.save(update_fields=['status'])
            OrganizationBid.objects.filter(booking=booking, status='pending').update(status='rejected')

        return Response({
            "message": f"Accepted {bid.driver.username}'s bid",
            "accepted_count": accepted_count,
            "drivers_needed": booking.drivers_needed,
            "booking_status": booking.status,
        })


class OccurrenceAssignDriverView(APIView):
    """Assign (or reassign) a driver to a specific scheduled date. If the booking
    ever went through mini-bidding (has any OrganizationBid rows), the driver must
    have a WON bid for it -- prevents the owner from bypassing the bidding they just
    ran. Older/ad-hoc org bookings with no bidding history just need roster membership.
    Either way, the double-booking check always applies."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, occurrence_id):
        occurrence = get_object_or_404(BookingOccurrence, id=occurrence_id)
        booking = occurrence.booking
        org = booking.organization
        if not org or org.owner_id != request.user.id:
            return Response({"error": "Only the organization's owner can assign drivers."}, status=403)

        driver_id = request.data.get('driver_id')
        if not driver_id:
            return Response({"error": "driver_id is required."}, status=400)
        driver = get_object_or_404(User, id=driver_id, role='driver')

        if not _is_active_roster_member(org, driver):
            return Response({"error": "That driver is not an active member of this organization's roster."},
                             status=400)

        if OrganizationBid.objects.filter(booking=booking).exists():
            won = OrganizationBid.objects.filter(booking=booking, driver=driver, status='accepted').exists()
            if not won:
                return Response({"error": "This driver's bid wasn't accepted for this schedule."}, status=400)

        start, end = get_job_window(occurrence.occurrence_date, booking.estimated_duration_minutes)
        conflicts = get_driver_conflicts(driver, start, end, exclude_occurrence_id=occurrence.id)
        if conflicts:
            return Response({
                "error": "This driver is already booked during that time window.",
                "conflicts": conflicts,
            }, status=409)

        occurrence.assigned_driver = driver
        occurrence.status = 'assigned'
        occurrence.save(update_fields=['assigned_driver', 'status'])
        return Response(BookingOccurrenceSerializer(occurrence).data)
