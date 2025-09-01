/**
 * Simplified Currency conversion handling for License Instance forms
 */

document.addEventListener('DOMContentLoaded', function() {
    const currencySelector = document.querySelector('.currency-selector');
    const nokPriceField = document.querySelector('.nok-price-field');
    
    if (!currencySelector || !nokPriceField) {
        return; // Fields not found, exit early
    }
    
    function updateFieldVisibility() {
        const selectedCurrency = currencySelector.value;
        const isNOK = selectedCurrency === 'NOK' || selectedCurrency === '';
        
        // Find NOK price field container
        const nokRow = nokPriceField.closest('.form-group') || nokPriceField.closest('tr') || nokPriceField.closest('.field');
        
        if (isNOK) {
            // Hide NOK price field for NOK currency (not needed)
            if (nokRow) nokRow.style.display = 'none';
        } else {
            // Show NOK price field for non-NOK currencies
            if (nokRow) nokRow.style.display = '';
        }
    }
    
    // Event listeners
    currencySelector.addEventListener('change', function() {
        updateFieldVisibility();
    });
    
    // Initialize on page load
    updateFieldVisibility();
    
    // Form validation
    const form = currencySelector.closest('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const selectedCurrency = currencySelector.value;
            
            if (selectedCurrency && selectedCurrency !== 'NOK') {
                const nokPrice = parseFloat(nokPriceField.value) || 0;
                if (nokPrice <= 0) {
                    e.preventDefault();
                    alert('Please enter a valid NOK price for currency conversion.');
                    nokPriceField.focus();
                    return false;
                }
            }
        });
    }
});