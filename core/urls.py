from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryZoneViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'deliveryzones', DeliveryZoneViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.home, name='home'),                       
    path('login/', views.login_view, name='login'),     
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),   
    path("features/", views.features_page, name="features_page"),
    path('payment-info/', views.payment_info, name='payment_info'),
    path('quality-info/', views.quality_info, name='quality_info'),
    path('cart/', views.cart_view, name='cart'),
    path('our-products/', views.our_products, name='our_products'),
    path('track-order/', views.track_order, name='track_order'),
    path("track-location/<int:order_id>/", views.track_location, name="track_location"),
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('contact/', views.contact_page, name='contact_page'),
    path('vendor/edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('vendor/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('search/', views.search_products, name='search_products'),
    path('category/<int:category_id>/', views.category_products, name='category_products'),
    path('category/<int:category_id>/product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('wishlist/', views.wishlist_view, name='wishlist_page'),
    path('toggle-wishlist/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path("cart/remove-guest/<int:index>/", views.remove_from_cart_guest, name="remove_from_cart_guest"),
    path("add-to-cart/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path('payment/', views.payment_page, name='payment_page'),
    path("payment/verify/", views.verify_payment, name="verify_payment"),
    path("order/<int:order_id>/edit/", views.edit_order, name="edit_order"),
    path("order/<int:order_id>/cancel/", views.cancel_order, name="cancel_order"),
    path("order/<int:order_id>/start-dispatch/", views.start_dispatch, name="start_dispatch"),
    path('check-delivery-feasibility/', views.check_delivery_feasibility, name='check_delivery_feasibility'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path("my-orders/", views.my_orders, name="my_orders"),
    path('cart/update/', views.update_cart_item, name='update_cart_item'),
    path('offers/', views.offers_page, name='offers_page'),
    path('check-delivery/', views.check_delivery_zone, name='check_delivery'),
    path('get-slots/', views.get_available_slots, name='get_slots'),
    path('set-delivery-location/', views.set_delivery_location, name='set_delivery_location'),
    path('get-delivery-zones/', views.get_delivery_zones, name='get_delivery_zones'),
    path('check-delivery/', views.check_delivery, name='check_delivery'),
    path('home-check-delivery/', views.home_check_delivery, name='home_check_delivery'),
    path('home-get-zones/', views.home_get_zones, name='home_get_zones'),
    path('home-set-location/', views.home_set_location, name='home_set_location'),
    path('home-clear-location/', views.clear_delivery_location, name='home_clear_location'),
    path('offers/', views.top_offers, name='top_offers'),
    path("api/get-delivery-estimate/", views.get_delivery_estimate, name="get_delivery_estimate"),
    path('get-nearest-zone/', views.get_nearest_zone, name='get_nearest_zone'),
    path(
        'ajax/check-delivery-slot/',
        views.check_delivery_with_slot,
        name='check_delivery_with_slot'
    ),
    path('ajax/check-email/', views.check_email_exists, name='check_email'),
    path('ajax/username-suggestions/', views.username_suggestions, name='username_suggestions'),
    path('ajax/check-phone/', views.check_phone_exists, name='check_phone'),
    path("reverse-geocode/", views.reverse_geocode, name="reverse_geocode"),
    path('delivery-info/', views.delivery_info, name='delivery_info'),
    path('fresh-organic/', views.fresh_organic, name='fresh_organic'),
    path('support/', views.support, name='support'),
    path('payment-info/', views.payment_info, name='payment_info'),
    path('quality-info/', views.quality_info, name='quality_info'),
    path("forgot-password/",views.forgot_password, name="forgot_password"),
    path("verify-otp/",views.verify_otp, name="verify_otp"),
    path("reset-password/",views.reset_password, name="reset_password"),
    path("update-cart-qty/<int:item_id>/<int:qty>/", views.update_cart_qty, name="update_cart_qty"),
    path("update-guest-cart/", views.update_guest_cart_qty, name="update_guest_cart"),


]

