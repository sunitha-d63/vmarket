from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string

from datetime import datetime, timedelta
from decimal import Decimal
from math import radians, sin, cos, sqrt, atan2

from .utils import calculate_distance_km, get_delivery_delay

class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, phone=None, role='customer', **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, phone=None, role='customer', **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, phone=phone, role=role, **extra_fields)

    def create_superuser(self, email, password, phone=None, role='admin', **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, phone=phone, role=role, **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('admin', 'Admin'),
    ]

    username = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()

        if not self.username and self.email:
            self.username = self.email.split("@")[0]

        self.username = self.username.lower().strip()
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    image = models.ImageField(upload_to='categories/')
    is_offer_category = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def product_count(self):
        return self.products.count()

    def get_absolute_url(self):
        return reverse('category_products', args=[self.id])

class Product(models.Model):

    UNIT_CHOICES = [
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("litre", "Litre"),
        ("ml", "Millilitre"),
        ("piece", "Piece"),
        ("pack", "Pack"),
        ("dozen", "Dozen"),
    ]

    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='vendor_products'
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='products/')

    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="kg")
    weight_options = models.CharField(max_length=200, default="500G,1KG,2KG")

    wishlist_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='wishlist', blank=True
    )

    is_offer = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(default=0)
    offer_start = models.DateTimeField(null=True, blank=True)
    offer_end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.category.id, self.id])

    def get_weight_options_list(self):
        return [w.strip() for w in self.weight_options.split(",")] if self.weight_options else []

    def is_in_wishlist_for_user(self, user):
        return user.is_authenticated and self.wishlist_users.filter(id=user.id).exists()

    @property
    def discounted_price(self):
        if self.is_offer_active:
            discount = (self.base_price * Decimal(self.discount_percent)) / Decimal("100")
            return (self.base_price - discount).quantize(Decimal("0.01"))
        return self.base_price

    @property
    def is_offer_active(self):
        if not self.is_offer:
            return False

        now = timezone.now()
        if self.offer_start and self.offer_end:
            return self.offer_start <= now <= self.offer_end
        return True

    @property
    def savings_amount(self):
        if self.is_offer_active and self.discount_percent > 0:
            return (self.base_price - self.discounted_price).quantize(Decimal("0.01"))
        return Decimal("0.00")

    def convert_weight_value(self, weight_str):
        if not weight_str:
            return Decimal("1")

        w = weight_str.upper().strip().replace(" ", "")

        w = (w.replace("GRAMS", "G").replace("GRAM", "G").replace("GMS", "G")
               .replace("LITRE", "L").replace("LTR", "L").replace("LITER", "L")
               .replace("MILLILITRE", "ML").replace("MILLILITER", "ML"))

        if self.unit == "kg":
            if w.endswith("KG"):
                return Decimal(w.replace("KG", ""))
            if w.endswith("G"):
                return Decimal(w.replace("G", "")) / Decimal("1000")

        if self.unit == "g":
            if w.endswith("G"):
                return Decimal(w.replace("G", "")) / Decimal("1000")
            if w.endswith("KG"):
                return Decimal(w.replace("KG", ""))

        if self.unit == "litre":
            if w.endswith("L") and not w.endswith("ML"):
                return Decimal(w.replace("L", ""))
            if w.endswith("ML"):
                return Decimal(w.replace("ML", "")) / Decimal("1000")

        if self.unit == "ml":
            if w.endswith("ML"):
                return Decimal(w.replace("ML", "")) / Decimal("1000")
            if w.endswith("L"):
                return Decimal(w.replace("L", ""))

        if self.unit == "piece":
            digits = ''.join(filter(str.isdigit, w))
            return Decimal(digits) if digits else Decimal("1")

        if self.unit == "pack":
            return Decimal("1")

        if self.unit == "dozen":
            digits = ''.join(filter(str.isdigit, w))
            return Decimal(digits) * Decimal("12") if digits else Decimal("12")

        return Decimal("1")

class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='cart_items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    weight = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def converted_weight(self):
        return self.product.convert_weight_value(self.weight)

    @property
    def total_price(self):
        weight_multiplier = self.converted_weight
        unit_price = self.product.discounted_price if self.product.is_offer_active else self.product.base_price
        return round(unit_price * weight_multiplier * self.quantity, 2)

    def __str__(self):
        return f"{self.product.title} ({self.weight}) x {self.quantity}"


class DeliveryZone(models.Model):
    area_name = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6, unique=True)
    city = models.CharField(max_length=100)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    delivery_delay_hours = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        try:
            if self.latitude is not None and self.longitude is not None:
                distance = calculate_distance_km(
                    float(settings.STORE_LATITUDE),
                    float(settings.STORE_LONGITUDE),
                    float(self.latitude),
                    float(self.longitude),
                )

                if distance <= 3:
                    self.delivery_delay_hours = 1
                elif distance <= 6:
                    self.delivery_delay_hours = 2
                elif distance <= 10:
                    self.delivery_delay_hours = 3
                elif distance <= 15:
                    self.delivery_delay_hours = 4
                else:
                    self.delivery_delay_hours = 5
        except Exception as e:
            print(f"[DeliveryZone.save] Error: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.area_name} ({self.pincode})"

class Order(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('delayed', 'Delayed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=10)

    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)

    delivery_zone = models.ForeignKey('DeliveryZone', on_delete=models.SET_NULL, null=True, blank=True)

    delivery_slot = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=20)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    address_from_map = models.CharField(max_length=255, blank=True, null=True)

    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)

    distance_km = models.FloatField(null=True, blank=True)
    expected_delivery_time = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    last_notified_status = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default="Pending")

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

    def send_status_email(self, subject, template_name, ctx):
        if not self.email:
            return False
        try:
            html = render_to_string(template_name, ctx)
            send_mail(subject, html, settings.EMAIL_HOST_USER, [self.email], html_message=html)
            return True
        except:
            return False

    def calculate_totals(self):
        subtotal = sum(item.price * item.quantity for item in self.items.all())
        tax = subtotal * Decimal('0.05')
        total = subtotal + tax

        self.subtotal = subtotal
        self.tax = tax
        self.total_amount = total

        dist = None
        if self.latitude and self.longitude:
            dist = calculate_distance_km(
                settings.STORE_LATITUDE,
                settings.STORE_LONGITUDE,
                self.latitude,
                self.longitude,
            )
        elif self.delivery_zone:
            dist = calculate_distance_km(
                settings.STORE_LATITUDE,
                settings.STORE_LONGITUDE,
                self.delivery_zone.latitude,
                self.delivery_zone.longitude,
            )

        if dist:
            self.distance_km = dist
            eta_minutes = max(10, (dist / 15) * 60)
            self.expected_delivery_time = timezone.now() + timedelta(minutes=eta_minutes)

        self.save()

    def get_distance_km(self):
        try:
            if not self.current_latitude or not self.current_longitude:
                return None
            if not self.latitude or not self.longitude:
                return None

            lat1 = radians(self.current_latitude)
            lon1 = radians(self.current_longitude)
            lat2 = radians(self.latitude)
            lon2 = radians(self.longitude)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))

            return 6371 * c
        except:
            return None

    def simulate_movement(self):
        if self.status != "out_for_delivery":
            return

        if not self.current_latitude or not self.current_longitude:
            self.current_latitude = settings.WAREHOUSE_LAT
            self.current_longitude = settings.WAREHOUSE_LON

        step = 0.00045

        if self.latitude and self.longitude:

            if abs(self.latitude - self.current_latitude) > step:
                self.current_latitude += step if self.latitude > self.current_latitude else -step
            else:
                self.current_latitude = self.latitude

            if abs(self.longitude - self.current_longitude) > step:
                self.current_longitude += step if self.longitude > self.current_longitude else -step
            else:
                self.current_longitude = self.longitude

        self.save(update_fields=['current_latitude', 'current_longitude'])

    def calculate_expected_delivery(self):
        delay_hours = 2

        if self.delivery_zone:
            delay_hours = get_delivery_delay(zone=self.delivery_zone)
        elif self.latitude and self.longitude:
            delay_hours = get_delivery_delay(lat=self.latitude, lon=self.longitude)

        def convert_to_24h(time_str):
            num = int(time_str[:-2])
            mer = time_str[-2:]
            if mer == "AM":
                return 0 if num == 12 else num
            return 12 if num == 12 else num + 12

        try:
            start_raw, _ = self.delivery_slot.split(" - ")
            start_hour = convert_to_24h(start_raw)
        except:
            start_hour = 10

        today = timezone.localtime().date()
        slot_start = timezone.make_aware(
            datetime(today.year, today.month, today.day, start_hour, 0)
        )

        final_eta = slot_start + timedelta(hours=delay_hours)
        self.expected_delivery_time = final_eta
        self.save(update_fields=["expected_delivery_time"])
        return final_eta

    def update_status(self):
        prev = self.status
        now = timezone.now()

        if self.status in ["delivered", "failed", "cancelled"]:
            return

        if self.status == "pending":
            self.status = "confirmed"

        elif self.status == "confirmed":
            self.status = "processing"

        elif self.status == "processing":
            distance = self.get_distance_km()
            if distance is not None and distance > 0.1:
                self.status = "out_for_delivery"

        if self.expected_delivery_time and now > self.expected_delivery_time:
            if self.status not in ["out_for_delivery", "delivered"]:
                self.status = "delayed"

        distance = self.get_distance_km()
        if distance is not None and distance < 0.05:
            self.status = "delivered"
            self.delivered_at = timezone.now()

        if prev != self.status:
            self.save(update_fields=['status'])
            self.send_status_notification()

    def send_status_notification(self):
        ctx = {
            "order": self,
            "tracking_url": f"{settings.SITE_URL}/track-order/?order_id={self.id}"
        }

        if self.status == "processing":
            self.send_status_email("Order Processing", "emails/order_processing.html", ctx)

        elif self.status == "out_for_delivery":
            self.send_status_email("Out for Delivery 🚚", "emails/out_for_delivery.html", ctx)

        elif self.status == "delivered":
            self.send_status_email("Delivered 🎉", "emails/order_delivered.html", ctx)

        elif self.status == "cancelled":
            self.send_status_email("Order Cancelled", "emails/order_cancelled.html", ctx)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.title} × {self.quantity}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    attachment = models.FileField(upload_to='contact_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)
