from utilities.choices import ChoiceSet

class CurrencyChoices(ChoiceSet):
    NOK = 'NOK'
    EUR = 'EUR'
    SEK = 'SEK'
    USD = 'USD'
    DKK = 'DKK'
    
    CHOICES = [
        (NOK, 'Norwegian Krone (NOK)'),
        (EUR, 'Euro (EUR)'),
        (SEK, 'Swedish Krona (SEK)'),
        (USD, 'US Dollar (USD)'),
        (DKK, 'Danish Krone (DKK)'),
    ]

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

