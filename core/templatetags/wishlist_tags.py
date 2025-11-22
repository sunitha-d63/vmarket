from django import template

register = template.Library()

@register.filter
def in_user_wishlist(product, user):
    if not user.is_authenticated:
        return False
    return product.wishlist_users.filter(id=user.id).exists()
