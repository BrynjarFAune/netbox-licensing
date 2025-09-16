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
    groups=(
        ('overview', (
            PluginMenuItem(
                link='plugins:netbox_licenses:dashboard',
                link_text='Dashboard'
            ),
        )),
        ('licenses', (
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
        ('reports', (
            PluginMenuItem(
                link='plugins:netbox_licenses:utilization_report',
                link_text='Utilization Report'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:vendor_utilization',
                link_text='Vendor Analysis'
            ),
        )),
        ('analytics', (
            PluginMenuItem(
                link='plugins:netbox_licenses:license_analytics',
                link_text='License Analytics'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:compliance_monitoring',
                link_text='Compliance Monitoring'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:cost_allocation',
                link_text='Cost Allocation'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:assigned_object_costs',
                link_text='Object Cost Attribution'
            ),
            PluginMenuItem(
                link='plugins:netbox_licenses:license_renewals',
                link_text='License Renewals'
            ),
        ))
    ),
    icon_class='mdi mdi-certificate'
)
