# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import requests
from werkzeug.urls import url_join
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.payment_plutu import const
import json
_logger = logging.getLogger(__name__)



class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    name = fields.Char(string="Name", required=True, translate=True, readonly=True)
    state = fields.Selection(
        string="Status",
        help="In test mode, a fake payment is processed through a test payment interface.\n"
             "This mode is advised when setting up the provider.",
        selection=[('test', "Test Environment"), ('enabled', "Production Environment"), ('disabled', "Disabled")],
        default='disabled', required=True, copy=False)

    code = fields.Selection(
        selection_add=[('plutu', "Plutu")], ondelete={'plutu': 'set default'}
    )
    minimum_amount = fields.Monetary(
        string="Minimum Amount",
        help="The minimum payment amount that this payment provider is available. ",
        currency_field='main_currency_id', default=5, readonly=True)
    website_id = fields.Many2one(
        "website",
        check_company=True,
        ondelete="restrict",
        required_if_provider='plutu'
    )
    plutu_api_key = fields.Char(string="Plutu API Key", required_if_provider='plutu', groups='base.group_system')
    plutu_secret_key = fields.Char(string="Plutu Secret Key", required_if_provider='plutu', groups='base.group_system')
    plutu_access_token = fields.Char(string="Plutu Access Token", required_if_provider='plutu', groups='base.group_system')


    # === COMPUTE METHODS ===#


    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'plutu').update({
            'support_tokenization': True,
        })

    # === BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, **kwargs):
        """ Override of `payment` to filter out paylink providers for validation operations. """
        providers = super()._get_compatible_providers(*args, is_validation=is_validation, **kwargs)

        if is_validation:
            providers = providers.filtered(lambda p: p.code != 'plutu')

        return providers
    
    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'plutu':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _plutu_make_request(self, endpoint, payload=None, method='POST'):
        """ Make a request to Plutu API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :param str method: The HTTP method of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs.
        """
        self.ensure_one()
        url = url_join('https://api.plutus.ly/api/v1/', endpoint)
        headers = {
            'X-API-KEY': self.plutu_api_key,
            'Authorization': f'Bearer {self.plutu_access_token}'
        }
        try:
            if method == 'GET':
                response = requests.get(url, params=payload, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                _logger.exception(
                    "Invalid API request at %s with data:\n%s", url, pprint.pformat(payload),
                )
                _logger.exception(response.text)
                raise ValidationError(response.text)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Unable to reach endpoint at %s", url)
            raise ValidationError(
                "Plutu: " + _("Could not establish the connection to the API.")
            )
        _logger.debug("Request to Plutu API at %s succeeded", url)
        _logger.info(response.json())
        return response.json()

    def _product_description(self, order_ref):
        sale_order = self.env["sale.order"].search([("name", "=", order_ref)])
        res = []
        if sale_order:
            for line in sale_order.order_line:
                dic = {
                          "description": line.name,
                          "price": line.price_subtotal,
                          "qty": line.product_uom_qty,
                          "title": line.product_template_id.name
                        }
                res.append(dic)
        return res

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'plutu':
            return default_codes

        return const.DEFAULT_PAYMENT_METHODS_CODES