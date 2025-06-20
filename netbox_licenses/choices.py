from utilities.choices import ChoiceSet

class LicenseStatusChoices(ChoiceSet):
    PENDING = 'pending'
    ACTIVE = 'active'
    WARNING = 'warning'
    EXPIRED = 'expired'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (ACTIVE, 'Active',),
        (WARNING, 'Warning'),
        (EXPIRED, 'Expired'),
    ]

    CSS_CLASSES = {
        PENDING: 'info',
        ACTIVE: 'success',
        WARNING: 'warning',
        EXPIRED: 'danger'
    }

