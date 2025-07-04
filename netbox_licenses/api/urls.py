from netbox.api.routers import NetBoxRouter
from . import views

app_name = 'netbox_license'

router = NetBoxRouter()
router.register('licenses', views.LicenseViewSet)
router.register('licenseinstances', views.LicenseInstanceViewSet)

urlpatterns = router.urls
