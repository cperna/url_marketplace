/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import "@website_sale/js/website_sale"; // Ensure website_sale is loaded so we can include it

publicWidget.registry.WebsiteSale.include({
    /**
     * @override
     */
    _onChangeCombination: function (ev, $parent, combination) {
        this._super.apply(this, arguments);
        
        // Hide all marketplace containers
        $parent.find('.js_marketplace_container').addClass('d-none');
        
        // Show the container matching the current combination's product variant ID
        if (combination.product_id) {
            $parent.find('.js_marketplace_container[data-variant-id="' + combination.product_id + '"]').removeClass('d-none');
        }
    }
});
