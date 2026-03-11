import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="brand_initials")
def brand_initials(value: str) -> str:
    """Return initials for a brand name, used as a logo fallback."""
    if not value:
        return "?"

    text = str(value).strip()
    if not text:
        return "?"

    tokens = []
    for part in text.split():
        clean_part = "".join(char for char in part if char.isalnum())
        if clean_part:
            tokens.append(clean_part)

    if len(tokens) >= 2:
        return f"{tokens[0][0]}{tokens[1][0]}".upper()

    if len(tokens) == 1:
        return tokens[0][:2].upper()

    fallback = "".join(char for char in text if char.isalnum())
    return fallback[:2].upper() or "?"


@register.filter(needs_autoescape=True)
def highlight_inquire_to(value: str, autoescape=True) -> str:
    """Wrap known inquire targets with colored badges."""
    if not value:
        return "-"

    text = str(value)
    escape = conditional_escape if autoescape else (lambda x: x)
    highlighted = escape(text)

    replacements = [
        (r"\bEurope\b", "inquire-badge inquire-badge-europe", "Europe"),
        (r"\bUSA\b", "inquire-badge inquire-badge-usa", "USA"),
        (r"\bChina\b", "inquire-badge inquire-badge-china", "China"),
        (r"\bdecline\b", "inquire-badge inquire-badge-decline", "Decline"),
    ]

    for pattern, classes, label in replacements:
        highlighted = re.sub(
            pattern,
            f'<span class="{classes}">{label}</span>',
            highlighted,
            flags=re.IGNORECASE,
        )

    return mark_safe(highlighted)
