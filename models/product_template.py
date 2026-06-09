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
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Accept': 'application/json'
                        }
                        response = requests.get(api_url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            price = data.get('price')
                            ml_currency = data.get('currency_id')
                            
                            if price is not None:
                                record.marketplace_price = float(price)
                                record.last_price_sync = datetime.now()
                                
                                # Buscar moneda
                                odoo_currency_code = currency_map.get(ml_currency, ml_currency)
                                currency = self.env['res.currency'].search([('name', '=', odoo_currency_code)], limit=1)
                                if currency:
                                    record.marketplace_currency_id = currency.id
                    except Exception as e:
                        import logging
                        _logger = logging.getLogger(__name__)
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
                            sku = str(p.get('SellerSku', '')).strip()
                            sale_price = p.get('SalePrice')
                            price = p.get('Price')
                            
                            # Usar SalePrice si existe y es > 0, sino usar Price normal
                            try:
                                final_price = float(sale_price) if sale_price and float(sale_price) > 0 else float(price or 0)
                                if final_price > 0 and sku:
                                    price_map[sku] = final_price
                            except (ValueError, TypeError):
                                pass
                        
                        # Moneda de Falabella Perú por defecto
                        pen_currency = self.env['res.currency'].search([('name', '=', 'PEN')], limit=1)
                        
                        for record in falabella_links:
                            # El SellerSku es la referencia interna de la variante
                            variant_sku = record.product_id.default_code
                            if variant_sku and variant_sku in price_map:
                                record.marketplace_price = price_map[variant_sku]
                                record.last_price_sync = datetime.now()
                                if pen_currency:
                                    record.marketplace_currency_id = pen_currency.id

                except Exception as e:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error("Error conectando a API Falabella: %s", str(e))


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
