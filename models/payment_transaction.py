# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import json
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    plutu_mobile_number = fields.Char(string="Mobile Number", help="Customer's mobile number for Sadad payment.")
    plutu_birth_year = fields.Char(string="Birth Year", help="Customer's birth year for Sadad payment.")
    plutu_process_id = fields.Char(string="Process ID", readonly=True, help="Process ID returned by Sadad API after sending OTP.")
    otp_code = fields.Char(string="OTP Code", help="One-Time Password sent to the customer’s phone.")

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paylink-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'plutu':
            return res
        
        _logger.info("Payment Method Name: %s", self.payment_method_id.name)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        payload = {
                'amount': str(self.amount),
                'invoice_no': self.reference,
                'return_url': base_url + '/payment/plutu/return',
                'mobile_number': self.partner_id.phone,
                'callback_url': base_url + '/payment/plutu/webhook',
                'lang': 'en'
            }
        payment_link_data = self.provider_id._plutu_make_request(f'transaction/{self.payment_method_id.code}/confirm', payload=payload)
        rendering_values = {
            'api_url': payment_link_data['result']['redirect_url'],
        }
        return rendering_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Paylink data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data were received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'plutu' or len(tx) == 1:
            return tx

        reference = notification_data.get('invoice_no')
        if not reference:
            raise ValidationError("Plutu: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'plutu')])
        if not tx:
            raise ValidationError(
                "Plutu: " + _("No transaction found matching reference %s.", reference)
            )
        return tx
    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Paylink data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data were received.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'plutu':
            return

        if True:
            if notification_data.get('callback'):
                if notification_data.get('approved'):
                    self._set_done()
                    _logger.info("Plutu: Payment approved for transaction %s.", self.reference)
                elif notification_data.get('canceled'):
                    self._set_canceled()
                    _logger.info("Plutu: Payment canceled for transaction %s.", self.reference)
            else:
                self._set_pending()
    def _handle_notification_data(self, provider_code, notification_data):
        """ Override to handle notification data specific to Plutu. """
        super()._handle_notification_data(provider_code, notification_data)
        
        if provider_code != 'plutu':
            return
        if notification_data.get('gateway') == 'localbankcards' or notification_data.get('gateway') == 'tlync':
            if notification_data.get('approved'):
                self._set_done()
                _logger.info("Plutu: Payment approved for transaction %s.", self.reference)
            elif notification_data.get('canceled'):
                self._set_canceled()
                _logger.info("Plutu: Payment canceled for transaction %s.", self.reference)
