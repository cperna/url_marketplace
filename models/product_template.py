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

    _sql_constraints = [
        ('uniq_product_marketplace', 'unique(product_id, marketplace_id)', '¡Ya existe un enlace para este marketplace en esta variante!')
    ]


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
