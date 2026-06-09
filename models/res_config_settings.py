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
