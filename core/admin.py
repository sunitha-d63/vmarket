from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Category, Product, DeliveryZone,
    Order, ContactMessage
)
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'phone', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'username')}),
        ('Role & Permissions', {
            'fields': ('role', 'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'phone', 'role',
                'password1', 'password2',
                'is_staff', 'is_active'
            ),
        }),
    )

    search_fields = ('email', 'phone', 'username')
    ordering = ('email',)


class ProductInline(admin.TabularInline):
    model = Product
    extra = 1
    fields = ('title', 'base_price', 'image', 'weight_options')
    readonly_fields = ('id',)
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_count')
    search_fields = ('name',)
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    class Media:
        js = ('admin_weight_autofill.js',)
        
    list_display = (
        'title', 'category', 'base_price', 'unit', 'get_final_price',
        'is_offer', 'discount_percent', 'offer_active_status',
        'offer_start', 'offer_end'
    )

    list_filter = ('category', 'unit', 'is_offer')
    search_fields = ('title', 'category__name')
    readonly_fields = ('id',)
    filter_horizontal = ('wishlist_users',)
    ordering = ('title',)

    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'category', 'vendor', 'description', 'image', 'unit', 'weight_options')
        }),
        ('Pricing', {
            'fields': ('base_price',)
        }),
        ('Offer Details', {
            'classes': ('collapse',),
            'fields': ('is_offer', 'discount_percent', 'offer_start', 'offer_end')
        }),
        ('Wishlist', {
            'fields': ('wishlist_users',)
        }),
    )

    @admin.display(description="Final Price")
    def get_final_price(self, obj):
        if obj.is_offer and obj.discount_percent > 0:
            return f"₹{obj.discounted_price:.2f}"
        return f"₹{obj.base_price:.2f}"

    @admin.display(description="Offer Status", ordering="offer_end")
    def offer_active_status(self, obj):
        now = timezone.now()
        if not obj.is_offer:
            return format_html('<span style="color:gray;">—</span>')

        if obj.offer_start and obj.offer_end:
            if obj.offer_start <= now <= obj.offer_end:
                return format_html('<span style="color:green;">🟢 Active</span>')
            elif now < obj.offer_start:
                return format_html('<span style="color:orange;">🕒 Upcoming</span>')
            else:
                return format_html('<span style="color:red;">🔴 Expired</span>')
        elif obj.is_offer:
            return format_html('<span style="color:green;">🟢 Always Active</span>')
        return format_html('<span style="color:gray;">—</span>')

    def save_model(self, request, obj, form, change):
        if obj.is_offer:
            if not obj.offer_start:
                obj.offer_start = timezone.now()
            if not obj.offer_end:
                obj.offer_end = timezone.now() + timedelta(days=7)
        super().save_model(request, obj, form, change)

@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("area_name", "pincode", "city", "delivery_delay_hours", "is_active", "map_preview")
    list_filter = ("is_active", "city")
    search_fields = ("area_name", "pincode", "city")
    readonly_fields = ("map_preview",)

    fieldsets = (
        (None, {
            "fields": ("area_name", "pincode", "city", "latitude", "longitude", "delivery_delay_hours", "is_active")
        }),
        ("Map Preview", {"fields": ("map_preview",)}),
    )

    def map_preview(self, obj):
        """Show live Google Map preview."""
        if obj.latitude and obj.longitude:
            return format_html(
                f'<iframe width="100%" height="300" '
                f'src="https://www.google.com/maps?q={obj.latitude},{obj.longitude}&hl=en&z=15&output=embed"></iframe>'
            )
        return "No location set"

    map_preview.short_description = "Google Map Preview"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('user__username', 'full_name', 'email')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'subject', 'created_at')
    search_fields = ('name', 'email', 'phone', 'subject')
    list_filter = ('created_at',)
