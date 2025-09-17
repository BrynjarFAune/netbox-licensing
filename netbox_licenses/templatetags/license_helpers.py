from django import template
from django.utils.html import format_html

register = template.Library()

# Centralized threshold configuration
UTILIZATION_THRESHOLDS = {
    'excellent': 90,  # >= 90% utilization
    'good': 70,       # >= 70% utilization
    'moderate': 50,   # >= 50% utilization
    'poor': 0         # < 50% utilization
}

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
    High utilization = good (green), Low utilization = bad (red)
    """
    if value is None:
        value = 0

    value = float(str(value))  # Handle SafeString

    # Determine level based on thresholds
    if value >= UTILIZATION_THRESHOLDS['excellent']:
        level = 'excellent'
    elif value >= UTILIZATION_THRESHOLDS['good']:
        level = 'good'
    elif value >= UTILIZATION_THRESHOLDS['moderate']:
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
    """
    if value is None:
        value = 0

    value = float(str(value))

    if value >= UTILIZATION_THRESHOLDS['excellent']:
        return 'text-success'
    elif value >= UTILIZATION_THRESHOLDS['good']:
        return 'text-info'
    elif value >= UTILIZATION_THRESHOLDS['moderate']:
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