from rest_framework import serializers
from .models import DeliveryZone, Order, OrderItem
class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = '__all__'
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.title', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price']
class OrderSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_zone_name = serializers.CharField(source='delivery_zone.area_name', read_only=True)
    status_message = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_name', 'full_name', 'email', 'phone',
            'street_address', 'city', 'delivery_zone', 'delivery_zone_name',
            'delivery_slot', 'payment_method', 'subtotal', 'tax', 'total_amount',
            'expected_delivery_time', 'status', 'status_message', 'created_at', 'items'
        ]
    def get_status_message(self, obj):
        if obj.status == "failed":
            return "⚠️ Delivery failed. Order not delivered on time."
        elif obj.status == "delayed":
            return "⏳ Delivery is delayed but will arrive soon."
        elif obj.status == "out_for_delivery":
            return "🚚 Out for delivery."
        elif obj.status == "processing":
            return "🛒 Order is being processed."
        elif obj.status == "confirmed":
            return "✅ Order confirmed."
        elif obj.status == "delivered":
            return "🎉 Order successfully delivered!"
        else:
            return "Order pending or awaiting confirmation."
