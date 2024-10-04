# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import logging
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.payment_plutu import const

from werkzeug.exceptions import Forbidden


_logger = logging.getLogger(__name__)
import hashlib
import hmac



class PaylinkController(http.Controller):
    _return_url = '/payment/plutu/return'
    _webhook_url = '/payment/plutu/webhook'
    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def plutu_return_from_payment(self, **data):
        """ Process the notification data sent by Plutu after payment. """
        _logger.info("Handling redirection from Plutu with data:\n%s", pprint.pformat(data))

        self._verify_plutu_callback_hash(data, self.plutu_secret_key)
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'plutu', data
        )
        tx_sudo._handle_notification_data('plutu', data)
        return request.redirect('/payment/status')
    @http.route(_webhook_url, type='http', methods=['POST'], auth='public',csrf=False)
    def plutu_payment_webhook(self):
        """ Process the notification data sent by Paylink to the webhook.
        :return: An empty string to acknowledge the notification.
        :rtype: str
        """
        data = request.get_json_data()
        _logger.info("Notification received from Paylink with data:\n%s", pprint.pformat(data))
        self._verify_plutu_callback_hash(data, self.plutu_secret_key,'callback')
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'plutu', data
        )
        tx_sudo._handle_notification_data('plutu', data)
        
        return request.make_json_response('')


    @staticmethod
    def _verify_plutu_callback_hash(parameters, secret_key,key='return'):
        """
        Verifies the callback hash from Plutu.

        :param parameters: dict - The parameters received in the callback.
        :param secret_key: str - The secret key used to generate the hash.
        :raises Exception: If the hash verification fails.
        """
        # Validate the secret key
        if not secret_key.strip():
            raise Exception('Secret key is not configured')

        # Define the callback parameters to be included in the hash calculation
        if key == 'callback':
            callback_parameters = ['gateway', 'approved', 'amount','invoice_no','canceled','payment_method', 'transaction_id']
        else:
            callback_parameters = ['gateway', 'approved', 'canceled', 'invoice_no', 'amount', 'transaction_id']

        # Get the data to hash by filtering and concatenating the relevant parameters
        data = '&'.join(f"{key}={parameters[key]}" for key in callback_parameters if key in parameters)

        # Retrieve the hash sent in the callback
        hash_from_callback = parameters.get('hashed').upper()
        if not hash_from_callback:
            _logger.warning("received notification with missing signature")
            raise Forbidden()
        
        # Generate the hash using HMAC-SHA256
        generated_hash = hmac.new(secret_key.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest().upper()

        # Compare the generated hash with the hash from the callback
        if not hash_from_callback or not generated_hash or not hmac.compare_digest(generated_hash, hash_from_callback):
            _logger.warning("received notification with invalid signature")
            raise Forbidden()

