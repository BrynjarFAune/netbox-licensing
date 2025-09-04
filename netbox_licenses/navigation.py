from netbox.plugins import PluginMenuItem, PluginMenu

# Minimal test navigation - single menu item to isolate issue
menu = PluginMenu(
    label='Licenses',
    groups=(
        ('Test', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_list',
                link_text='Licenses'
            ),
        )),
    ),
    icon_class='mdi mdi-certificate'
)
