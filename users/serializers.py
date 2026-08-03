from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = ['license_number', 'vehicle_type', 'vehicle_number', 'is_online',
                  'current_lat', 'current_lng', 'rating']
        read_only_fields = ['is_online', 'rating']


class UserSerializer(serializers.ModelSerializer):
    driver_profile = DriverProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'role', 'first_name', 'last_name', 'driver_profile']
        read_only_fields = ['id', 'role']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='customer')

    # Only required/used when role == 'driver'
    license_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_type = serializers.ChoiceField(choices=DriverProfile.VEHICLE_CHOICES, write_only=True, required=False)
    vehicle_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password', 'role', 'first_name', 'last_name',
                  'license_number', 'vehicle_type', 'vehicle_number']

    def validate(self, attrs):
        if attrs.get('role') == 'driver':
            missing = [f for f in ('license_number', 'vehicle_type', 'vehicle_number') if not attrs.get(f)]
            if missing:
                raise serializers.ValidationError(
                    {f: "Required when registering as a driver." for f in missing}
                )
        return attrs

    def create(self, validated_data):
        license_number = validated_data.pop('license_number', None)
        vehicle_type = validated_data.pop('vehicle_type', None)
        vehicle_number = validated_data.pop('vehicle_number', None)
        password = validated_data.pop('password')

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        if user.role == 'driver':
            DriverProfile.objects.create(
                user=user,
                license_number=license_number,
                vehicle_type=vehicle_type,
                vehicle_number=vehicle_number,
            )
        return user


class LoginSerializer(serializers.Serializer):
    # Accept either username or phone_number in the same field for convenience,
    # since Flutter's login screen may not distinguish them.
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs['identifier']
        password = attrs['password']

        username = identifier
        if identifier not in ('',) and not User.objects.filter(username=identifier).exists():
            user_by_phone = User.objects.filter(phone_number=identifier).first()
            if user_by_phone:
                username = user_by_phone.username

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")

        attrs['user'] = user
        return attrs
