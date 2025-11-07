from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu

# Create buttons using proper PluginMenuButton class
license_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:license_add',
        title='Add License',
        icon_class='mdi mdi-plus-thick'
    ),
)

licenseinstance_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:licenseinstance_add',
        title='Add Instance',
        icon_class='mdi mdi-plus-thick'
    ),
)

licenserenewal_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:licenserenewal_add',
        title='Add Renewal',
        icon_class='mdi mdi-plus-thick'
    ),
)

currencyrate_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:currencyconversionrate_add_api',
        title='Add from API',
        icon_class='mdi mdi-cloud-download'
    ),
    PluginMenuButton(
        link='plugins:netbox_licenses:currencyconversionrate_add',
        title='Add Manually',
        icon_class='mdi mdi-pencil'
    ),
    PluginMenuButton(
        link='plugins:netbox_licenses:currencyconversionrate_bulk_sync',
        title='Sync All API Rates',
        icon_class='mdi mdi-sync'
    ),
)

# Create the menu with proper navigation structure
menu = PluginMenu(
    label='License Management',
    groups=(
        # ('Overview', (
        #     PluginMenuItem(
        #         link='plugins:netbox_licenses:dashboard',
        #         link_text='Dashboard'
        #     ),
        # )),
        ('Management', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_list',
                link_text='Licenses',
                buttons=license_buttons
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:licenseinstance_list',
                link_text='License Instances',
                buttons=licenseinstance_buttons
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:licenserenewal_list',
                link_text='License Renewals',
                buttons=licenserenewal_buttons
            ),
        )),
        ('Configuration', (
            PluginMenuItem(
                link='plugins:netbox_licenses:config',
                link_text='Plugin Settings'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:currencyconversionrate_list',
                link_text='Currency Rates',
                buttons=currencyrate_buttons
            ),
        )),
    ),
    icon_class='mdi mdi-certificate'
)
