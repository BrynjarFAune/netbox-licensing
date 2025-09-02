from netbox.plugins import PluginMenuItem

# Minimal test navigation - should appear in "Plugins" menu
menu_items = (
    PluginMenuItem(
        link='plugins:netbox_licenses:license_list',
        link_text='Licenses'
    ),
)
