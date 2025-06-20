from netbox.plugins import PluginConfig

class NetBoxLicensesConfig(PluginConfig):
    name = 'netbox_licenses'
    verbose_name = 'Licenses'
    description = 'License management in NetBox'
    version = '0.1'
    author = 'Brynjar F Aune'
    author_email = 'BrynjarFAune@gmail.com'
    base_url = 'licenses'

config = NetBoxLicensesConfig
