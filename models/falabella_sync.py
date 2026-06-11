# -*- coding: utf-8 -*-
from odoo import models, fields, api
import hmac
import hashlib
import urllib.parse
import requests
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

class FalabellaSync(models.AbstractModel):
    _name = 'marketplace.falabella.sync'
    _description = 'Sincronización con Falabella'

    @api.model
    def sync_falabella_urls(self):
        # Obtain Falabella marketplace record
        falabella = self.env['marketplace.marketplace'].search([('name', 'ilike', 'Falabella')], limit=1)
        if not falabella:
            _logger.warning("No marketplace found with name 'Falabella'")
            return

        user_id = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.falabella_api_user_id')
        api_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.falabella_api_key')

        if not user_id or not api_key:
            _logger.warning("Falabella API credentials are not configured in system parameters.")
            return

        # Find products that don't have a URL for Falabella
        # This includes products that don't have a marketplace link for Falabella at all, 
        # or products that have a link but the URL is missing.
        # It's better to iterate over products and find the missing ones.
        products = self.env['product.product'].search([('active', '=', True)])
        
        # Build list of SKUs to search
        skus_to_search = []
        products_map = {}
        for product in products:
            if not product.default_code:
                continue
            
            # Check if it already has a Falabella link with a URL
            has_valid_link = False
            for link in product.x_marketplace_ids:
                if link.marketplace_id.id == falabella.id and link.url:
                    has_valid_link = True
                    break
            
            if not has_valid_link:
                skus_to_search.append(product.default_code)
                products_map[product.default_code] = product

        if not skus_to_search:
            _logger.info("All products already have Falabella URLs or don't have SKUs.")
            return

        # The Seller Center API might have limits on the Search parameter or pagination
        # Usually it's better to search one by one, or if there's a batch way.
        # Since it's a cron, let's query one by one with a small limit per run.
        max_queries = 50
        for sku in skus_to_search[:max_queries]:
            self._fetch_and_update_url(sku, products_map[sku], falabella, user_id, api_key)

    def _fetch_and_update_url(self, sku, product, falabella, user_id, api_key):
        params = {
            'Action': 'GetProducts',
            'Format': 'JSON',
            'Timestamp': datetime.utcnow().isoformat() + '+00:00',
            'UserID': user_id,
            'Version': '1.0',
            'Search': sku
        }

        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        signature = hmac.new(
            api_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        url = f'https://sellercenter-api.falabella.com/?{query_string}&Signature={signature}'

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                success_resp = data.get('SuccessResponse')
                if not success_resp:
                    return

                body = success_resp.get('Body')
                if not body:
                    return
                    
                products_node = body.get('Products')
                if not products_node or isinstance(products_node, str):
                    return

                products = products_node.get('Product')
                
                if products:
                    # Products could be a list or a dict
                    if isinstance(products, dict):
                        products = [products]
                        
                    for prod in products:
                        if prod.get('SellerSku') == sku:
                            product_url = prod.get('Url')
                            if product_url:
                                self._update_product_link(product, falabella, product_url)
                                _logger.info(f"Updated Falabella URL for SKU {sku}")
                            break
        except Exception as e:
            _logger.error(f"Error connecting to Falabella API for SKU {sku}: {e}")

    def _update_product_link(self, product, falabella, url):
        link = product.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == falabella.id)
        if link:
            link[0].url = url
        else:
            self.env['product.variant.marketplace'].create({
                'product_id': product.id,
                'marketplace_id': falabella.id,
                'url': url
            })

