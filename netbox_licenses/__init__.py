from netbox.plugins import PluginConfig

class NetBoxLicensesConfig(PluginConfig):
    name = 'netbox_licenses'  # Must match Python module name
    verbose_name = 'License Management'
    description = 'Comprehensive license management with utilization tracking and analytics'
    version = '0.2.0'
    author = 'Brynjar F. Aune'
    author_email = 'contact@example.com'
    base_url = 'licenses'
    required_settings = []
    
    # Plugin-specific settings
    default_settings = {
        'auto_calculate_utilization': True,  # Automatically calculate license utilization
        'alert_threshold_percent': 90,       # Alert when utilization exceeds this percentage
        'show_utilization_badges': True,     # Display utilization status in UI
        'enable_cost_tracking': True,        # Track license costs and renewals
        'renewal_warning_days': 90,          # Days before renewal to show warnings
        'max_instances_per_license': 1000,   # Safety limit for license instances
    }
    
    # Cache settings for performance
    caching_config = {
        'timeout': 300,  # 5 minutes
        'cache_key': 'netbox_licenses',
    }
    
    def ready(self):
        # Import signal handlers to ensure they're registered
        from . import signals

    @property
    def navigation(self):
        """Return the plugin's navigation menu"""
        from .navigation import menu
        return menu

config = NetBoxLicensesConfig
