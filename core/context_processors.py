from core.models import Product

def guest_wishlist(request):
    wishlist = request.session.get("wishlist", [])
    return {
        "guest_wishlist_ids": wishlist
    }
