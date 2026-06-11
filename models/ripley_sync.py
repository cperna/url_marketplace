# -*- coding: utf-8 -*-
from odoo import models, api
import requests
import logging
import re

_logger = logging.getLogger(__name__)

class MarketplaceRipleySync(models.TransientModel):
    _name = 'marketplace.ripley.sync'
    _description = 'Sincronizador de Enlaces de Ripley'

    def _slugify(self, text):
        import unicodedata
        if not text:
            return ''
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')

    @api.model
    def action_sync_urls(self):
        """Tarea programada para construir los enlaces de Ripley desde Mirakl API."""
        ripley_api_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ripley_api_key')
        ripley_shop_id = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ripley_shop_id')

        if not ripley_api_key:
            _logger.warning("Falta la API Key de Ripley (Mirakl).")
            return

        headers = {
            'Authorization': ripley_api_key,
            'Accept': 'application/json'
        }

        # Buscar o crear el marketplace en Odoo
        marketplace = self.env['marketplace.marketplace'].search([('name', 'ilike', 'ripley')], limit=1)
        if not marketplace:
            marketplace = self.env['marketplace.marketplace'].create({
                'name': 'Ripley',
                'sequence': 20
            })

        LinkModel = self.env['product.variant.marketplace']
        ProductModel = self.env['product.product']

        offset = 0
        max_records = 100
        
        while True:
            url = f"https://ripleyperu-prod.mirakl.net/api/offers?max={max_records}&offset={offset}"
            if ripley_shop_id:
                url += f"&shop_id={ripley_shop_id}"
                
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                data = res.json()
                offers = data.get('offers', [])
                if not offers:
                    break
                
                for offer in offers:
                    shop_sku = offer.get('shop_sku') # Odoo internal reference (SKU)
                    product_title = offer.get('product_title')
                    product_sku = offer.get('product_sku') # Ripley SKU (e.g. PMP...)
                    
                    if not shop_sku or not product_sku or not product_title:
                        continue
                        
                    # Buscar producto en Odoo usando la referencia interna
                    product = ProductModel.search([('default_code', '=', shop_sku)], limit=1)
                    if not product:
                        continue
                    
                    # Construir la URL de Ripley Perú
                    slug = self._slugify(product_title)
                    sku_lower = product_sku.lower()
                    
                    # Ripley Perú format: https://simple.ripley.com.pe/slug-skup
                    # Si el SKU ya termina en 'p', no se la añadimos de nuevo por si acaso, aunque normalmente el 'p' es estático al final de la URL
                    if sku_lower.endswith('p'):
                        constructed_url = f"https://simple.ripley.com.pe/{slug}-{sku_lower}"
                    else:
                        constructed_url = f"https://simple.ripley.com.pe/{slug}-{sku_lower}p"

                    existing = LinkModel.search([
                        ('product_id', '=', product.id),
                        ('marketplace_id', '=', marketplace.id)
                    ], limit=1)
                    
                    if existing:
                        if existing.url != constructed_url or existing.marketplace_sku != product_sku or existing.marketplace_product_name != product_title:
                            existing.write({
                                'url': constructed_url,
                                'marketplace_sku': product_sku,
                                'marketplace_product_name': product_title
                            })
                    else:
                        LinkModel.create({
                            'product_id': product.id,
                            'marketplace_id': marketplace.id,
                            'url': constructed_url,
                            'marketplace_sku': product_sku,
                            'marketplace_product_name': product_title
                        })
                
                if len(offers) < max_records:
                    break
                offset += max_records
            else:
                _logger.error("Error API Ripley Mirakl URL Sync: %s - %s", res.status_code, res.text)
                break
