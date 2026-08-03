from django.contrib import admin
from django.urls import include, path

from testconsole.views import ConsoleView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('console/', ConsoleView.as_view(), name='console'),

    path('api/auth/', include('users.urls')),
    path('api/organizations/', include('organizations.urls')),
    path('api/bookings/', include('bookings.urls')),
    path('api/payments/', include('payments.urls')),
]
