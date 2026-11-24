from django import template

from accounts.validators import PasswordComplexityValidator

register = template.Library()


@register.inclusion_tag("includes/_password_rules.html")
def password_rules(optional=False):
    """Live password checklist. Mirrors accounts.validators (see static/js/password.js)."""
    return {"fragments": list(PasswordComplexityValidator.WEAK_FRAGMENTS), "optional": optional}


@register.filter
def get_item(mapping, key):
    return mapping.get(key)
