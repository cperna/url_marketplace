# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_marketplace_ids = fields.One2many(
        'product.variant.marketplace',
        'product_id',
        string='Marketplaces y Enlaces de Compra',
        help='Enlaces de compra en las diferentes plataformas de marketplace'
    )

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
            for i in range(1, 11):
                setattr(record, f'x_url_m{i}', False)
            for idx, mp in enumerate(marketplaces[:10]):
                link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == mp.id)
                if link:
                    setattr(record, f'x_url_m{idx+1}', link[0].url)

    def _inverse_marketplace_url(self, index):
        marketplaces = self.env['marketplace.marketplace'].search([], order='sequence, id')
        if len(marketplaces) < index:
            return
            
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
            
            if target_mp != original_mp:
                original_link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == original_mp.id)
                if original_link:
                    original_link.unlink()
            
            link = record.x_marketplace_ids.filtered(lambda l: l.marketplace_id.id == target_mp.id)
            if link:
                if val:
                    link[0].url = val
                else:
                    link[0].unlink()
            elif val:
                self.env['product.variant.marketplace'].create({
                    'product_id': record.id,
                    'marketplace_id': target_mp.id,
                    'url': val
                })

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
                for idx, mp in enumerate(marketplaces[:10]):
                    field_name = f'x_url_m{idx+1}'
                    for node in doc.xpath(f"//field[@name='{field_name}']"):
                        node.set('string', mp.name)
                    if res.get('fields', {}).get(field_name):
                        res['fields'][field_name]['string'] = mp.name
                res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
