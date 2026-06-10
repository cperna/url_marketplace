from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    falabella_api_user_id = fields.Char(
        string='Falabella API User ID',
        config_parameter='url_marketplace.falabella_api_user_id',
        help="El User ID de tu cuenta de Falabella Seller Center (ej. ventas@gbcstore.com.pe)"
    )
    
    falabella_api_key = fields.Char(
        string='Falabella API Key',
        config_parameter='url_marketplace.falabella_api_key',
        help="La clave API proporcionada por Falabella Seller Center"
    )

    ripley_api_key = fields.Char(
        string='Ripley API Key (Mirakl)',
        config_parameter='url_marketplace.ripley_api_key',
        help="La Clave API generada desde el panel de Mirakl de Ripley Perú"
    )
    
    ripley_shop_id = fields.Char(
        string='Ripley Shop ID (Mirakl)',
        config_parameter='url_marketplace.ripley_shop_id',
        help="Tu ID de tienda en Ripley (Opcional pero recomendado)"
    )

    ml_app_id = fields.Char(
        string='Mercado Libre App ID',
        config_parameter='url_marketplace.ml_app_id',
        help="El ID de la Aplicación de Mercado Libre"
    )

    ml_secret_key = fields.Char(
        string='Mercado Libre Secret Key',
        config_parameter='url_marketplace.ml_secret_key',
        help="La Clave Secreta de la Aplicación"
    )

    ml_redirect_uri = fields.Char(
        string='Mercado Libre Redirect URI',
        config_parameter='url_marketplace.ml_redirect_uri',
        help="URL de redirección configurada en la App (ej. https://techstop.com.pe)"
    )

    ml_auth_code = fields.Char(
        string='Mercado Libre Auth Code (TG)',
        config_parameter='url_marketplace.ml_auth_code',
        help="Código de autorización manual (TG-...) generado tras dar permisos a la App."
    )

    vtex_account_name = fields.Char(
        string='VTEX Account Name (Claro)',
        config_parameter='url_marketplace.vtex_account_name',
        help="El nombre de tu cuenta en VTEX (ej. claroperu o tiendaclaro)"
    )

    vtex_app_key = fields.Char(
        string='VTEX API AppKey',
        config_parameter='url_marketplace.vtex_app_key',
        help="La Clave API generada en VTEX"
    )

    vtex_app_token = fields.Char(
        string='VTEX API AppToken',
        config_parameter='url_marketplace.vtex_app_token',
        help="El Token Secreto de la API generado en VTEX"
    )

    vtex_marketplace_id = fields.Many2one(
        'marketplace.marketplace',
        string='Marketplace destino (Claro)',
        config_parameter='url_marketplace.vtex_marketplace_id',
        help="Elige el marketplace que representa a Claro para asignar los enlaces automáticamente"
    )

    vtex_store_domain = fields.Char(
        string='Dominio de la Tienda (Ej. www.tiendaclaro.pe)',
        config_parameter='url_marketplace.vtex_store_domain',
        help="Usado para construir la URL pública de los productos al importarlos"
    )

    def action_import_vtex_catalog(self):
        """Tarea manual para importar el catálogo de VTEX a los enlaces de Odoo"""
        vtex_account_name = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.vtex_account_name')
        vtex_app_key = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.vtex_app_key')
        vtex_app_token = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.vtex_app_token')
        vtex_marketplace_id = int(self.env['ir.config_parameter'].sudo().get_param('url_marketplace.vtex_marketplace_id', 0))
        vtex_store_domain = self.env['ir.config_parameter'].sudo().get_param('url_marketplace.vtex_store_domain')

        if not vtex_account_name or not vtex_app_key or not vtex_app_token or not vtex_marketplace_id:
            raise models.ValidationError("Faltan configurar credenciales o el Marketplace destino para VTEX.")

        domain = vtex_store_domain or f"{vtex_account_name}.myvtex.com"

        import requests
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-VTEX-API-AppKey': vtex_app_key,
            'X-VTEX-API-AppToken': vtex_app_token
        }

        # 1. Obtener la lista de SKU IDs
        page = 1
        pagesize = 1000
        all_sku_ids = []
        while True:
            url_ids = f"https://{vtex_account_name}.vtexcommercestable.com.br/api/catalog_system/pvt/sku/stockkeepingunitids?page={page}&pagesize={pagesize}"
            res = requests.get(url_ids, headers=headers, timeout=20)
            if res.status_code == 200:
                sku_ids = res.json()
                if not sku_ids:
                    break
                all_sku_ids.extend(sku_ids)
                if len(sku_ids) < pagesize:
                    break
                page += 1
            else:
                raise models.UserError(f"Error obteniendo IDs de VTEX: {res.status_code} - {res.text}")

        # 2. Consultar cada SKU
        LinkModel = self.env['product.variant.marketplace']
        ProductModel = self.env['product.product']
        
        imported_count = 0
        orphan_count = 0

        for sku_id in all_sku_ids:
            url_detail = f"https://{vtex_account_name}.vtexcommercestable.com.br/api/catalog_system/pvt/sku/stockkeepingunitbyid/{sku_id}"
            res_det = requests.get(url_detail, headers=headers, timeout=10)
            if res_det.status_code == 200:
                data = res_det.json()
                ref_id = data.get('RefId')
                name = data.get('NameComplete') or data.get('Name')
                
                # Intentar hacer match por Referencia Interna de Odoo
                product = False
                if ref_id:
                    product = ProductModel.search([('default_code', '=', ref_id)], limit=1)
                if not product:
                    # Alternativa: Buscar por el propio ID numérico del SKU en VTEX si Odoo lo usa como código
                    product = ProductModel.search([('default_code', '=', str(sku_id))], limit=1)

                # Comprobar si ya existe un enlace
                existing = LinkModel.search([
                    ('marketplace_sku', '=', ref_id or str(sku_id)),
                    ('marketplace_id', '=', vtex_marketplace_id)
                ], limit=1)
                
                # O si el producto ya tiene un enlace a ese marketplace
                if not existing and product:
                    existing = LinkModel.search([
                        ('product_id', '=', product.id),
                        ('marketplace_id', '=', vtex_marketplace_id)
                    ], limit=1)

                vals = {
                    'marketplace_id': vtex_marketplace_id,
                    'marketplace_sku': ref_id or str(sku_id),
                    'marketplace_product_name': name,
                    'url': f"https://{domain}/p?skuId={sku_id}"
                }
                
                if product:
                    vals['product_id'] = product.id
                    imported_count += 1
                else:
                    orphan_count += 1

                if existing:
                    # Update fields except product_id if it's already linked correctly
                    update_vals = {'marketplace_product_name': name, 'marketplace_sku': ref_id or str(sku_id)}
                    if product and not existing.product_id:
                        update_vals['product_id'] = product.id
                    existing.write(update_vals)
                else:
                    LinkModel.create(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación Completada',
                'message': f'Se escanearon {len(all_sku_ids)} SKUs. Enlazados: {imported_count}. Huérfanos: {orphan_count}.',
                'type': 'success',
                'sticky': False,
            }
        }
