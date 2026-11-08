from django import template

register = template.Library()


@register.filter(name='dict_key')
def dict_key(d, k):
    """Allows looking up dictionary keys dynamically in templates."""
    if isinstance(d, dict):
        return d.get(k, None)
    return None
