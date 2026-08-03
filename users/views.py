from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DriverProfile
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, DriverProfileSerializer


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": UserSerializer(user).data,
        })


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class DriverToggleOnlineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'driver':
            return Response({"error": "Only drivers can toggle online status."}, status=403)
        profile = getattr(request.user, 'driver_profile', None)
        if not profile:
            return Response({"error": "No driver profile found for this account."}, status=400)
        profile.is_online = not profile.is_online
        profile.save(update_fields=['is_online'])
        return Response({"is_online": profile.is_online})


class DriverLocationUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'driver':
            return Response({"error": "Only drivers can update location."}, status=403)
        profile = getattr(request.user, 'driver_profile', None)
        if not profile:
            return Response({"error": "No driver profile found for this account."}, status=400)
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        if lat is None or lng is None:
            return Response({"error": "lat and lng are required."}, status=400)
        profile.current_lat = lat
        profile.current_lng = lng
        profile.save(update_fields=['current_lat', 'current_lng'])
        return Response(DriverProfileSerializer(profile).data)
