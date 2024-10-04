API_VERSION = '2024-01-01' 
DEFAULT_PAYMENT_METHODS_CODES = [
    # Brand payment methods.
    'card',
    'mada',
    'visa',
    'mastercard',
    'amex',
    'mada',
]
STATUS_MAPPING = {
    'draft': ('requires_confirmation', 'requires_action'),
    'pending': ('processing', 'pending'),
    'authorized': ('requires_capture',),
    'done': ('succeeded',),
    'cancel': ('canceled',),
    'error': ('requires_payment_method', 'failed',),
}
SUPPORTED_CURRENCIES = {
    'USD',
    'LYD'
}
PAYMENT_METHODS_MAPPING = {
    'bank_transfer': 'banktransfer',
}


