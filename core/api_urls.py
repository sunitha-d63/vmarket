from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import  DeliveryZoneViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'zones', DeliveryZoneViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
