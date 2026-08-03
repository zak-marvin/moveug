from rest_framework import serializers
from users.serializers import UserSerializer
from .models import Organization, OrganizationDriver, OrganizationBid


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'phone_number', 'address', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']


class OrganizationDriverSerializer(serializers.ModelSerializer):
    driver_detail = UserSerializer(source='driver', read_only=True)

    class Meta:
        model = OrganizationDriver
        fields = ['id', 'driver', 'driver_detail', 'is_active', 'joined_at']
        read_only_fields = ['id', 'joined_at']
        extra_kwargs = {'driver': {'write_only': True}}


class OrganizationBidSerializer(serializers.ModelSerializer):
    driver_username = serializers.CharField(source='driver.username', read_only=True)

    class Meta:
        model = OrganizationBid
        fields = ['id', 'booking', 'driver', 'driver_username', 'bid_amount', 'message', 'status', 'created_at']
        read_only_fields = ['id', 'driver', 'booking', 'status', 'created_at']
