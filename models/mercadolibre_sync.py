# -*- coding: utf-8 -*-
from odoo import models, api
import requests
import logging

_logger = logging.getLogger(__name__)

class MarketplaceMercadoLibreSync(models.TransientModel):
    _name = 'marketplace.mercadolibre.sync'
    _description = 'Sincronizador de Enlaces de Mercado Libre'

    @api.model
    def action_sync_urls(self):
        """Tarea programada para obtener los enlaces de Mercado Libre."""
        ml_app_id = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_app_id')
        ml_secret_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_secret_key')
        ml_access_token = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_access_token')
        ml_refresh_token = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_refresh_token')

        if not ml_app_id or not ml_secret_key:
            _logger.warning("Faltan credenciales de Mercado Libre (App ID o Secret Key).")
            return

        def _get_ml_token(grant_type, code_or_refresh):
            token_url = "https://api.mercadolibre.com/oauth/token"
            headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded'
            }
            data = {
                'grant_type': grant_type,
                'client_id': ml_app_id,
                'client_secret': ml_secret_key
            }
            if grant_type == 'refresh_token':
                data['refresh_token'] = code_or_refresh
                
            try:
                response = requests.post(token_url, headers=headers, data=data, timeout=15)
                if response.status_code == 200:
                    resp_json = response.json()
                    new_access = resp_json.get('access_token')
                    new_refresh = resp_json.get('refresh_token')
                    if new_access:
                        self.env['ir.config_parameter'].sudo().set_param('url_marketplace.ml_access_token', new_access)
                    if new_refresh:
                        self.env['ir.config_parameter'].sudo().set_param('url_marketplace.ml_refresh_token', new_refresh)
                    return new_access, new_refresh
                else:
                    _logger.error("Error obteniendo token ML: %s", response.text)
                    return None, None
            except Exception as e:
                _logger.error("Excepcion al conectar con API ML para tokens: %s", str(e))
                return None, None

        if not ml_access_token and ml_refresh_token:
            ml_access_token, ml_refresh_token = _get_ml_token('refresh_token', ml_refresh_token)

        if not ml_access_token:
            _logger.warning("No hay token de acceso válido para Mercado Libre y no se pudo refrescar.")
            return

        ml_headers = {
            'Authorization': f'Bearer {ml_access_token}',
            'Accept': 'application/json'
        }

        # 1. Obtener User ID (Seller ID)
        user_url = "https://api.mercadolibre.com/users/me"
        user_res = requests.get(user_url, headers=ml_headers, timeout=10)
        
        # Si da error de token, refrescamos e intentamos de nuevo
        if user_res.status_code in [401, 403] and ml_refresh_token:
            ml_access_token, ml_refresh_token = _get_ml_token('refresh_token', ml_refresh_token)
            if ml_access_token:
                ml_headers['Authorization'] = f'Bearer {ml_access_token}'
                user_res = requests.get(user_url, headers=ml_headers, timeout=10)
        
        if user_res.status_code != 200:
            _logger.error("Error obteniendo usuario ML: %s", user_res.text)
            return
            
        seller_id = user_res.json().get('id')
        if not seller_id:
            _logger.error("No se pudo obtener el Seller ID de Mercado Libre.")
            return

        # 2. Obtener lista completa de IDs de ítems del vendedor
        all_item_ids = []
        offset = 0
        limit = 50
        while True:
            search_url = f"https://api.mercadolibre.com/users/{seller_id}/items/search?limit={limit}&offset={offset}"
            search_res = requests.get(search_url, headers=ml_headers, timeout=15)
            if search_res.status_code == 200:
                data = search_res.json()
                results = data.get('results', [])
                all_item_ids.extend(results)
                
                paging = data.get('paging', {})
                total = paging.get('total', 0)
                if len(all_item_ids) >= total or not results:
                    break
                offset += limit
            else:
                _logger.error("Error buscando items de ML: %s", search_res.text)
                break

        if not all_item_ids:
            _logger.info("No se encontraron ítems en la cuenta de Mercado Libre.")
            return

        # Buscar o crear el marketplace en Odoo
        marketplace = self.env['marketplace.marketplace'].search([('name', 'ilike', 'mercado%libre')], limit=1)
        if not marketplace:
            marketplace = self.env['marketplace.marketplace'].search([('name', 'ilike', 'mercado')], limit=1)
        if not marketplace:
            marketplace = self.env['marketplace.marketplace'].create({
                'name': 'Mercado Libre',
                'sequence': 10
            })

        LinkModel = self.env['product.variant.marketplace']
        ProductModel = self.env['product.product']

        # 3. Consultar detalles de los ítems en bloques de 20 (límite de la API de ML)
        chunk_size = 20
        for i in range(0, len(all_item_ids), chunk_size):
            chunk = all_item_ids[i:i + chunk_size]
            ids_str = ",".join(chunk)
            items_url = f"https://api.mercadolibre.com/items?ids={ids_str}&attributes=id,title,permalink,seller_custom_field,attributes"
            items_res = requests.get(items_url, headers=ml_headers, timeout=20)
            
            if items_res.status_code == 200:
                items_data = items_res.json()
                for item_obj in items_data:
                    if item_obj.get('code') == 200:
                        body = item_obj.get('body', {})
                        item_id = body.get('id')
                        title = body.get('title')
                        permalink = body.get('permalink')
                        
                        # Buscar SKU (primero en seller_custom_field, sino en atributos SELLER_SKU)
                        sku = body.get('seller_custom_field')
                        if not sku:
                            attributes = body.get('attributes', [])
                            for attr in attributes:
                                if attr.get('id') == 'SELLER_SKU':
                                    sku = attr.get('value_name')
                                    break
                                    
                        if not sku:
                            continue  # No podemos enlazar si no hay SKU
                            
                        # Buscar producto en Odoo
                        product = ProductModel.search([('default_code', '=', sku)], limit=1)
                        if not product:
                            continue  # Si no existe en Odoo, lo saltamos
                            
                        # Revisar si ya existe el enlace
                        existing = LinkModel.search([
                            ('product_id', '=', product.id),
                            ('marketplace_id', '=', marketplace.id)
                        ], limit=1)
                        
                        if existing:
                            if existing.url != permalink or existing.marketplace_sku != sku or existing.marketplace_product_name != title:
                                existing.write({
                                    'url': permalink,
                                    'marketplace_sku': sku,
                                    'marketplace_product_name': title
                                })
                        else:
                            LinkModel.create({
                                'product_id': product.id,
                                'marketplace_id': marketplace.id,
                                'url': permalink,
                                'marketplace_sku': sku,
                                'marketplace_product_name': title
                            })
            else:
                _logger.error("Error consultando multiget en ML: %s", items_res.text)
