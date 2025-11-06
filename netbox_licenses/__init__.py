from netbox.plugins import PluginConfig

class LicenseManagementConfig(PluginConfig):
    name = 'netbox_licenses'  # Must match Python module name
    verbose_name = 'License Management'
    description = 'Comprehensive license management with utilization tracking and analytics'
    version = '0.2.0'
    author = 'Brynjar F. Aune'
    author_email = 'contact@example.com'
    base_url = 'licenses'
    required_settings = []

    def ready(self):
        """Import signals when app is ready"""
        super().ready()
        from . import signals  # Import signals at runtime, not during module load

    # Plugin-specific settings
    default_settings = {
        'auto_calculate_utilization': True,  # Automatically calculate license utilization
        'alert_threshold_percent': 90,       # Alert when utilization exceeds this percentage
        'show_utilization_badges': True,     # Display utilization status in UI
        'enable_cost_tracking': True,        # Track license costs and renewals
        'renewal_warning_days': 90,          # Days before renewal to show warnings
        'max_instances_per_license': 1000,   # Safety limit for license instances
        # Currency sync settings
        'currency_sync_enabled': True,       # Enable automatic currency rate syncing
        'currency_sync_interval': 86400,     # Sync interval in seconds (default: 24 hours)
        'currency_stale_days': 7,            # Days before rate is considered stale
    }

    # Cache settings for performance
    caching_config = {
        'timeout': 300,  # 5 minutes
        'cache_key': 'netbox_licenses',
    }

config = LicenseManagementConfig
