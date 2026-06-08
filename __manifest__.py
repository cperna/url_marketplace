# -*- coding: utf-8 -*-
{
    'name': 'URL Marketplace y Compra Dinámico por Variante',
    'version': '17.0.2.0.0',
    'category': 'Sales/Product',
    'summary': 'Agrega URLs de compra dinámicas con logotipos para múltiples marketplaces en cada variante de producto',
    'description': """
Módulo avanzado que permite definir dinámicamente un catálogo de marketplaces con logotipos, vinculándolos mediante tablas relacionales One2many en cada variante de producto.
    """,
    'author': 'Carlos Pernalete',
    'depends': ['product', 'sale', 'stock', 'website', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/marketplace_data.xml',
        'views/marketplace_views.xml',
        'views/product_variant_marketplace_views.xml',
        'views/website_sale_product_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'url_marketplace/static/src/scss/marketplace_buttons.scss',
            'url_marketplace/static/src/js/variant_marketplace.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
