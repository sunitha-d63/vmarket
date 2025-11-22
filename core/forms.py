from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate
import re

from .models import (
    Order,
    DeliveryZone,
    Product,
    ContactMessage,
    CustomUser,
)
from .choices import SLOT_CHOICES


User = get_user_model()

class UserLoginForm(forms.Form):
    identifier = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email or Username'}),
        required=True
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get('identifier', '').strip().lower()
        password = cleaned_data.get('password')

        if not identifier or not password:
            raise ValidationError("Please provide both identifier and password.")

        user_obj = CustomUser.objects.filter(username__iexact=identifier).first()

        if user_obj is None:
            user_obj = CustomUser.objects.filter(email__iexact=identifier).first()

        if user_obj is None:
            raise ValidationError("Invalid username/email or password.")

        user = authenticate(email=user_obj.email, password=password)

        if user is None:
            raise ValidationError("Invalid username/email or password.")

        if not user.is_active:
            raise ValidationError("This account is inactive.")

        cleaned_data['user'] = user
        return cleaned_data

    def get_user(self):
        return self.cleaned_data.get('user')


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email',
            'class': 'form-control',
        })
    )

    phone = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Phone Number',
            'class': 'form-control',
        })
    )

    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'phone', 'role', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise ValidationError("Enter a valid 10-digit Indian mobile number.")
        if CustomUser.objects.filter(phone=phone).exists():
            raise ValidationError("This phone number is already used.")
        return phone


class AddToCartForm(forms.Form):
    weight = forms.CharField(required=True)
    quantity = forms.IntegerField(min_value=1, initial=1)

class OrderForm(forms.ModelForm):

    delivery_zone = forms.ModelChoiceField(
        queryset=DeliveryZone.objects.filter(is_active=True).order_by('area_name'),
        required=False,
        label="Select Delivery Area / Pincode",
        empty_label="Choose your delivery area"
    )

    delivery_slot = forms.ChoiceField(
        choices=SLOT_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    address_from_map = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Order
        fields = [
            'full_name', 'email', 'phone',
            'street_address', 'city',
            'delivery_zone', 'delivery_slot',
            'latitude', 'longitude', 'address_from_map'
        ]

    def __init__(self, *args, **kwargs):
        available_slots = kwargs.pop('available_slots', None)
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': field.label
                })

        if available_slots:
            self.fields['delivery_slot'].choices = [(s, s) for s in available_slots]

    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not re.match(r'^[A-Za-z\s]{3,50}$', name):
            raise ValidationError("Full name should contain only letters and spaces.")
        return name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise ValidationError("Enter a valid 10-digit mobile number.")
        return phone

    def clean_city(self):
        city = self.cleaned_data.get('city', '').strip()
        if not re.match(r'^[A-Za-z\s]{2,50}$', city):
            raise ValidationError("City should contain only letters.")
        return city

    def clean_street_address(self):
        street = self.cleaned_data.get('street_address', '').strip()
        if not re.match(r'^[A-Za-z0-9\s,.-]{3,100}$', street):
            raise ValidationError("Street address contains invalid characters.")
        return street

    def clean(self):
        cleaned = super().clean()
        zone = cleaned.get('delivery_zone')
        lat = cleaned.get('latitude')
        lon = cleaned.get('longitude')

        if not zone and (not lat or not lon):
            raise ValidationError("Select a delivery area or choose a location on the map.")

        return cleaned

class VendorProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'title', 'description', 'base_price', 'weight_options', 'image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({'class': 'form-control'})
        self.fields['description'].widget.attrs['rows'] = 3


class ContactForm(forms.ModelForm):

    phone = forms.CharField(
        required=True,
        max_length=10,
        min_length=10,
        error_messages={
            "required": "Phone number is required.",
            "min_length": "Phone number must be exactly 10 digits.",
            "max_length": "Phone number must be exactly 10 digits.",
        },
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": ""
        })
    )

    email = forms.EmailField(
        required=True,
        error_messages={
            "required": "Email is required.",
            "invalid": "Enter a valid email address."
        },
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": ""
        })
    )

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'message', 'attachment']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if not phone.isdigit():
            raise forms.ValidationError("Phone number must contain digits only.")

        if len(phone) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        return phone

    def clean_subject(self):
        subject = self.cleaned_data.get("subject", "")

        if not re.search(r"[A-Za-z0-9]", subject):
            raise forms.ValidationError("Subject cannot contain only special characters.")

        return subject

    def clean_message(self):
        message = self.cleaned_data.get("message", "")

        if not re.search(r"[A-Za-z0-9]", message):
            raise forms.ValidationError("Message cannot contain only special characters.")

        return message


class EditOrderForm(forms.ModelForm):
    delivery_slot = forms.ChoiceField(
        choices=SLOT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Order
        fields = [
            'street_address', 'city', 'delivery_zone',
            'delivery_slot', 'latitude', 'longitude', 'address_from_map'
        ]
        widgets = {
            'street_address': forms.TextInput(attrs={"class": "form-control"}),
            'city': forms.TextInput(attrs={"class": "form-control"}),
            'delivery_zone': forms.Select(attrs={"class": "form-select"}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address_from_map': forms.HiddenInput(),
        }

class CancelOrderForm(forms.Form):
    REASON_CHOICES = [
        ("found_cheaper", "Found a cheaper price somewhere else"),
        ("ordered_by_mistake", "Ordered by mistake"),
        ("payment_issue", "Payment or checkout issues"),
        ("item_not_needed", "No longer need the item"),
        ("duplicate_order", "Duplicate order"),
        ("wrong_product", "Selected wrong product"),
        ("delivery_date_unsuitable", "Delivery date too late"),
        ("size_color_change", "I want to change size or color"),
        ("quantity_issue", "I want to change quantity"),
        ("not_trusted", "Do not trust transaction"),
        ("edit_details", "Want to edit delivery details"),
        ("other", "Other"),
    ]

    reason = forms.ChoiceField(choices=REASON_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    other_reason = forms.CharField(required=False, widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "Write reason here"}
    ))


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "form-control",
        "placeholder": "Enter registered email"
    }))


class OTPVerifyForm(forms.Form):
    otp = forms.CharField(max_length=6, widget=forms.TextInput(attrs={
        "class": "form-control",
        "placeholder": "Enter OTP"
    }))


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "New Password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm Password"})
    )

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters.")

        if not re.search(r"[A-Z]", password):
            raise ValidationError("Must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            raise ValidationError("Must contain at least one lowercase letter.")

        if not re.search(r"[0-9]", password):
            raise ValidationError("Must contain at least one number.")

        if re.search(r"\s", password):
            raise ValidationError("Password cannot contain spaces.")

        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")

        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")

        return cleaned


from django import forms

class EmailLoginForm(forms.Form):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your email"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password"
        })
    )
