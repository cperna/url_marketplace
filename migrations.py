# Este archivo no se ejecuta automáticamente por Odoo, 
# se usará desde odoo shell antes de actualizar el módulo.

def migrate_urls(env):
    env.cr.execute("""
        ALTER TABLE product_variant_marketplace ADD COLUMN IF NOT EXISTS product_id INTEGER;
        
        UPDATE product_variant_marketplace pvm
        SET product_id = (
            SELECT pp.id 
            FROM product_product pp 
            WHERE pp.product_tmpl_id = pvm.product_tmpl_id 
            ORDER BY pp.id ASC 
            LIMIT 1
        )
        WHERE pvm.product_id IS NULL AND pvm.product_tmpl_id IS NOT NULL;
    """)
    env.cr.commit()
    print("Migración SQL de product_tmpl_id a product_id completada exitosamente.")
