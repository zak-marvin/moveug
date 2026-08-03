from django.urls import path
from .views import (OrganizationListCreateView, OrganizationDriverRosterView,
                     OrganizationScheduleCreateView, OccurrenceAssignDriverView,
                     OrganizationScheduleListView, OrgOpportunitiesListView,
                     OrgBidListCreateView, AcceptOrgBidView)

urlpatterns = [
    path('', OrganizationListCreateView.as_view(), name='org-list-create'),
    path('opportunities/', OrgOpportunitiesListView.as_view(), name='org-opportunities'),
    path('<int:organization_id>/drivers/', OrganizationDriverRosterView.as_view(), name='org-roster'),
    path('<int:organization_id>/schedule/', OrganizationScheduleCreateView.as_view(), name='org-schedule-create'),
    path('<int:organization_id>/occurrences/', OrganizationScheduleListView.as_view(), name='org-occurrence-list'),
    path('schedule/<int:booking_id>/bids/', OrgBidListCreateView.as_view(), name='org-bid-list-create'),
    path('schedule/<int:booking_id>/bids/<int:bid_id>/accept/', AcceptOrgBidView.as_view(), name='org-bid-accept'),
    path('occurrences/<int:occurrence_id>/assign/', OccurrenceAssignDriverView.as_view(), name='occurrence-assign'),
]
