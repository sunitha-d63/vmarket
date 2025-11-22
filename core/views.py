from datetime import datetime, timedelta
from decimal import Decimal
import json
import math
from math import radians, sin, cos, sqrt, atan2
import razorpay

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.db.models import Q, Sum, Count, F
from django.db.models.functions import TruncDate

from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .forms import (
    CustomUserCreationForm, UserLoginForm, OrderForm,
    VendorProductForm, ContactForm, EditOrderForm,
    ForgotPasswordForm, OTPVerifyForm, ResetPasswordForm,
    CancelOrderForm
)

from .models import (
    Category, Product, CartItem, Order, DeliveryZone,
    OrderItem, PasswordResetOTP, get_delivery_delay
)

from .serializers import DeliveryZoneSerializer, OrderSerializer

from .utils import (
    calculate_distance_km, send_order_email
)

from core.models import CustomUser, Product, Category, Order, OrderItem


def home(request):
    categories = Category.objects.all()

    selected_zone_id = request.session.get('selected_zone')
    selected_zone = None

    if selected_zone_id:
        selected_zone = DeliveryZone.objects.filter(id=selected_zone_id).first()

    context = {
        'categories': categories,
        'selected_zone': selected_zone,
    }
    return render(request, 'core/home.html', context)

from django.contrib.auth import login as auth_login
from django.utils.http import url_has_allowed_host_and_scheme

ALLOWED_HOSTS = getattr(settings, "ALLOWED_HOSTS", [])

def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = category.products.all()
    now = timezone.now()

    show_offers = request.GET.get('offers') == 'true'
    if show_offers:
        products = products.filter(
            is_offer=True,
            offer_start__lte=now,
            offer_end__gte=now
        )

    sort = request.GET.get('sort')
    if sort == 'price_low':
        products = products.order_by('base_price')
    elif sort == 'price_high':
        products = products.order_by('-base_price')
    elif sort == 'name_asc':
        products = products.order_by('title')
    elif sort == 'name_desc':
        products = products.order_by('-title')


    if request.user.is_authenticated:
        user_wishlist_ids = set(request.user.wishlist.values_list('id', flat=True))
        for product in products:
            product.in_wishlist = product.id in user_wishlist_ids
        guest_wishlist_ids = []
    else:
        guest_wishlist_ids = request.session.get("wishlist", [])
        for product in products:
            product.in_wishlist = product.id in guest_wishlist_ids

    return render(request, 'core/category_products.html', {
        'category': category,
        'products': products,
        'sort': sort,
        'show_offers': show_offers,
        'guest_wishlist_ids': guest_wishlist_ids,  # ⭐ IMPORTANT
    })


def top_offers(request):
    offer_categories = Category.objects.filter(is_offer_category=True)
    return render(request, 'core/top_offers.html', {'offer_categories': offer_categories})


def product_detail(request, category_id, product_id):
    product = get_object_or_404(Product, id=product_id, category_id=category_id)
    weight_options = product.get_weight_options_list()

    selected_weight = weight_options[0] if weight_options else None

    if request.method == "POST":
        selected_weight = request.POST.get("weight")
        quantity = int(request.POST.get("quantity", 1))

        weight_multiplier = product.convert_weight_value(selected_weight)

        unit_price = (
            product.discounted_price
            if product.is_offer_active
            else product.base_price
        )

        final_price = float(unit_price) * float(weight_multiplier)
        
        if not request.user.is_authenticated:

            cart = request.session.get("cart", [])

            cart.append({
                    "product_id": product.id,
                    "weight": selected_weight.upper(),
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                    "weight_multiplier": str(weight_multiplier),
                    "image": product.image.url if product.image else "",
                    })


            request.session["cart"] = cart
            request.session.modified = True

            if "buy_now" in request.POST:
                return redirect("login")

            return redirect("cart")
        unit_price = (
            product.discounted_price
            if product.is_offer_active
            else product.base_price
        )
        final_price = float(unit_price) * weight_multiplier

        cart_item = CartItem.objects.filter(
            user=request.user,
            product=product,
            weight=selected_weight
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save()
        else:
            CartItem.objects.create(
                user=request.user,
                product=product,
                weight=selected_weight,
                quantity=quantity
            )

        if "buy_now" in request.POST:
            return redirect("payment_page")

        return redirect("cart")

    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]

    in_wishlist = (
        product.wishlist_users.filter(id=request.user.id).exists()
        if request.user.is_authenticated else False
    )

    return render(request, "core/product_detail.html", {
        "product": product,
        "selected_weight": selected_weight,
        "weight_options": weight_options,
        "related_products": related_products,
        "in_wishlist": in_wishlist,
    })


def cart_view(request):

    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user)
        subtotal = Decimal("0.00")
        for item in cart_items:
            weight_multiplier = Decimal(str(item.product.convert_weight_value(item.weight)))

            item.converted_weight_display = weight_multiplier
            unit_price = item.product.discounted_price if item.product.is_offer_active else item.product.base_price
            item.final_price = (unit_price * weight_multiplier * Decimal(item.quantity))
            subtotal += item.final_price

        tax = subtotal * Decimal("0.05")
        total = subtotal + tax
        return render(request, "core/cart.html", {
            "cart_items": cart_items,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "is_guest": False,
        })

    cart = request.session.get("cart", [])
    subtotal = Decimal("0.00")
    for item in cart:
        product = Product.objects.get(id=item["product_id"])
        weight_multiplier = Decimal(str(product.convert_weight_value(item["weight"])))
        item["converted_weight"] = weight_multiplier
        unit_price = Decimal(str(item["unit_price"]))
        quantity = Decimal(str(item["quantity"]))
        item["final_price"] = unit_price * weight_multiplier * quantity
        subtotal += item["final_price"]

    tax = subtotal * Decimal("0.05")
    total = subtotal + tax
    return render(request, "core/cart.html", {
        "cart_items": cart,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "is_guest": True,
    })

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    weight = (request.POST.get("weight") or request.GET.get("weight") or "").strip()
    if not weight:
        try:
            weight_options = product.weight_options 
            if weight_options:
                weight = weight_options[0] if isinstance(weight_options, (list, tuple)) else weight_options.split(",")[0]
            else:
                weight = "1"
        except Exception:
            weight = "1"

    weight = weight.strip().upper()
    quantity = int(request.POST.get("quantity", 1))

    if "buy_now" in request.POST:
        if not request.user.is_authenticated:
            return redirect("login")
        request.session["buy_now_item"] = {
            "product_id": product.id,
            "weight": weight,
            "quantity": quantity,
        }
        return redirect("payment_page")
    weight_multiplier = Decimal(str(product.convert_weight_value(weight)))
    unit_price = product.discounted_price if product.is_offer_active else product.base_price
    final_price = unit_price * weight_multiplier * Decimal(quantity)

    if request.user.is_authenticated:
        item, created = CartItem.objects.get_or_create(user=request.user, product=product, weight=weight)
        if created:
            item.quantity = quantity
        else:
            item.quantity += quantity
        item.save()
        return redirect("cart")

    cart = request.session.get("cart", [])
    for entry in cart:
        if entry["product_id"] == product.id and entry["weight"] == weight:
            entry["quantity"] += quantity
            request.session["cart"] = cart
            request.session.modified = True
            return redirect("cart")

    cart.append({
    "product_id": product.id,
    "weight": weight.upper(),
    "quantity": quantity,
    "unit_price": str(unit_price),
    "weight_multiplier": str(weight_multiplier),
    "image": product.image.url,
})

    request.session["cart"] = cart
    request.session.modified = True
    return redirect("cart")

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect("cart")

def remove_from_cart_guest(request, index):
    cart = request.session.get("cart", [])
    if 0 <= index < len(cart):
        cart.pop(index)
        request.session["cart"] = cart
    return redirect("cart")

@login_required
@require_POST
def update_cart_item(request):
    item_id = request.POST.get('item_id')
    quantity = int(request.POST.get('quantity', 1))

    try:
        cart_item = CartItem.objects.get(id=item_id, user=request.user)
        cart_item.quantity = quantity
        cart_item.save()
        total_price = cart_item.quantity * cart_item.product.base_price
        return JsonResponse({'success': True, 'total_price': f'{total_price:.2f}'})
    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item not found'})

from django.shortcuts import render, redirect, get_object_or_404
from core.models import Product

def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)


    if request.user.is_authenticated:
        if request.user in product.wishlist_users.all():
            product.wishlist_users.remove(request.user)
        else:
            product.wishlist_users.add(request.user)

        return redirect(request.META.get("HTTP_REFERER", "wishlist_page"))
    
    wishlist = request.session.get("wishlist", [])

    if product.id in wishlist:
        wishlist.remove(product.id)
    else:
        wishlist.append(product.id)

    request.session["wishlist"] = wishlist
    request.session.modified = True

    return redirect(request.META.get("HTTP_REFERER", "wishlist_page"))

def wishlist_view(request):

    guest_wishlist_ids = request.session.get("wishlist", [])

    if request.user.is_authenticated:
        wishlist_items = request.user.wishlist.all()
        return render(
            request,
            "core/wishlist.html",
            {
                "wishlist_items": wishlist_items,
                "is_guest": False,
                "guest_wishlist_ids": guest_wishlist_ids,
            }
        )

    wishlist = request.session.get("wishlist", [])
    products = []

    for pid in wishlist:
        try:
            products.append(Product.objects.get(id=pid))
        except Product.DoesNotExist:
            pass

    return render(
        request,
        "core/wishlist.html",
        {
            "wishlist_items": products,
            "is_guest": True,
            "guest_wishlist_ids": guest_wishlist_ids,
        }
    )

def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        product.wishlist_users.add(request.user)
        return redirect("wishlist_page")

    wishlist = request.session.get("wishlist", [])

    if product.id not in wishlist:
        wishlist.append(product.id)

    request.session["wishlist"] = wishlist
    request.session.modified = True

    return redirect("wishlist_page")

def remove_from_wishlist(request, product_id):

    if request.user.is_authenticated:
        product = get_object_or_404(Product, id=product_id)
        product.wishlist_users.remove(request.user)
        return redirect("wishlist_page")

    wishlist = request.session.get("wishlist", [])
    if product_id in wishlist:
        wishlist.remove(product_id)

    request.session["wishlist"] = wishlist
    request.session.modified = True

    return redirect("wishlist_page")


def search_products(request):
    query = request.GET.get('q', '').strip()
    products = []

    if query:
        products = Product.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        ).distinct()


        if request.user.is_authenticated:

            user_wishlist_ids = set(
                request.user.wishlist.values_list('id', flat=True)
            )

            for product in products:
                product.in_wishlist = product.id in user_wishlist_ids

            guest_wishlist_ids = []  

        else:
            guest_wishlist_ids = request.session.get("wishlist", [])

            for product in products:
                product.in_wishlist = product.id in guest_wishlist_ids

    return render(request, 'core/search.html', {
        'query': query,
        'products': products,
        'guest_wishlist_ids': guest_wishlist_ids if not request.user.is_authenticated else []
    })


def our_products(request):
    products = Product.objects.all()
    categories = Category.objects.all()

    keyword = request.GET.get('q', '').strip()
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    weight_filter = request.GET.get('weight', '').strip()
    category_param = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', '').strip()

    selected_category = None

    if category_param and category_param.lower() != "none":
        selected_category = Category.objects.filter(name__iexact=category_param).first()
        if selected_category:
            products = products.filter(category=selected_category)

    if keyword:
        products = products.filter(
            Q(title__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(category__name__icontains=keyword)
        )

    if min_price:
        products = products.filter(base_price__gte=min_price)
    if max_price:
        products = products.filter(base_price__lte=max_price)

    if weight_filter:
        products = products.filter(weight_options__icontains=weight_filter)

    if sort == "price_asc":
        products = products.order_by("base_price")
    elif sort == "price_desc":
        products = products.order_by("-base_price")
    elif sort == "name_asc":
        products = products.order_by("title")
    elif sort == "name_desc":
        products = products.order_by("-title")


    if request.user.is_authenticated:
        user_wishlist_ids = request.user.wishlist.values_list("id", flat=True)
        guest_wishlist_ids = []  

        for p in products:
            p.in_wishlist = p.id in user_wishlist_ids

    else:

        guest_wishlist_ids = request.session.get("wishlist", [])

        for p in products:
            p.in_wishlist = p.id in guest_wishlist_ids


    return render(request, 'core/our_products.html', {
        'products': products,
        'categories': categories,

        'keyword': keyword,
        'min_price': min_price or '',
        'max_price': max_price or '',
        'weight_filter': weight_filter,
        'selected_category': selected_category.name if selected_category else None,
        'sort': sort,

        'guest_wishlist_ids': guest_wishlist_ids,  
    })

def is_admin(user):
    return user.is_authenticated and getattr(user, "role", None) == "admin"

def is_admin(user):
    return user.is_authenticated and getattr(user, "role", None) == "admin"

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_users = CustomUser.objects.filter(role="customer").count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_sales = Order.objects.aggregate(total=Sum("total_amount"))["total"] or 0

    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:10]

    top_products = (
        Product.objects.annotate(order_count=Count("order_items"))
        .order_by("-order_count")[:5]
    )

    # ⭐ REPLACED LOW-STOCK WITH BEST-SELLING ITEMS
    top_selling_items = (
        Product.objects
        .annotate(sales=Sum("order_items__quantity"))
        .filter(sales__gt=0)
        .order_by("-sales")[:10]
    )

    delivery_status_counts = {
        "pending": Order.objects.filter(status="pending").count(),
        "confirmed": Order.objects.filter(status="confirmed").count(),
        "processing": Order.objects.filter(status="processing").count(),
        "out_for_delivery": Order.objects.filter(status="out_for_delivery").count(),
        "delivered": Order.objects.filter(status="delivered").count(),
        "delayed": Order.objects.filter(status="delayed").count(),
        "failed": Order.objects.filter(status="failed").count(),
        "cancelled": Order.objects.filter(status="cancelled").count(),
    }

    category_data = Category.objects.annotate(
        total_sales=Sum("products__order_items__price")
    )

    category_labels = [c.name for c in category_data]
    category_values = [float(c.total_sales or 0) for c in category_data]

    daily_qs = (
        Order.objects
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total_amount"))
        .order_by("day")
    )

    daily_labels = [d["day"].strftime("%b %d") for d in daily_qs]
    daily_values = [float(d["total"] or 0) for d in daily_qs]

    top_items = (
        OrderItem.objects
        .values("product__title")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )

    top_labels = [p["product__title"] for p in top_items]
    top_values = [p["total_qty"] for p in top_items]

    context = {
        "total_users": total_users,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_sales": total_sales,
        "recent_orders": recent_orders,
        "top_products": top_products,

        # ⭐ NEW FIELD
        "top_selling_items": top_selling_items,

        "delivery_status_counts": delivery_status_counts,

        "daily_sales": {
            "labels": json.dumps(daily_labels),
            "values": json.dumps(daily_values),
        },

        "category_sales": {
            "labels": json.dumps(category_labels),
            "values": json.dumps(category_values),
        },

        "top_products_chart": {
            "labels": json.dumps(top_labels),
            "values": json.dumps(top_values),
        },
    }

    return render(request, "core/admin_dashboard.html", context)


from .forms import VendorProductForm

def is_vendor(user):
    return user.is_authenticated and getattr(user, "role", None) == "vendor"
@login_required
@user_passes_test(is_vendor)
def vendor_dashboard(request):

    products = Product.objects.filter(vendor=request.user).order_by('-id')
    form = VendorProductForm(request.POST or None, request.FILES or None)

    # Add Product
    if request.method == "POST":
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            messages.success(request, f"✅ '{product.title}' added successfully!")
            return redirect('vendor_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")

    # -------------------------
    # 📌 VENDOR STATISTICS
    # -------------------------

    # Total Revenue
    total_revenue = (
        OrderItem.objects.filter(product__vendor=request.user)
        .aggregate(total=Sum(F("price") * F("quantity")))["total"]
        or 0
    )

    # Total Orders (unique)
    total_orders = (
        OrderItem.objects.filter(product__vendor=request.user)
        .values('order')
        .distinct()
        .count()
    )

    # Total Products
    total_products = products.count()

    # Sales breakdown per product
    sales_data = (
        OrderItem.objects.filter(product__vendor=request.user)
        .values('product__title')
        .annotate(
            total_sales=Sum(F('price') * F('quantity')),
            total_quantity=Sum('quantity')
        )
        .order_by('-total_sales')
    )

    context = {
        'form': form,
        'products': products,
        'sales_data': sales_data,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_products': total_products,
    }

    return render(request, 'core/vendor_dashboard.html', context)


@login_required
@user_passes_test(is_vendor)
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user)
    form = VendorProductForm(request.POST or None, request.FILES or None, instance=product)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, f"✏️ '{product.title}' updated successfully!")
            return redirect('vendor_dashboard')

    return render(request, 'core/vendor_edit.html', {'form': form, 'product': product})

@login_required
@user_passes_test(is_vendor)
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user)
    product.delete()
    messages.warning(request, f"🗑️ '{product.title}' deleted successfully.")
    return redirect('vendor_dashboard')

from django.db.models.functions import Lower

def offers_page(request):
    sort = request.GET.get('sort', '')
    category_filter = request.GET.get('category', '')

    products = Product.objects.filter(is_offer=True)

    if category_filter:
        products = products.filter(category__name__icontains=category_filter)

    if sort == 'price_low':
        products = products.order_by('discount_percent')

    elif sort == 'price_high':
        products = products.order_by('-discount_percent')

    elif sort == 'name_asc':    
        products = products.order_by(Lower('title'))

    elif sort == 'name_desc':    
        products = products.order_by(Lower('title').desc())

    categories = Category.objects.all()

    return render(request, "core/offers.html", {
        "products": products,
        "sort": sort,
        "selected_category": category_filter,
        "categories": categories,
    })


def check_delivery_zone(request):
    """AJAX: Validate if pincode and city combination is deliverable."""
    pincode = request.GET.get('pincode', '').strip()
    street = request.GET.get('street', '').strip().lower()
    city = request.GET.get('city', '').strip().lower()

    if not pincode:
        return JsonResponse({'success': False, 'message': 'Please enter a valid pincode.'})

    try:
        zone = DeliveryZone.objects.get(pincode=pincode, is_active=True)
        zone_city = zone.city.lower().strip()

        if city and city != zone_city:
            return JsonResponse({
                'success': False,
                'message': f'❌ Delivery not available: Pincode {pincode} belongs to {zone.city}, not {city.title()}.'
            })
        message = f'✅ Delivery available in {zone.area_name} ({zone.city}) within {zone.delivery_delay_hours} hours.'
        return JsonResponse({'success': True, 'message': message})

    except DeliveryZone.DoesNotExist:
        known_streets = ['mg road', 'church street', 'koramangala', 'indiranagar']
        if any(street_name in street for street_name in known_streets):
            return JsonResponse({'success': True, 'message': '✅ Delivery available in your street area within 2 hours.'})

        return JsonResponse({'success': False, 'message': '❌ Sorry, delivery not available in this location yet.'})

def get_available_slots(request):
    """Return available delivery slots for a given delivery zone."""
    pincode = request.GET.get('pincode', '').strip()

    if not pincode:
        return JsonResponse({'success': False, 'message': 'No pincode provided.'})

    try:
        zone = DeliveryZone.objects.get(pincode=pincode, is_active=True)
        slots = zone.get_slots() if hasattr(zone, 'get_slots') else []
        return JsonResponse({
            'success': True,
            'slots': slots,
            'delay_hours': zone.delivery_delay_hours,
        })
    except DeliveryZone.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Delivery zone not found.'})

from django.http import JsonResponse
def set_delivery_location(request):
    zone_id = request.GET.get('zone_id')

    if not zone_id:
        return JsonResponse({'success': False, 'message': 'No delivery zone selected.'})

    try:
        zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
        old_zone_id = request.session.get('selected_zone')
        request.session['selected_zone'] = zone.id
        if old_zone_id and old_zone_id != zone.id:
            msg = f'✅ Delivery area updated to {zone.area_name} ({zone.pincode}).'
        else:
            msg = f'✅ Delivering to {zone.area_name} ({zone.pincode}).'

        return JsonResponse({'success': True, 'message': msg})

    except DeliveryZone.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid delivery area.'})

def get_delivery_zones(request):
    zones = DeliveryZone.objects.filter(is_active=True).order_by('area_name')
    data = [
        {
            'id': z.id,
            'area_name': z.area_name,
            'pincode': z.pincode,
            'city': z.city,
            'delay_hours': z.delivery_delay_hours
        }
        for z in zones
    ]
    return JsonResponse({'zones': data})


def check_delivery(request):
    """AJAX endpoint: check if delivery available for entered area/pincode"""
    query = request.GET.get('query', '').strip()

    if not query:
        return JsonResponse({'success': False, 'message': 'Please enter a valid area or pincode.'})
    zone = DeliveryZone.objects.filter(pincode__iexact=query, is_active=True).first()

    if not zone:
        zone = DeliveryZone.objects.filter(area_name__icontains=query, is_active=True).first()

    if zone:
        return JsonResponse({
            'success': True,
            'message': f'✅ Delivery available in {zone.area_name} ({zone.city}) within {zone.delivery_delay_hours} hours.',
            'zone_id': zone.id
        })
    else:
        return JsonResponse({
            'success': False,
            'message': '❌ Sorry, we don’t deliver to this location yet.'
        })

def home_check_delivery(request):
    """Check if entered pincode or area is deliverable."""
    query = request.GET.get('query', '').strip()

    zones = DeliveryZone.objects.filter(is_active=True).order_by('area_name')
    available_zones = [
        {
            'id': z.id,
            'area_name': z.area_name,
            'pincode': z.pincode,
            'city': z.city,
            'delay_hours': z.delivery_delay_hours,
        }
        for z in zones
    ]

    if not query:
        return JsonResponse({
            'success': False,
            'message': 'Please enter a valid pincode or area name.',
            'available_zones': available_zones
        })

    zone = (
        DeliveryZone.objects.filter(pincode__iexact=query, is_active=True).first() or
        DeliveryZone.objects.filter(area_name__icontains=query, is_active=True).first()
    )

    if zone:
        return JsonResponse({
            'success': True,
            'message': f'✅ Delivery available in {zone.area_name} ({zone.city}) within {zone.delivery_delay_hours} hours.',
            'zone_id': zone.id,
            'available_zones': available_zones
        })

    return JsonResponse({
        'success': False,
        'message': '❌ Sorry, we don’t deliver to this location yet.',
        'available_zones': available_zones
    })


def home_get_zones(request):
    """Return all active delivery zones."""
    zones = DeliveryZone.objects.filter(is_active=True).order_by('area_name')
    data = [
        {
            'id': z.id,
            'area_name': z.area_name,
            'pincode': z.pincode,
            'city': z.city,
            'delay_hours': z.delivery_delay_hours
        }
        for z in zones
    ]
    return JsonResponse({'zones': data})


def home_set_location(request):
    """Set selected delivery zone in session."""
    zone_id = request.GET.get('zone_id')
    try:
        zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
        request.session['selected_zone'] = zone.id
        return JsonResponse({
            'success': True,
            'message': f'Delivering to {zone.area_name} ({zone.pincode})'
        })
    except DeliveryZone.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid delivery area.'})

def clear_delivery_location(request):
    request.session.pop('selected_zone', None)
    return JsonResponse({'success': True, 'message': 'Delivery location cleared.'})


def save_model(self, request, obj, form, change):
    if obj.is_offer and not obj.offer_start:
        obj.offer_start = timezone.now()

    if obj.is_offer and not obj.offer_end:
        obj.offer_end = timezone.now() + timedelta(days=7)
    super().save_model(request, obj, form, change)

from decimal import Decimal
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt

def calculate_final_price(product, weight, quantity):
    weight_value = Decimal(str(product.convert_weight_value(weight)))
    unit_price = Decimal(str(
        product.discounted_price if product.is_offer_active else product.base_price
    ))
    qty = Decimal(str(quantity))
    return (unit_price * weight_value * qty).quantize(Decimal("0.01"))


@csrf_exempt
def payment_page(request):
    user = request.user
    buy_now_item = request.session.get("buy_now_item")

    if buy_now_item:
        product = Product.objects.get(id=buy_now_item["product_id"])
        quantity = buy_now_item["quantity"]
        weight = buy_now_item.get("weight", product.unit)

        class TempItem: pass
        tmp = TempItem()
        tmp.product = product
        tmp.quantity = quantity
        tmp.weight = weight
        tmp.final_price = calculate_final_price(product, weight, quantity)

        cart_items = [tmp]

    else:
        cart_items = CartItem.objects.filter(user=user)

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("cart")

        for item in cart_items:
            item.final_price = calculate_final_price(
                item.product, item.weight, item.quantity
            )

    subtotal = sum(item.final_price for item in cart_items)
    tax = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    total = (subtotal + tax).quantize(Decimal("0.01"))

    zones = DeliveryZone.objects.filter(is_active=True)

    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":

        form = OrderForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"status": "error", "message": form.errors}, status=400)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        rzp_order = client.order.create({
            "amount": int(total * 100),
            "currency": "INR",
            "payment_capture": 1,
        })

        request.session["pending_order"] = {
            "form_data": request.POST,
            "subtotal": str(subtotal),
            "tax": str(tax),
            "total": str(total),
            "rzp_order_id": rzp_order["id"],
            "buy_now": buy_now_item,
        }

        return JsonResponse({
            "status": "created",
            "razorpay_order_id": rzp_order["id"],
            "amount": int(total * 100),
            "key": settings.RAZORPAY_KEY_ID,
        })

    form = OrderForm(initial={
        "full_name": user.get_full_name() or "",
        "email": user.email,
        "phone": getattr(user, "phone", ""),
    })

    return render(request, "core/payment.html", {
        "form": form,
        "zones": zones,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    })

@csrf_exempt
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    data = json.loads(request.body)

    rzp_order_id = data.get("razorpay_order_id")
    rzp_payment_id = data.get("razorpay_payment_id")
    rzp_signature = data.get("razorpay_signature")

    session_data = request.session.get("pending_order")
    if not session_data:
        return JsonResponse({"status": "error", "message": "Session expired"}, status=400)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_payment_id,
            "razorpay_signature": rzp_signature
        })
    except:
        return JsonResponse({"status": "error", "message": "Payment verification failed"}, status=400)

    form_data = session_data["form_data"]

    subtotal = Decimal(str(session_data["subtotal"]))
    tax = Decimal(str(session_data["tax"]))
    total = Decimal(str(session_data["total"]))

    form = OrderForm(form_data)
    order = form.save(commit=False)

    order.user = request.user
    order.payment_method = "RAZORPAY"
    order.payment_status = "Paid"
    order.status = "confirmed"
    order.subtotal = subtotal
    order.tax = tax
    order.total_amount = total
    order.razorpay_order_id = rzp_order_id
    order.razorpay_payment_id = rzp_payment_id
    order.save()

    if session_data.get("buy_now"):
        item = session_data["buy_now"]
        product = Product.objects.get(id=item["product_id"])
        qty = item["quantity"]
        weight = item.get("weight", product.unit)

        final_price = calculate_final_price(product, weight, qty)

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=qty,
            price=final_price,
        )

    else:
        cart_items = CartItem.objects.filter(user=request.user)

        for item in cart_items:
            final_price = calculate_final_price(item.product, item.weight, item.quantity)

            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=final_price,
            )

        cart_items.delete()

    del request.session["pending_order"]

    return JsonResponse({"status": "success", "order_id": order.id})

def order_failed(request):
    return render(request, 'core/order_failed.html', {
        'message': 'Payment was not completed or verification failed. Please try again.'
    })

WAREHOUSE_LAT = 12.9716
WAREHOUSE_LON = 77.5946

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371 

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

def parse_slot(slot_raw):
    slot_raw = slot_raw.replace(" ", "").upper()

    start_raw, end_raw = slot_raw.split("-")

    if len(start_raw) <= 4:
        start_raw = start_raw[:-2].zfill(2) + ":00" + start_raw[-2:]

    if len(end_raw) <= 4:
        end_raw = end_raw[:-2].zfill(2) + ":00" + end_raw[-2:]

    start_time = datetime.strptime(start_raw, "%I:%M%p").time()
    end_time = datetime.strptime(end_raw, "%I:%M%p").time()

    return start_time, end_time

@csrf_exempt
def check_delivery_feasibility(request):

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"})

    zone_id = request.POST.get("zone_id")
    slot = request.POST.get("slot")
    lat = request.POST.get("latitude")
    lon = request.POST.get("longitude")

    if not zone_id or not slot:
        return JsonResponse({"status": "error", "message": "Select area & slot"})

    try:
        zone = DeliveryZone.objects.get(id=zone_id)
    except:
        return JsonResponse({"status": "error", "message": "Invalid zone"})

    try:
        user_lat = float(lat) if lat else float(zone.latitude)
        user_lon = float(lon) if lon else float(zone.longitude)
    except:
        return JsonResponse({"status": "error", "message": "Invalid coordinates"})

    distance_km = calculate_distance(
        settings.STORE_LATITUDE,
        settings.STORE_LONGITUDE,
        user_lat,
        user_lon
    )

    s = slot.upper().replace(" ", "")
    start_raw, end_raw = s.split("-")

    def normalize(t):
        if len(t) <= 4:
            return t[:-2].zfill(2) + ":00" + t[-2:]
        return t

    start_norm = normalize(start_raw)
    end_norm = normalize(end_raw)

    slot_start = datetime.strptime(start_norm, "%I:%M%p").time()
    slot_end = datetime.strptime(end_norm, "%I:%M%p").time()

    today = timezone.localdate()
    now = timezone.localtime()

    start_dt = timezone.make_aware(datetime.combine(today, slot_start))
    end_dt = timezone.make_aware(datetime.combine(today, slot_end))

    if now.time() > slot_start:
        start_dt += timedelta(days=1)
        end_dt += timedelta(days=1)

    if distance_km <= 3: add_minutes = 20
    elif distance_km <= 6: add_minutes = 30
    elif distance_km <= 8: add_minutes = 40
    elif distance_km <= 12: add_minutes = 50
    else: add_minutes = 60

    eta_dt = start_dt + timedelta(minutes=add_minutes)

    formatted_eta = eta_dt.strftime("%I:%M %p")
    day_label = "Today" if eta_dt.date() == today else "Tomorrow"

    return JsonResponse({
        "status": "on_time",
        "eta": formatted_eta,
        "distance_km": round(distance_km, 1),
        "slot_window": f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}",
        "day_label": day_label,
        "message": f"ETA {formatted_eta} (Distance {distance_km:.1f} km)",
    })

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.subtotal == 0 or order.total_amount == 0:
        order.calculate_totals()

    if not order.expected_delivery_time:
        order.calculate_expected_delivery()

    order.update_status()

    return render(request, 'core/order_confirmation.html', {'order': order})



@login_required
def track_order(request):
    order_id = request.GET.get('order_id')
    order = None
    not_found = False

    if order_id:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            not_found = True
        else:
            if order.status == "processing" and (order.current_latitude is None or order.current_longitude is None):
                order.current_latitude = settings.WAREHOUSE_LAT
                order.current_longitude = settings.WAREHOUSE_LON
                order.save(update_fields=["current_latitude", "current_longitude"])
                order.update_status()

            order.simulate_movement()

            prev_status = order.status
            order.update_status()
            if order.status != prev_status:
                order.send_status_notification()
                order.last_notified_status = order.status
                order.save(update_fields=['last_notified_status'])

    return render(request, 'core/track_order.html', {
        'order': order,
        'order_id': order_id,
        'not_found': not_found,
        'WAREHOUSE_LAT': settings.WAREHOUSE_LAT,
        'WAREHOUSE_LON': settings.WAREHOUSE_LON,
    })

@login_required
def track_location(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    return JsonResponse({
        "driver_lat": order.current_latitude,
        "driver_lon": order.current_longitude,
        "customer_lat": order.latitude,
        "customer_lon": order.longitude,
        "status": order.status,
    })

@login_required
def confirm_delivery(request, order_id):
    """Admin or staff can manually mark a delayed/failed order as confirmed."""
    try:
        order = Order.objects.get(id=order_id)
        if order.status in ['failed', 'delayed', 'out_for_delivery']:
            order.confirm_delivery()
            messages.success(request, f"✅ Delivery confirmed for Order #{order.id}")
        else:
            messages.info(request, "Order already delivered or confirmed.")
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")

    return redirect('track_order')

class DeliveryZoneViewSet(viewsets.ModelViewSet):
    queryset = DeliveryZone.objects.all()
    serializer_class = DeliveryZoneSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['city', 'pincode', 'is_active']
    search_fields = ['area_name', 'city']

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'status', 'city', 'delivery_zone']  
    search_fields = ['full_name', 'email', 'phone', 'city']  
    ordering_fields = ['created_at', 'total_amount'] 

@login_required
def get_delivery_estimate(request):
    """Return live delivery distance and ETA based on selected area."""
    zone_id = request.GET.get("zone_id")
    if not zone_id:
        return JsonResponse({"success": False, "message": "No zone selected."})

    try:
        zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
    except DeliveryZone.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid zone selected."})

    distance = calculate_distance_km(
        settings.STORE_LATITUDE, settings.STORE_LONGITUDE,
        zone.latitude, zone.longitude
    )

    delay_hours = get_delivery_delay(zone)

    expected_delivery = timezone.now() + timedelta(hours=delay_hours)

    eta_formatted = expected_delivery.strftime("%b %d, %Y %I:%M %p")

    return JsonResponse({
        "success": True,
        "zone": zone.area_name,
        "distance": round(distance, 2),
        "delay_hours": delay_hours,
        "expected_delivery": eta_formatted,  # ⭐ ADD THIS
        "message": f"🚚 Approx. {distance:.2f} km away — expected delivery within {delay_hours} hours.",
    })

@csrf_exempt
def get_nearest_zone(request):
    """Return the nearest delivery zone based on given coordinates."""
    try:
        lat = float(request.POST.get('latitude'))
        lon = float(request.POST.get('longitude'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)

    nearest_zone = None
    nearest_distance = float('inf')

    for zone in DeliveryZone.objects.filter(is_active=True):
        if zone.latitude and zone.longitude:
            dist = calculate_distance_km(lat, lon, zone.latitude, zone.longitude)
            if dist < nearest_distance:
                nearest_distance = dist
                nearest_zone = zone

    if not nearest_zone:
        return JsonResponse({'error': 'No delivery zones found'}, status=404)

    return JsonResponse({
        'zone_id': nearest_zone.id,
        'zone_name': nearest_zone.area_name,
        'pincode': nearest_zone.pincode,
        'distance_km': round(nearest_distance, 2)
    })

def haversine_distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmbda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmbda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def check_delivery_with_slot(request):
    """
    AJAX endpoint:
    Checks if delivery from store → customer location can reach within chosen time slot.
    POST params: zone_id, latitude, longitude, slot (e.g., "4PM - 6PM")
    """
    try:
        zone_id = int(request.POST.get('zone_id'))
        lat = float(request.POST.get('latitude'))
        lon = float(request.POST.get('longitude'))
        slot_str = request.POST.get('slot', '').strip()
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid input data.'})

    try:
        zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
    except DeliveryZone.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid delivery zone selected.'})

    distance_km = haversine_distance_km(
        float(settings.STORE_LATITUDE),
        float(settings.STORE_LONGITUDE),
        lat,
        lon,
    )

    speed_kmph = 15.0
    estimated_hours = distance_km / speed_kmph
    estimated_minutes = estimated_hours * 60  

    try:
        slot_parts = slot_str.upper().split('-')
        slot_start = datetime.strptime(slot_parts[0].strip(), "%I%p").time()
        slot_end = datetime.strptime(slot_parts[1].strip(), "%I%p").time()

        today = timezone.localdate()
        slot_start_dt = timezone.make_aware(datetime.combine(today, slot_start))
        slot_end_dt = timezone.make_aware(datetime.combine(today, slot_end))

        if timezone.now() > slot_end_dt:
            slot_start_dt += timedelta(days=1)
            slot_end_dt += timedelta(days=1)
    except Exception:
        return JsonResponse({'success': False, 'message': f'Invalid slot format: {slot_str}'})

    eta_dt = timezone.now() + timedelta(minutes=estimated_minutes)

    if estimated_minutes < 60:
        eta_text = f"{int(round(estimated_minutes))} minutes"
    else:
        hours = int(estimated_minutes // 60)
        mins = int(estimated_minutes % 60)
        eta_text = f"{hours} hr {mins} min" if mins > 0 else f"{hours} hr"

    if eta_dt <= slot_end_dt:
        return JsonResponse({
            'success': True,
            'message': (
                f"✅ Delivery expected within chosen slot ({slot_str}). "
                f"ETA: {eta_dt.strftime('%I:%M %p')}, "
                f"Distance: {distance_km:.1f} km, "
                f"Estimated time: {eta_text}."
            ),
            'distance_km': round(distance_km, 2),
            'estimated_minutes': round(estimated_minutes, 1),
            'eta': eta_dt.strftime('%I:%M %p'),
        })
    else:
        return JsonResponse({
            'success': False,
            'message': (
                f"⚠️ Delivery might not reach within the selected slot ({slot_str}). "
                f"ETA: {eta_dt.strftime('%I:%M %p')} (Distance: {distance_km:.1f} km, "
                f"Estimated time: {eta_text})."
            ),
            'distance_km': round(distance_km, 2),
            'estimated_minutes': round(estimated_minutes, 1),
            'eta': eta_dt.strftime('%I:%M %p'),
        })

User = get_user_model()

def check_email_exists(request):
    email = request.GET.get('email', '').strip()
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'exists': exists})

def username_suggestions(request):
    q = request.GET.get('q', '').strip()
    suggestions = []
    if q:
        users = User.objects.filter(username__istartswith=q).values_list('username', flat=True)[:5]
        suggestions = list(users)
    return JsonResponse({'suggestions': suggestions})

def check_phone_exists(request):
    phone = request.GET.get('phone', '').strip()
    exists = User.objects.filter(phone__iexact=phone).exists()
    return JsonResponse({'exists': exists})

def order_confirmation_no_id(request):
    return render(request, 'order_failed.html', {
        'message': 'No order ID received. Payment may have been canceled.'
    })
    
    
def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status in ["out_for_delivery", "delivered"]:
        messages.error(request, "You cannot edit this order now.")
        return redirect("order_confirmation", order_id=order.id)

    if request.method == "POST":
        form = EditOrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            order.calculate_expected_delivery()
            order.save()

            messages.success(request, "Delivery details updated successfully!")
            return redirect("order_confirmation", order_id=order.id)
    else:
        form = EditOrderForm(instance=order)

    if order.delivery_zone:
        selected_zone = f"{order.delivery_zone.area_name} ({order.delivery_zone.pincode})"
    else:
        selected_zone = None

    selected_slot = order.delivery_slot if order.delivery_slot else None

    return render(
        request,
        "core/edit_order.html",
        {
            "form": form,
            "order": order,
            "selected_zone": selected_zone,
            "selected_slot": selected_slot,
            "zones": DeliveryZone.objects.all(),
        }
    )

def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status in ["out_for_delivery", "delivered"]:
        return redirect(f"/order-confirmation/{order.id}/?msg=locked")

    if request.method == "POST":
        form = CancelOrderForm(request.POST)

        if form.is_valid():
            reason = form.cleaned_data["reason"]
            other_reason = form.cleaned_data.get("other_reason")

            fixable_reasons = [
                "wrong_address",
                "wrong_slot",
                "change_address",
                "edit_details",  
            ]

            if reason in fixable_reasons:
                return redirect(f"/order/{order.id}/edit/?msg=edit")

            if reason == "other":
                final_reason = other_reason or "No reason provided"
            else:
                final_reason = dict(form.fields["reason"].choices).get(reason)

            order.status = "cancelled"
            order.save()

            send_order_email(
                order.email,
                "Your Order Has Been Cancelled",
                "emails/order_cancelled.html",
                {"order": order, "reason": final_reason}
            )

            return redirect(f"/order-confirmation/{order.id}/?msg=cancelled")

    form = CancelOrderForm()
    return render(request, "core/cancel_order.html", {"form": form, "order": order})


@login_required
def start_dispatch(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    order.current_latitude = settings.WAREHOUSE_LAT
    order.current_longitude = settings.WAREHOUSE_LON

    order.status = "out_for_delivery"

    order.save(update_fields=['current_latitude', 'current_longitude', 'status'])
    order.send_status_notification()

    return redirect('order_confirmation', order.id)

@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "core/my_orders.html", {"orders": orders})

def features_page(request):
    return render(request, "core/features.html")

def payment_info(request):
    return render(request, "core/payment_info.html")

def quality_info(request):
    return render(request, "core/quality_info.html")

import requests
from django.http import JsonResponse

def reverse_geocode(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "VetriMartDeliveryTracker/1.0"
    }

    response = requests.get(url, params=params, headers=headers)
    return JsonResponse(response.json(), safe=False)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def mark_order_delivered(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        order.status = "delivered"
        order.save(update_fields=["status"])

        order.send_status_notification()  

        return JsonResponse({"success": True})
    except:
        return JsonResponse({"success": False}, status=500)


def delivery_info(request):
    return render(request, 'core/delivery-info.html')

def fresh_organic(request):
    return render(request, 'core/fresh-organic.html')
def support(request):
    return render(request, 'core/support.html')
def payment_info(request):
    return render(request, 'core/payment_info.html')

def quality_info(request):
    return render(request, 'core/quality_info.html')


User = get_user_model()

import random

def forgot_password(request):

    list(messages.get_messages(request))

    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            # Check user exists
            try:
                user = CustomUser.objects.get(email__iexact=email)
            except CustomUser.DoesNotExist:
                messages.error(request, "❌ This email is not registered.")
                return redirect("forgot_password")

            # Clear previous OTP
            PasswordResetOTP.objects.filter(user=user).delete()

            otp = str(random.randint(100000, 999999))

            PasswordResetOTP.objects.create(user=user, otp=otp)

            try:
                send_mail(
                    subject="Your VetriMart Password Reset OTP",
                    message=f"Your OTP for password reset is: {otp}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                messages.error(request, "Unable to send OTP. Please try again.")
                return redirect("forgot_password")

            request.session["reset_user_id"] = user.id
            messages.success(request, "OTP sent to your email.")
            return redirect("verify_otp")

    else:
        form = ForgotPasswordForm()

    return render(request, "core/forgot_password.html", {"form": form})

def verify_otp(request):

    if "reset_user_id" not in request.session:
        return redirect("forgot_password")

    try:
        user = CustomUser.objects.get(id=request.session["reset_user_id"])
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data["otp"].strip()

            otp_obj = PasswordResetOTP.objects.filter(
                user=user, otp=otp
            ).order_by("-created_at").first()

            if not otp_obj:
                messages.error(request, "Invalid OTP.")
                return redirect("verify_otp")

            if not otp_obj.is_valid():
                messages.error(request, "OTP expired.")
                return redirect("forgot_password")

            request.session["otp_verified"] = True
            return redirect("reset_password")

    else:
        form = OTPVerifyForm()

    return render(request, "core/verify_otp.html", {"form": form})


def reset_password(request):

    if "reset_user_id" not in request.session or "otp_verified" not in request.session:
        return redirect("forgot_password")

    try:
        user = CustomUser.objects.get(id=request.session["reset_user_id"])
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)

        if form.is_valid():
            new_password = form.cleaned_data["new_password"]

            user.set_password(new_password)
            user.save()

            request.session.pop("reset_user_id", None)
            request.session.pop("otp_verified", None)

            messages.success(request, "Password reset successfully!")
            return redirect("login")

    else:
        form = ResetPasswordForm()

    return render(request, "core/reset_password.html", {"form": form})

@login_required(login_url='login')
def checkout(request):
    return render(request, "core/checkout.html")


def contact_page(request):
    if request.method == 'POST':
        form = ContactForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "contact_success",
                extra_tags="contact"
            )

            return redirect('contact_page')

        else:
            messages.error(
                request,
                "Please fix the highlighted errors before submitting again."
            )

    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {'form': form})

from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
import logging

logger = logging.getLogger(__name__)

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.save()
            except Exception as exc:
                logger.exception("Failed saving user: %s", exc)
                form.add_error(None, "An unexpected error occurred. Please try again.")
                return render(request, 'core/register.html', {'form': form})

            login(request, user, backend='core.backends.EmailBackend')

            guest_cart = request.session.get("cart", [])

            for item in guest_cart:
                try:
                    product = Product.objects.get(id=item["product_id"])
                except Product.DoesNotExist:
                    continue

                weight = item.get("weight", "1")
                quantity = int(item.get("quantity", 1))

                cart_item, created = CartItem.objects.get_or_create(
                    user=user,
                    product=product,
                    weight=weight,
                    defaults={"quantity": quantity}
                )

                if not created:
                    cart_item.quantity += quantity
                    cart_item.save()

            if "cart" in request.session:
                del request.session["cart"]
            request.session.modified = True

            guest_wishlist = request.session.get("wishlist", [])

            for pid in guest_wishlist:
                try:
                    product = Product.objects.get(id=pid)
                    product.wishlist_users.add(user)
                except Product.DoesNotExist:
                    pass

            if "wishlist" in request.session:
                del request.session["wishlist"]
            request.session.modified = True

            user_name = user.email.split("@")[0] if user.email else "User"
            try:
                send_mail(
                    subject="Welcome to VetriMart!",
                    message=(
                        f"Hi {user_name},\n\n"
                        "Your account has been created successfully.\n"
                        "You can now order groceries and track delivery live.\n\n"
                        "Thank you for joining VetriMart!"
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER),
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.exception("Failed to send welcome email to %s: %s", user.email, e)
                messages.warning(request, "Account created but welcome email could not be delivered.")

            messages.success(request, "🎉 Your account has been created successfully!")
            return redirect('cart')  

        else:
            return render(request, 'core/register.html', {'form': form})

    else:
        form = CustomUserCreationForm()

    return render(request, 'core/register.html', {'form': form})

from core.forms import EmailLoginForm

def login_view(request):
    if request.user.is_authenticated:
        next_url = request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("/")

    form = EmailLoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():

            email = form.cleaned_data["username"].strip().lower()
            password = form.cleaned_data["password"]

            user = authenticate(request, username=email, password=password)

            if user is not None:

                login(request, user, backend="core.backends.EmailBackend")


                guest_cart = request.session.get("cart", [])

                for item in guest_cart:
                    try:
                        product = Product.objects.get(id=item["product_id"])
                    except Product.DoesNotExist:
                        continue

                    weight = item.get("weight", "1")
                    qty = int(item.get("quantity", 1))

                    cart_item, created = CartItem.objects.get_or_create(
                        user=user,
                        product=product,
                        weight=weight,
                        defaults={"quantity": qty},
                    )

                    if not created:
                        cart_item.quantity += qty
                        cart_item.save()

                if "cart" in request.session:
                    del request.session["cart"]
                request.session.modified = True

                guest_wishlist = request.session.get("wishlist", [])

                for product_id in guest_wishlist:
                    try:
                        product = Product.objects.get(id=product_id)
                        product.wishlist_users.add(user)
                    except Product.DoesNotExist:
                        pass

                if "wishlist" in request.session:
                    del request.session["wishlist"]
                request.session.modified = True


                next_url = request.GET.get("next")

                if next_url:
                    return redirect(next_url)

                if user.role in ["admin", "vendor"]:
                    return redirect("/")

                return redirect("/")

            else:
                form.add_error("username", "Invalid email or password.")
                form.add_error("password", "Invalid email or password.")

    return render(request, "core/login.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


@login_required
def update_cart_qty(request, item_id, qty):
    try:
        item = CartItem.objects.get(id=item_id, user=request.user)

        item.quantity = int(qty)
        item.save()

        cart_items = CartItem.objects.filter(user=request.user)

        subtotal = Decimal("0.00")
        for ci in cart_items:
            weight_value = Decimal(str(ci.product.convert_weight_value(ci.weight)))
            unit_price = ci.product.discounted_price if ci.product.is_offer_active else ci.product.base_price
            final_price = unit_price * weight_value * ci.quantity
            subtotal += final_price

        tax = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        total = (subtotal + tax).quantize(Decimal("0.01"))

        return JsonResponse({
            "success": True,
            "subtotal": f"{subtotal:.2f}",
            "tax": f"{tax:.2f}",
            "total": f"{total:.2f}",
        })

    except CartItem.DoesNotExist:
        return JsonResponse({"success": False}, status=404)

@csrf_exempt
def update_guest_cart_qty(request):
    cart = request.session.get("cart", [])
    product_id = request.POST.get("product_id")
    weight = request.POST.get("weight")
    qty = int(request.POST.get("qty"))

    for item in cart:
        if str(item["product_id"]) == str(product_id) and item["weight"] == weight:
            item["quantity"] = qty

            # FIX: support both weight_multiplier and converted_weight
            weight_val = Decimal(str(
                item.get("weight_multiplier") or 
                item.get("converted_weight") or 
                1
            ))

            unit_price = Decimal(str(item["unit_price"]))
            item["final_price"] = float(unit_price * weight_val * qty)
            break

    request.session["cart"] = cart
    request.session.modified = True

    return JsonResponse({"success": True})

