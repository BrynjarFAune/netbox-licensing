from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu
from netbox.choices import ButtonColorChoices

license_buttons = [
    PluginMenuButton(
        link='plugins:netbox_licenses:license_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
    )
]

licenseinstance_buttons = [
    PluginMenuButton(
        link='plugins:netbox_licenses:licenseinstance_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
    )
]

menu = PluginMenu(
    label='licenses',
    groups=[
        ('licenses', [
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
        ]),
        ('reports', [
            PluginMenuItem(
                link='plugins:netbox_licenses:utilization_report',
                link_text='Utilization Report',
                icon_class='mdi mdi-chart-bar'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:vendor_utilization',
                link_text='Vendor Analysis',
                icon_class='mdi mdi-domain'
            ),
        ])
    ],
    icon_class='mdi mdi-certificate'
)
