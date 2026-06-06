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
        """Fusiona los marketplaces duplicados conservando el primero y eliminando el resto,
        reasignando los enlaces de productos al marketplace principal."""
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
                        ('product_tmpl_id', '=', link.product_tmpl_id.id)
                    ])
                    if existing:
                        link.unlink()
                    else:
                        link.marketplace_id = keep.id
                remove.unlink()


class ProductVariantMarketplace(models.Model):
    _name = 'product.variant.marketplace'
    _description = 'Enlace de Producto a Marketplace'
    _order = 'marketplace_id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
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
        help='Enlace directo al producto publicado en este marketplace'
    )

    _sql_constraints = [
        ('uniq_product_marketplace', 'unique(product_tmpl_id, marketplace_id)', '¡Ya existe un enlace para este marketplace en este producto!')
    ]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_marketplace_ids = fields.One2many(
        'product.variant.marketplace',
        'product_tmpl_id',
        string='Marketplaces y Enlaces de Compra',
        help='Enlaces de compra en las diferentes plataformas de marketplace'
    )

    # Campos computados de soporte plano para la vista de lista/tree y Odoo Studio
    x_url_m1 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_1', string='Marketplace 1')
    x_url_m2 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_2', string='Marketplace 2')
    x_url_m3 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_3', string='Marketplace 3')
    x_url_m4 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_4', string='Marketplace 4')
    x_url_m5 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_5', string='Marketplace 5')
    x_url_m6 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_6', string='Marketplace 6')
    x_url_m7 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_7', string='Marketplace 7')
    x_url_m8 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_8', string='Marketplace 8')
    x_url_m9 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_9', string='Marketplace 9')
    x_url_m10 = fields.Char(compute='_compute_marketplace_urls', inverse='_inverse_marketplace_url_10', string='Marketplace 10')

    @api.depends('x_marketplace_ids.url', 'x_marketplace_ids.marketplace_id')
    def _compute_marketplace_urls(self):
        marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
        for record in self:
            # Inicializar todos los campos a False
            for i in range(1, 11):
                setattr(record, f'x_url_m{i}', False)
            
            # Asignar URLs de los marketplaces activos correspondientes en orden de secuencia
            for idx, mp in enumerate(marketplaces[:10]):
                link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == mp.id)
                if link:
                    setattr(record, f'x_url_m{idx+1}', link[0].url)

    def _inverse_marketplace_url(self, index):
        marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
        if len(marketplaces) < index:
            return
            
        # Pre-ordenar marketplaces por longitud de nombre para buscar coincidencias largas primero
        sorted_mps = sorted(marketplaces, key=lambda m: len(m.name), reverse=True)
        original_mp = marketplaces[index-1]
        
        for record in self:
            val = getattr(record, f'x_url_m{index}')
            target_mp = original_mp
            
            if val:
                val_lower = val.lower()
                for mp in sorted_mps:
                    keyword = mp.name.lower().replace(' ', '')
                    if keyword in val_lower:
                        target_mp = mp
                        break
            
            # Si el enlace pertenece a un marketplace distinto al de la columna original
            if target_mp != original_mp:
                original_link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == original_mp.id)
                if original_link:
                    original_link.unlink()  # Limpiar la columna original porque el enlace se va a reasignar
            
            # Crear o actualizar en el marketplace destino
            link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == target_mp.id)
            if link:
                if val:
                    link[0].url = val
                else:
                    link[0].unlink()
            elif val:
                self.env['product.variant.marketplace'].create({
                    'product_tmpl_id': record.id,
                    'marketplace_id': target_mp.id,
                    'url': val
                })

    def action_auto_correct_marketplaces(self):
        """Acción de servidor para reasignar automáticamente los enlaces a sus marketplaces correctos."""
        marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
        sorted_mps = sorted(marketplaces, key=lambda m: len(m.name), reverse=True)
        
        for record in self:
            for link in record.x_marketplace_ids:
                if not link.url:
                    continue
                    
                url_lower = link.url.lower()
                for mp in sorted_mps:
                    keyword = mp.name.lower().replace(' ', '')
                    if keyword in url_lower and link.marketplace_id.id != mp.id:
                        existing = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == mp.id)
                        if not existing:
                            link.marketplace_id = mp.id
                        break

    def _inverse_marketplace_url_1(self): self._inverse_marketplace_url(1)
    def _inverse_marketplace_url_2(self): self._inverse_marketplace_url(2)
    def _inverse_marketplace_url_3(self): self._inverse_marketplace_url(3)
    def _inverse_marketplace_url_4(self): self._inverse_marketplace_url(4)
    def _inverse_marketplace_url_5(self): self._inverse_marketplace_url(5)
    def _inverse_marketplace_url_6(self): self._inverse_marketplace_url(6)
    def _inverse_marketplace_url_7(self): self._inverse_marketplace_url(7)
    def _inverse_marketplace_url_8(self): self._inverse_marketplace_url(8)
    def _inverse_marketplace_url_9(self): self._inverse_marketplace_url(9)
    def _inverse_marketplace_url_10(self): self._inverse_marketplace_url(10)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type in ('tree', 'list', 'form'):
            from lxml import etree
            arch = res.get('arch')
            if arch:
                doc = etree.fromstring(arch)
                marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
                
                # Cambiar las cabeceras de columnas XML y etiquetas de Odoo en caliente
                for idx, mp in enumerate(marketplaces[:10]):
                    field_name = f'x_url_m{idx+1}'
                    for node in doc.xpath(f"//field[@name='{field_name}']"):
                        node.set('string', mp.name)
                    
                    # Sincronizar diccionario de campos de Odoo para consistencia
                    if res.get('fields', {}).get(field_name):
                        res['fields'][field_name]['string'] = mp.name
                
                res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

