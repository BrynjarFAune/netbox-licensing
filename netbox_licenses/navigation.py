from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu

# Create buttons using proper PluginMenuButton class
protected_resource_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:license_add',
        title='Add License',
        icon_class='mdi mdi-plus-thick'
    ),
)

# Create the menu with proper navigation structure
menu = PluginMenu(
    label='License Control',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_list',
                link_text='Licenses'
            ),
        )),
        ('Management', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_list',
                link_text='License Management',
                buttons=protected_resource_buttons
            ),
        )),
    ),
    icon_class='mdi mdi-shield-lock'
)
