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

licenseperiod_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:licenseperiod_add',
        title='Add Period',
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
        link='plugins:netbox_licenses:currencyconversionrate_bulk_sync',
        title='Sync All API Rates',
        icon_class='mdi mdi-sync'
    ),
)

# Create the menu with proper navigation structure
menu = PluginMenu(
    label='License Management',
    groups=(
        ('Management', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_list',
                link_text='Licenses',
                permissions=['netbox_licenses.view_license'],
                buttons=license_buttons
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:licenseinstance_list',
                link_text='License Instances',
                permissions=['netbox_licenses.view_licenseinstance'],
                buttons=licenseinstance_buttons
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:licenseperiod_list',
                link_text='License Periods',
                permissions=['netbox_licenses.view_licenseperiod'],
                buttons=licenseperiod_buttons
            ),
        )),
        ('Configuration', (
            # PluginMenuItem(
            #     link='plugins:netbox_licenses:config',
            #     link_text='Plugin Settings'
            # ),
            PluginMenuItem(
                link='plugins:netbox_licenses:currencyconversionrate_list',
                link_text='Currency Rates',
                permissions=['netbox_licenses.view_currencyconversionrate'],
                buttons=currencyrate_buttons
            ),
        )),
    ),
    icon_class='mdi mdi-certificate'
)
