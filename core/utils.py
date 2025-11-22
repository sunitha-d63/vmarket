import math
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the approximate distance (in kilometers) between two GPS coordinates
    using the Haversine formula.
    """
    try:
        if not all([lat1, lon1, lat2, lon2]):
            return 0.0  

        R = 6371 
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return round(distance, 2)
    except Exception:
        return 0.0


def get_delivery_delay(zone=None, lat=None, lon=None):
    """
    Return delivery delay (in hours) dynamically based on either:
    - a DeliveryZone object, OR
    - a pair of latitude/longitude coordinates (for custom map location)
    """
    if not zone and (lat is None or lon is None):
        return 2

    if zone and zone.latitude and zone.longitude:
        distance = calculate_distance_km(
            settings.STORE_LATITUDE,
            settings.STORE_LONGITUDE,
            zone.latitude,
            zone.longitude
        )
    elif lat is not None and lon is not None:
        distance = calculate_distance_km(
            settings.STORE_LATITUDE,
            settings.STORE_LONGITUDE,
            lat,
            lon
        )
    else:
        return 2

    if distance <= 3:
        delay = 1
    elif distance <= 6:
        delay = 2
    elif distance <= 10:
        delay = 3
    elif distance <= 15:
        delay = 4
    else:
        delay = 5

    return delay



def send_order_email(to_email, subject, template, context):
    if not to_email:
        return False

    html_message = render_to_string(template, context)
    
    send_mail(
        subject,
        html_message,
        settings.EMAIL_HOST_USER,
        [to_email],
        html_message=html_message,
        fail_silently=False
    )
    return True

