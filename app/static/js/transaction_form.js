/**
 * Portfolio Tracker -- Transaction form dynamic field visibility.
 * Shows/hides form fields based on selected transaction type.
 */

document.addEventListener('DOMContentLoaded', function () {
    var txTypeSelect = document.getElementById('tx_type');
    var assetFields = document.getElementById('assetFields');
    var qtyPriceFields = document.getElementById('qtyPriceFields');
    var amountField = document.getElementById('amountField');
    var feeField = document.getElementById('feeField');

    if (!txTypeSelect) return;

    function updateFields() {
        var type = txTypeSelect.value;

        // Reset visibility
        assetFields.classList.add('hidden');
        qtyPriceFields.classList.add('hidden');
        amountField.classList.add('hidden');
        if (feeField) feeField.classList.add('hidden');

        // Remove required attributes
        var assetSymbol = document.getElementById('asset_symbol');
        var quantity = document.getElementById('quantity');
        var pricePerUnit = document.getElementById('price_per_unit');
        var totalAmount = document.getElementById('total_amount');

        assetSymbol.removeAttribute('required');
        quantity.removeAttribute('required');
        pricePerUnit.removeAttribute('required');
        totalAmount.removeAttribute('required');

        if (type === 'buy' || type === 'sell') {
            assetFields.classList.remove('hidden');
            qtyPriceFields.classList.remove('hidden');
            if (feeField) feeField.classList.remove('hidden');
            assetSymbol.setAttribute('required', '');
            quantity.setAttribute('required', '');
            pricePerUnit.setAttribute('required', '');
        } else if (type === 'dividend') {
            assetFields.classList.remove('hidden');
            amountField.classList.remove('hidden');
            assetSymbol.setAttribute('required', '');
            totalAmount.setAttribute('required', '');
        } else if (type === 'deposit' || type === 'withdrawal') {
            amountField.classList.remove('hidden');
            totalAmount.setAttribute('required', '');
        }
    }

    txTypeSelect.addEventListener('change', updateFields);

    // Run on page load in case of form re-render with pre-selected value
    updateFields();

    // Pre-select account from query string
    var urlParams = new URLSearchParams(window.location.search);
    var preAccount = urlParams.get('account_id');
    if (preAccount) {
        var accountSelect = document.getElementById('account_id');
        if (accountSelect) {
            accountSelect.value = preAccount;
        }
    }
});
