## netbox-licenses

Manage licenses in netbox

dev section:

1. prep
setup root dir (netbox-licenses), sub-root dir (netbox_licenses), create __init__.py

2. mount
copy __init__.py dir into docker container
include plugin name in configurations/plaugins.py

3. create models
create models.py in sub-root folder and create any models you want

X. migrate db anytime you want changes in the models to be reflected
build and run containers
enter netbox container and run "python3 manage.py makemigrations <plugin-name>" and then "python3 manage.py migrate"
this will create a migration file for the db and migrate your db to include the new models.

5. create tables
create tables.py in sub-root folder and create tables for all the models you want toables for
a table is the list of all instances of the model you would see in the UI

6. create forms
create forms.py in sub-root folder and create forms for modifying the models in the ui.

7. Create views and urls
create files views.py and urls.py in the sub-root dir and create views and urls.
the urls will give you a way to access the views in the UI, and the views would contain things like the list of all instances of your model, individual pages, the creation / editing forms. though you can't create anything yet in the ui, and you need to manually type the url.

8. Create template files
in sub-root dir, create folder templates/<plugin-name>/ and create a <model>.html for each of your models

9. Create menu items
in sub-root dir, create a navigation.py file, and set menu_items = (PluginMenuItem(link, link_text),...)
PluginMenuItem being an item int the Plugins page, set one for each view you want a link to from the sidebar

10. Enable filtering (Optional)
if you want to enable filtering on your models, create a filtersets.py in the sub-root dir, create some filters and potentially forms for them, import it into views.py and declare 'filterset = filtersets.<MyModelFilterSet>' on the list-view


