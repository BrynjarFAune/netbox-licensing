from setuptools import find_packages, setup

setup(
    name='netbox_licenses',
    version='0.1',
    description='Manage licenses in NetBox',
    install_requires=[],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'netbox.plugins': [
            'netbox_licenses = netbox_licenses',
        ],
        'netbox.plugin_template_extensions': [
            'netbox_licenses = netbox_licenses.template_content',
        ]
    }
)
