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
    'depends': ['product', 'sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/marketplace_views.xml',
        'views/product_variant_marketplace_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
