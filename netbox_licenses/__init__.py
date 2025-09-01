from netbox.plugins import PluginConfig

class NetBoxLicensesConfig(PluginConfig):
    name = 'netbox_licenses'
    verbose_name = 'Licenses'
    description = 'License management in NetBox'
    version = '0.2'  # Updated for enhancements
    author = 'Brynjar F Aune'
    author_email = 'BrynjarFAune@gmail.com'
    base_url = 'licenses'
    
    # Explicitly define navigation menu
    navigation = 'navigation.menu'
    
    def ready(self):
        # Import signal handlers to ensure they're registered
        from . import signals

config = NetBoxLicensesConfig
