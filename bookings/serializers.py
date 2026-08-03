from rest_framework import serializers
from .models import Booking, BookingItem, DriverBid, ChatMessage, BookingOccurrence


class BookingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingItem
        fields = ['id', 'item_type', 'quantity']


class BookingSerializer(serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, required=False)
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    selected_driver_username = serializers.CharField(source='selected_driver.username', read_only=True, default=None)

    class Meta:
        model = Booking
        fields = [
            'id', 'customer', 'customer_username', 'selected_driver', 'selected_driver_username',
            'organization', 'is_recurring', 'drivers_needed',
            'move_type', 'vehicle_type', 'passenger_count',
            'pickup_address', 'pickup_lat', 'pickup_lng',
            'dropoff_address', 'dropoff_lat', 'dropoff_lng',
            'distance_km', 'distance_source', 'estimated_duration_minutes',
            'system_price', 'final_price', 'move_date', 'status', 'items', 'created_at',
        ]
        read_only_fields = ['customer', 'selected_driver', 'distance_km', 'distance_source',
                             'estimated_duration_minutes', 'system_price', 'final_price', 'status']


class DriverBidSerializer(serializers.ModelSerializer):
    driver_username = serializers.CharField(source='driver.username', read_only=True)

    class Meta:
        model = DriverBid
        fields = ['id', 'booking', 'driver', 'driver_username', 'bid_amount', 'message', 'created_at']
        read_only_fields = ['driver', 'booking']


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'booking', 'sender', 'sender_username', 'message', 'timestamp']
        read_only_fields = ['sender', 'booking']


class BookingOccurrenceSerializer(serializers.ModelSerializer):
    assigned_driver_username = serializers.CharField(source='assigned_driver.username', read_only=True, default=None)

    class Meta:
        model = BookingOccurrence
        fields = ['id', 'booking', 'occurrence_date', 'assigned_driver', 'assigned_driver_username',
                   'status', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
