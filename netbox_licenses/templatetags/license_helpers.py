from django import template
from django.utils.html import format_html

register = template.Library()


def get_utilization_thresholds():
    """Get utilization thresholds from plugin configuration"""
    from netbox_licenses.models import PluginConfiguration

    try:
        config = PluginConfiguration.get_config()
        return {
            'excellent': config.utilization_excellent_threshold,
            'good': config.utilization_good_threshold,
            'moderate': config.utilization_moderate_threshold,
            'poor': 0
        }
    except Exception:
        # Fallback to defaults if config doesn't exist yet
        return {
            'excellent': 90,
            'good': 70,
            'moderate': 50,
            'poor': 0
        }


# Waste thresholds (not configurable)
WASTE_THRESHOLDS = {
    'critical': 80,   # >= 80% waste
    'high': 50,       # >= 50% waste
    'moderate': 30,   # >= 30% waste
    'low': 0          # < 30% waste
}

# Color mappings
UTILIZATION_COLORS = {
    'excellent': 'success',  # Green
    'good': 'info',         # Blue
    'moderate': 'warning',  # Yellow
    'poor': 'danger'        # Red
}

WASTE_COLORS = {
    'critical': 'danger',   # Red
    'high': 'warning',      # Yellow
    'moderate': 'info',     # Blue
    'low': 'success'        # Green
}


@register.simple_tag
def utilization_badge(value):
    """
    Returns a badge HTML with appropriate color based on utilization percentage.
    >100% = overallocated (red), High utilization = good (green), Low utilization = bad (red)
    Thresholds are read from plugin configuration.
    """
    if value is None:
        value = 0

    value = float(str(value))  # Handle SafeString

    # Overallocation gets red badge regardless of thresholds
    if value > 100:
        color = 'danger'
    else:
        # Get thresholds from config
        thresholds = get_utilization_thresholds()

        # Determine level based on thresholds
        if value >= thresholds['excellent']:
            level = 'excellent'
        elif value >= thresholds['good']:
            level = 'good'
        elif value >= thresholds['moderate']:
            level = 'moderate'
        else:
            level = 'poor'

        color = UTILIZATION_COLORS[level]

    formatted_value = "{:.1f}%".format(value)
    return format_html(
        '<span class="badge text-bg-{}">{}</span>',
        color, formatted_value
    )


@register.simple_tag
def waste_badge(value):
    """
    Returns a badge HTML with appropriate color based on waste percentage.
    High waste = bad (red), Low waste = good (green)
    """
    if value is None:
        value = 0

    value = float(str(value))  # Handle SafeString

    # Determine level based on thresholds
    if value >= WASTE_THRESHOLDS['critical']:
        level = 'critical'
    elif value >= WASTE_THRESHOLDS['high']:
        level = 'high'
    elif value >= WASTE_THRESHOLDS['moderate']:
        level = 'moderate'
    else:
        level = 'low'

    color = WASTE_COLORS[level]
    formatted_value = "{:.1f}%".format(value)
    return format_html(
        '<span class="badge text-bg-{}">{}</span>',
        color, formatted_value
    )


@register.simple_tag
def utilization_text_color(value):
    """
    Returns just the color class for utilization percentage.
    Useful for coloring text without a badge.
    Thresholds are read from plugin configuration.
    """
    if value is None:
        value = 0

    value = float(str(value))

    # Get thresholds from config
    thresholds = get_utilization_thresholds()

    if value >= thresholds['excellent']:
        return 'text-success'
    elif value >= thresholds['good']:
        return 'text-info'
    elif value >= thresholds['moderate']:
        return 'text-warning'
    else:
        return 'text-danger'


@register.simple_tag
def availability_color(value):
    """
    Returns color class based on available licenses.
    Negative = overallocated (danger), Zero = full (warning), Positive = available (success)
    """
    if value is None:
        value = 0

    value = float(str(value))

    if value < 0:
        return 'text-danger'  # Overallocated
    elif value == 0:
        return 'text-warning'  # Fully utilized
    else:
        return 'text-success'  # Available


@register.simple_tag
def renewal_status_badge(days_until_renewal):
    """
    Returns a badge for renewal status based on days remaining.
    """
    if days_until_renewal is None:
        return format_html('<span class="badge text-bg-secondary">No renewal date</span>')

    days = int(days_until_renewal)

    if days < 0:
        return format_html('<span class="badge text-bg-danger">Expired {} days ago</span>', abs(days))
    elif days <= 30:
        return format_html('<span class="badge text-bg-danger">Expires in {} days</span>', days)
    elif days <= 90:
        return format_html('<span class="badge text-bg-warning">Expires in {} days</span>', days)
    else:
        return format_html('<span class="badge text-bg-success">Expires in {} days</span>', days)


@register.simple_tag
def auto_renew_badge(value):
    """
    Returns a badge for auto-renewal status.
    """
    if value:
        return format_html('<span class="badge text-bg-info"><i class="mdi mdi-refresh-auto"></i> Auto-renew</span>')
    else:
        return format_html('<span class="badge text-bg-secondary">Manual renewal</span>')


@register.filter
def currency_format(value, currency='NOK'):
    """
    Formats currency with thousand separators using apostrophes.
    Example: 106996924.96 NOK -> 106'996'924.96 NOK
    """
    if value is None:
        return f"0.00 {currency}"

    try:
        # Convert to float to handle Decimal/string
        num_value = float(str(value))

        # Split into integer and decimal parts
        int_part = int(num_value)
        dec_part = num_value - int_part

        # Format integer part with apostrophe separators
        int_str = f"{int_part:,}".replace(',', "'")

        # Format decimal part (always 2 decimals)
        dec_str = f"{dec_part:.2f}".split('.')[1]

        return f"{int_str}.{dec_str} {currency}"
    except (ValueError, TypeError):
        return f"{value} {currency}"


@register.filter
def basename(value):
    """
    Returns the base filename from a file path.
    Example: 'uploads/invoices/2024/invoice.pdf' -> 'invoice.pdf'
    """
    if not value:
        return ''
    import os
    return os.path.basename(str(value))