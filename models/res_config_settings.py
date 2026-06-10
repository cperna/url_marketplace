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
