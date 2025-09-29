from utilities.choices import ChoiceSet

class PaymentMethodChoices(ChoiceSet):
    INVOICE = 'invoice'
    CARD_AUTO = 'card_auto'
    CARD_MANUAL = 'card_manual'
    BANK_TRANSFER = 'bank_transfer'
    PURCHASE_ORDER = 'purchase_order'
    PREPAID = 'prepaid'
    FREE_TRIAL = 'free_trial'

    CHOICES = [
        (INVOICE, 'Invoice (Manual Approval & Payment)'),
        (CARD_AUTO, 'Credit Card (Auto-Charge)'),
        (CARD_MANUAL, 'Credit Card (Manual Payment)'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (PURCHASE_ORDER, 'Purchase Order'),
        (PREPAID, 'Prepaid'),
        (FREE_TRIAL, 'Free/Trial'),
    ]

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

