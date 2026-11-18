from django import template

register = template.Library()


@register.filter
def ribu(value):
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return value
