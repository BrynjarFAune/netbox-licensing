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

# Create the menu with proper navigation structure
menu = PluginMenu(
    label='License Management',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:netbox_licenses:dashboard',
                link_text='Dashboard'
            ),
        )),
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
        )),
    ),
    icon_class='mdi mdi-certificate'
)
