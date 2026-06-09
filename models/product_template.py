# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MarketplaceMarketplace(models.Model):
    _name = 'marketplace.marketplace'
    _description = 'Plataforma de Marketplace'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre del Marketplace',
        required=True,
        translate=True,
        help='Nombre comercial de la plataforma (ej. MercadoLibre, Amazon, AliExpress)'
    )
    logo = fields.Image(
        string='Logotipo',
        max_width=256,
        max_height=256,
        help='Imagen o logotipo oficial de la plataforma'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización de los marketplaces'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Permite archivar/desactivar un marketplace sin borrar sus registros históricos'
    )

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([('name', '=ilike', record.name), ('id', '!=', record.id)]) > 0:
                raise models.ValidationError(f"El marketplace '{record.name}' ya existe. No se permiten nombres duplicados.")

    @api.model
    def _clean_duplicate_marketplaces(self):
        """Fusiona los marketplaces duplicados conservando el primero y eliminando el resto."""
        self.env.cr.execute("SELECT name FROM marketplace_marketplace GROUP BY name HAVING count(*) > 1")
        duplicates = self.env.cr.fetchall()
        for dup in duplicates:
            name = dup[0]
            records = self.search([('name', '=', name)], order='id asc')
            keep = records[0]
            for remove in records[1:]:
                links = self.env['product.variant.marketplace'].search([('marketplace_id', '=', remove.id)])
                for link in links:
                    existing = self.env['product.variant.marketplace'].search([
                        ('marketplace_id', '=', keep.id), 
                        ('product_id', '=', link.product_id.id)
                    ])
                    if existing:
                        link.unlink()
                    else:
                        link.marketplace_id = keep.id
                remove.unlink()


class ProductVariantMarketplace(models.Model):
    _name = 'product.variant.marketplace'
    _description = 'Enlace de Variante a Marketplace'
    _order = 'marketplace_id'

    # Campo legacy (a ser removido en el futuro)
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto (Legacy)'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Variante de Producto',
        required=False, # False temporalmente para permitir migración
        ondelete='cascade',
        index=True
    )
    marketplace_id = fields.Many2one(
        'marketplace.marketplace',
        string='Marketplace',
        required=True,
        ondelete='restrict',
        index=True
    )
    marketplace_logo = fields.Image(
        related='marketplace_id.logo',
        string='Logo',
        readonly=True
    )
    url = fields.Char(
        string='URL de Compra',
        required=False,
        help='Enlace directo a la variante publicada en este marketplace'
    )
    marketplace_price = fields.Float(
        string='Precio en Marketplace',
        help='Último precio obtenido desde la plataforma del marketplace',
        readonly=True
    )
    marketplace_stock = fields.Integer(
        string='Stock en Marketplace',
        default=0,
        help="Inventario extraído desde la plataforma (Mercado Libre, Falabella, etc.)",
        readonly=True
    )
    marketplace_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda del Marketplace',
        readonly=True
    )
    last_price_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )

    _sql_constraints = [
        ('uniq_product_marketplace', 'unique(product_id, marketplace_id)', '¡Ya existe un enlace para este marketplace en esta variante!')
    ]

    @api.model
    def action_sync_marketplace_prices(self):
        """Tarea programada para sincronizar los precios de los marketplaces soportados."""
        import requests
        import re
        from datetime import datetime

        # Actualmente soportamos Mercado Libre
        ml_records = self.search([('url', '!=', False)])
        
        # Diccionario para mapear códigos de moneda de ML a Odoo
        currency_map = {
            'PEN': 'PEN',
            'USD': 'USD',
            'ARS': 'ARS',
            'CLP': 'CLP',
            'COP': 'COP',
            'MXN': 'MXN'
        }
        
        import logging
        _logger = logging.getLogger(__name__)

        # Configuración de Mercado Libre API
        ml_app_id = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_app_id')
        ml_secret_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_secret_key')
        ml_redirect_uri = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_redirect_uri')
        ml_auth_code = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_auth_code')
        ml_access_token = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_access_token')
        ml_refresh_token = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ml_refresh_token')

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
            if grant_type == 'authorization_code':
                data['code'] = code_or_refresh
                data['redirect_uri'] = ml_redirect_uri
            else:
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

        # Intento inicial si hay auth_code y no token
        if ml_app_id and ml_secret_key and ml_auth_code and not ml_access_token:
            ml_access_token, ml_refresh_token = _get_ml_token('authorization_code', ml_auth_code)
            # Limpiar auth code para evitar reusarlo ya que expirará
            self.env['ir.config_parameter'].sudo().set_param('url_marketplace.ml_auth_code', '')
            
        ml_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'
        }
        if ml_access_token:
            ml_headers['Authorization'] = f'Bearer {ml_access_token}'

        # Configuración de Falabella API
        falabella_user = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.falabella_api_user_id')
        falabella_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.falabella_api_key')

        import urllib.parse
        import hmac
        import hashlib
        from datetime import timezone

        def get_falabella_url(action, user_id, api_key, extra_params=None):
            params = {
                'Action': action,
                'Format': 'JSON',
                'Timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'UserID': user_id,
                'Version': '1.0'
            }
            if extra_params:
                params.update(extra_params)
            
            # Ordenar y codificar según RFC 3986
            sorted_params = sorted(params.items())
            encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
            
            # Generar firma HMAC-SHA256
            signature = hmac.new(
                api_key.encode('utf-8'),
                encoded_params.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return f"https://sellercenter-api.falabella.com/?{encoded_params}&Signature={signature}"

        for record in ml_records:
            if not record.url:
                continue
                
            # Validar si es MercadoLibre
            if 'mercadolibre.com' in record.url.lower():
                # Extraer el ID. Formatos comunes: /MPE-1042551190- o /MPE1042551190
                match = re.search(r'/(M[A-Z]{2})-?(\d+)', record.url)
                if match:
                    site_id = match.group(1)
                    item_number = match.group(2)
                    item_id = f"{site_id}{item_number}"
                    
                    try:
                        api_url = f"https://api.mercadolibre.com/items/{item_id}"
                        response = requests.get(api_url, headers=ml_headers, timeout=10)
                        
                        # Manejo de expiración o error 401/403 con ML
                        if response.status_code in [401, 403] and ml_refresh_token:
                            _logger.info("Refrescando token de Mercado Libre...")
                            new_access, new_refresh = _get_ml_token('refresh_token', ml_refresh_token)
                            if new_access:
                                ml_access_token = new_access
                                ml_refresh_token = new_refresh
                                ml_headers['Authorization'] = f'Bearer {ml_access_token}'
                                response = requests.get(api_url, headers=ml_headers, timeout=10)
                                
                        if response.status_code == 200:
                            data = response.json()
                            price = data.get('price')
                            ml_currency = data.get('currency_id')
                            
                            if price is not None:
                                record.marketplace_price = float(price)
                                record.marketplace_stock = int(data.get('available_quantity', 0))
                                record.last_price_sync = datetime.now()
                                
                                # Buscar moneda
                                odoo_currency_code = currency_map.get(ml_currency, ml_currency)
                                currency = self.env['res.currency'].search([('name', '=', odoo_currency_code)], limit=1)
                                if currency:
                                    record.marketplace_currency_id = currency.id
                        else:
                            _logger.warning("No se pudo sincronizar ML para %s. Estado: %s - Respuesta: %s", item_id, response.status_code, response.text)
                    except Exception as e:
                        _logger.error("Error sincronizando precio para %s: %s", item_id, str(e))

        # Sincronización de Falabella
        if falabella_user and falabella_key:
            falabella_records = self.search([('url', '!=', False)])
            falabella_links = [r for r in falabella_records if 'falabella.com' in r.url.lower()]
            
            if falabella_links:
                try:
                    limit = 1000
                    offset = 0
                    all_products = []
                    
                    # Extraer todos los productos en páginas de 1000 (suficiente para la mayoría)
                    url = get_falabella_url('GetProducts', falabella_user, falabella_key, {'Limit': str(limit), 'Offset': str(offset)})
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        body = data.get('SuccessResponse', {}).get('Body', {})
                        products_data = body.get('Products', {}).get('Product', [])
                        
                        # Si es un solo producto, la API devuelve un diccionario en vez de una lista
                        if isinstance(products_data, dict):
                            products_data = [products_data]
                            
                        # Mapear precios
                        price_map = {}
                        for p in products_data:
                            sku = p.get('SellerSku')
                            # The price is usually in BusinessUnits.BusinessUnit
                            business_units = p.get('BusinessUnits', {}).get('BusinessUnit', [])
                            if isinstance(business_units, dict):
                                business_units = [business_units]
                            
                            price = 0.0
                            sale_price = 0.0
                            
                            stock = 0
                            
                            for bu in business_units:
                                if bu.get('BusinessUnit') == 'Falabella':
                                    price = float(bu.get('Price') or 0.0)
                                    sale_price = float(bu.get('SpecialPrice') or 0.0)
                                    stock = int(bu.get('Stock') or 0)
                                    break
                            
                            if not price and not sale_price:
                                price = float(p.get('Price') or 0.0)
                                sale_price = float(p.get('SalePrice') or 0.0)
                                
                            try:
                                final_price = sale_price if sale_price > 0 else price
                                if final_price > 0 and sku:
                                    price_map[sku] = {
                                        'price': final_price,
                                        'stock': stock
                                    }
                            except (ValueError, TypeError):
                                pass
                        
                        # Moneda de Falabella Perú por defecto
                        pen_currency = self.env['res.currency'].search([('name', '=', 'PEN')], limit=1)
                        
                        for record in falabella_links:
                            # El SellerSku es la referencia interna de la variante
                            variant_sku = record.product_id.default_code
                            if variant_sku and variant_sku in price_map:
                                record.marketplace_price = price_map[variant_sku]['price']
                                record.marketplace_stock = price_map[variant_sku]['stock']
                                record.last_price_sync = datetime.now()
                                if pen_currency:
                                    record.marketplace_currency_id = pen_currency.id

                except Exception as e:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error("Error conectando a API Falabella: %s", str(e))

        # Sincronización de Ripley (Mirakl)
        ripley_api_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ripley_api_key')
        ripley_shop_id = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.ripley_shop_id')
        
        if ripley_api_key:
            ripley_records = self.search([('url', '!=', False)])
            ripley_links = [r for r in ripley_records if r.marketplace_id.name and 'ripley' in r.marketplace_id.name.lower()]
            
            if ripley_links:
                try:
                    headers = {
                        'Authorization': ripley_api_key,
                        'Accept': 'application/json'
                    }
                    if ripley_shop_id:
                        headers['Shop-Id'] = ripley_shop_id
                        
                    price_map = {}
                    offset = 0
                    max_records = 100
                    
                    while True:
                        url = f"https://ripley-prod.mirakl.net/api/offers?max={max_records}&offset={offset}"
                        res = requests.get(url, headers=headers, timeout=20)
                        if res.status_code == 200:
                            data = res.json()
                            offers = data.get('offers', [])
                            if not offers:
                                break
                            
                            for offer in offers:
                                sku = offer.get('shop_sku')
                                price = offer.get('price')
                                qty = offer.get('quantity')
                                
                                if sku and price is not None:
                                    price_map[sku] = {
                                        'price': float(price),
                                        'stock': int(qty) if qty is not None else 0
                                    }
                            
                            if len(offers) < max_records:
                                break
                            offset += max_records
                        else:
                            _logger.error("Error API Ripley Mirakl: %s - %s", res.status_code, res.text)
                            break
                            
                    pen_currency = self.env['res.currency'].search([('name', '=', 'PEN')], limit=1)
                    for record in ripley_links:
                        variant_sku = record.product_id.default_code
                        if variant_sku and variant_sku in price_map:
                            record.marketplace_price = price_map[variant_sku]['price']
                            record.marketplace_stock = price_map[variant_sku]['stock']
                            record.last_price_sync = datetime.now()
                            if pen_currency:
                                record.marketplace_currency_id = pen_currency.id
                except Exception as e:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error("Error sincronizando Ripley: %s", str(e))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Delegamos los campos al primer variant para mantener compatibilidad con las vistas
    x_url_m1 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 1')
    x_url_m2 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 2')
    x_url_m3 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 3')
    x_url_m4 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 4')
    x_url_m5 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 5')
    x_url_m6 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 6')
    x_url_m7 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 7')
    x_url_m8 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 8')
    x_url_m9 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 9')
    x_url_m10 = fields.Char(compute='_compute_template_marketplace_urls', inverse='_inverse_template_marketplace_urls', string='Marketplace 10')

    @api.depends('product_variant_ids.x_url_m1', 'product_variant_ids.x_url_m2', 'product_variant_ids.x_url_m3', 'product_variant_ids.x_url_m4', 'product_variant_ids.x_url_m5', 'product_variant_ids.x_url_m6', 'product_variant_ids.x_url_m7', 'product_variant_ids.x_url_m8', 'product_variant_ids.x_url_m9', 'product_variant_ids.x_url_m10')
    def _compute_template_marketplace_urls(self):
        for record in self:
            variant = record.product_variant_ids[:1]
            for i in range(1, 11):
                setattr(record, f'x_url_m{i}', getattr(variant, f'x_url_m{i}') if variant else False)

    def _inverse_template_marketplace_urls(self):
        # Al escribir en la plantilla, aplicamos el mismo URL a TODAS sus variantes
        for record in self:
            for variant in record.product_variant_ids:
                for i in range(1, 11):
                    val = getattr(record, f'x_url_m{i}')
                    if val != getattr(variant, f'x_url_m{i}'):
                        setattr(variant, f'x_url_m{i}', val)

    def action_auto_correct_marketplaces(self):
        """Acción de servidor para reasignar automáticamente los enlaces a sus marketplaces correctos."""
        marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
        sorted_mps = sorted(marketplaces, key=lambda m: len(m.name), reverse=True)
        
        for record in self:
            for variant in record.product_variant_ids:
                for link in variant.x_marketplace_ids:
                    if not link.url:
                        continue
                        
                    url_lower = link.url.lower()
                    for mp in sorted_mps:
                        keyword = mp.name.lower().replace(' ', '')
                        if keyword in url_lower and link.marketplace_id.id != mp.id:
                            existing = variant.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == mp.id)
                            if not existing:
                                link.marketplace_id = mp.id
                            break

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type in ('tree', 'list', 'form'):
            from lxml import etree
            arch = res.get('arch')
            if arch:
                doc = etree.fromstring(arch)
                marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
                for idx, mp in enumerate(marketplaces[:10]):
                    field_name = f'x_url_m{idx+1}'
                    for node in doc.xpath(f"//field[@name='{field_name}']"):
                        node.set('string', mp.name)
                    if res.get('fields', {}).get(field_name):
                        res['fields'][field_name]['string'] = mp.name
                res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
