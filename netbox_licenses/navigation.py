from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu
from netbox.choices import ButtonColorChoices

license_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:license_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
    ),
)

licenseinstance_buttons = (
    PluginMenuButton(
        link='plugins:netbox_licenses:licenseinstance_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
    ),
)

menu = PluginMenu(
    label='Licenses',
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
