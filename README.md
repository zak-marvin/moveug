# MoveUG — Django Backend

Logistics/goods-transport backend: open marketplace bidding for one-off jobs, plus
organizations that run their own driver fleet on scheduled/recurring jobs. A driver
can never be double-booked across either flow.

## What changed in this rebuild

The previous version (built with Meta AI) had several things out of sync between
files — see the audit notes below the setup instructions if you want the detail.
Short version: there was no real authentication (every request was hardcoded as
user #1), Google Maps distance calculation existed but was never actually called,
`core/pricing.py` imported functions that didn't exist, the `payments` app had no
urls and wasn't wired into the project at all, and nothing stopped a driver being
assigned to two overlapping jobs. All of that is fixed here.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env            # then fill in your real keys
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open **http://127.0.0.1:8000/console/** — a plain HTML/JS page that exercises every
endpoint (register, login, create booking, bid, accept, create an org, roster a
driver, schedule recurring rides, and a dedicated button to prove the double-booking
guard rejects an overlapping assignment). No Flutter or CORS setup needed for this
since it's served same-origin by Django itself.

Django admin is at **/admin/** with your superuser.

## ⚠️ Before you do anything else

Your old `.env` had a live-looking Google Maps API key and MTN MoMo sandbox keys in
it, and four leftover debug scripts (`create_api_key.py`, `test_momo_pay.py`, etc. —
now deleted from this rebuild) had MoMo keys **hardcoded directly in the Python
source**. Since this project was previously shared with Meta AI, treat all of those
as exposed:

- Rotate the Google Maps key in Google Cloud Console and restrict it to your
  server/API scope.
- Regenerate MoMo sandbox keys via the MTN MoMo developer portal (lower risk since
  it's sandbox, but still worth doing before you go anywhere near production).

## Architecture

```
config/          settings, root urls
core/            distance (Google -> OSRM -> haversine fallback) + pricing/duration
                 estimation. Every other app must go through this — nothing else
                 should reimplement distance or pricing math.
users/           custom User (role: customer/driver), DriverProfile, auth endpoints
organizations/   Organization + driver roster (an org's own fleet)
bookings/        Booking, BookingOccurrence, bidding, chat, status updates,
                 the double-booking conflict checker (utils.py)
payments/        MTN MoMo collections/disbursements (MOMO_SIMULATE=True fakes it)
testconsole/     the /console/ test page
```

### Two ways a job gets a driver

1. **Open marketplace** (`Booking`, no organization) — customer posts a job, drivers
   bid, customer accepts a bid.
2. **Organization mini-bidding** (`Booking.is_recurring=True` + `BookingOccurrence`
   per date) — an org owner describes a weekly schedule (which days, what time,
   how many weeks, how many drivers needed) and pickup/dropoff. This opens bidding
   to *only that org's roster* — the general public never sees it. Roster drivers
   each place one bid; the owner accepts bids up to `drivers_needed`, at which point
   bidding auto-closes. The owner then assigns each winning driver to specific
   calendar dates (can be a different driver per day) — this is a separate step
   from winning the bid, since "how many drivers are needed" and "which driver
   covers which specific day" are different decisions.

Both paths funnel through the same `bookings/utils.py::get_driver_conflicts()` before
a driver is actually assigned to a date, so a driver committed to an org run on
Tuesday morning can't also be accepted for an overlapping marketplace job that
morning, and vice versa. The occupied window is `move_date` (or `occurrence_date`)
→ `+ estimated_duration_minutes`, where duration comes from Google/OSRM's own
travel-time estimate when available, or distance ÷ average speed for the vehicle
type plus a loading/unloading buffer otherwise.

## API reference

All endpoints except register/login require `Authorization: Token <token>`.

**Auth** (`/api/auth/`)
- `POST register/` — `{username, phone_number, password, role: customer|driver, [license_number, vehicle_type, vehicle_number if driver]}`
- `POST login/` — `{identifier, password}` (identifier = username or phone_number)
- `GET me/`
- `POST drivers/online/` — toggle own online status (driver only)
- `POST drivers/location/` — `{lat, lng}` (driver only)

**Bookings** (`/api/bookings/`)
- `POST create/` — open-marketplace booking; computes distance/price/duration server-side
- `GET jobs/` — open jobs (status=bidding, no organization)
- `POST <id>/bid/` — `{bid_amount, message}` (driver only)
- `GET <id>/bids/`
- `POST <id>/accept/<bid_id>/` — customer only; **409 if the driver has a time conflict**
- `GET/POST <id>/chat/`
- `POST <id>/status/` — `{status}`

**Organizations** (`/api/organizations/`)
- `GET/POST ` — list/create your organizations
- `GET/POST <org_id>/drivers/` — roster; add by `{phone_number}` or `{driver_id}`
- `POST <org_id>/schedule/` — `{pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, vehicle_type, days_of_week: ["mon","wed","fri"], time_of_day: "07:00", start_date: "2026-08-10", weeks: 4, drivers_needed: 2}` → creates one `Booking` (status='bidding') + one `BookingOccurrence` per matching date, opens to roster mini-bidding
- `GET <org_id>/occurrences/` — list generated dates for an org (optionally `?booking_id=`)
- `GET /opportunities/` — roster driver's view: open schedules across every org they belong to, with slots still needed and their own bid if any (driver only)
- `GET/POST schedule/<booking_id>/bids/` — GET: owner sees all bids, driver sees only their own. POST: roster driver places one bid `{bid_amount, message}`
- `POST schedule/<booking_id>/bids/<bid_id>/accept/` — owner only; accepting enough bids to reach `drivers_needed` auto-closes bidding and rejects the rest
- `POST occurrences/<id>/assign/` — `{driver_id}`; owner only; requires the driver to have a **won** bid on that schedule (if it went through bidding) and to be on the roster; **409 if a time conflict with any other job**

**Payments** (`/api/payments/`)
- `POST <booking_id>/initiate/` — `{phone}`, customer only
- `GET <booking_id>/status/` — polls MoMo, auto-triggers driver payout on success

## Known limitations / next decisions

- Google/OSRM aren't reachable from some restricted sandboxes (including the one I
  built this in) — it silently falls back to a haversine estimate in that case, which
  is why you may see `distance_source: "haversine_estimate"` in dev. On a normal
  machine/server with outbound internet it'll actually hit Google.
- Once bids are accepted for a schedule, the owner still manually assigns which
  winning driver covers which specific date. That's intentional (filling slots vs.
  scheduling calendar days are different decisions), but if you'd rather it
  auto-distribute winners across dates evenly, that's a small addition on top of
  `OccurrenceAssignDriverView`.
- No refund/cancellation-fee logic yet for `status='cancelled'`.
- `ALLOWED_HOSTS = ['*']` and `CORS_ALLOW_ALL_ORIGINS = True` are dev-only — lock both
  down before this is public.
