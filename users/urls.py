from django.urls import path
from .views import RegisterView, LoginView, MeView, DriverToggleOnlineView, DriverLocationUpdateView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('drivers/online/', DriverToggleOnlineView.as_view(), name='driver-toggle-online'),
    path('drivers/location/', DriverLocationUpdateView.as_view(), name='driver-location'),
]
