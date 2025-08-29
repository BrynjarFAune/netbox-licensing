/**
 * Simplified Currency conversion handling for License Instance forms
 */

document.addEventListener('DOMContentLoaded', function() {
    const currencySelector = document.querySelector('.currency-selector');
    const priceField = document.querySelector('.price-field');
    const modeSelector = document.querySelector('.price-input-mode-selector');
    const conversionField = document.querySelector('.conversion-rate-field');
    const nokPriceField = document.querySelector('.nok-price-field');
    
    if (!currencySelector || !modeSelector || !conversionField || !nokPriceField) {
        return; // Fields not found, exit early
    }
    
    function updateFieldVisibility() {
        const selectedCurrency = currencySelector.value;
        const inputMode = modeSelector.value;
        const isNOK = selectedCurrency === 'NOK' || selectedCurrency === '';
        
        // Find field containers
        const modeRow = modeSelector.closest('.form-group') || modeSelector.closest('tr') || modeSelector.closest('.field');
        const conversionRow = conversionField.closest('.form-group') || conversionField.closest('tr') || conversionField.closest('.field');
        const nokRow = nokPriceField.closest('.form-group') || nokPriceField.closest('tr') || nokPriceField.closest('.field');
        
        if (isNOK) {
            // Hide all currency conversion fields for NOK
            if (modeRow) modeRow.style.display = 'none';
            if (conversionRow) conversionRow.style.display = 'none';
            if (nokRow) nokRow.style.display = 'none';
        } else {
            // Show mode selector for non-NOK currencies
            if (modeRow) modeRow.style.display = '';
            
            // Show only the relevant field based on input mode
            if (inputMode === 'conversion_rate') {
                if (conversionRow) conversionRow.style.display = '';
                if (nokRow) nokRow.style.display = 'none';
                // Clear NOK field when switching to conversion rate mode
                if (nokPriceField) nokPriceField.value = '';
            } else if (inputMode === 'nok_price') {
                if (conversionRow) conversionRow.style.display = 'none';
                if (nokRow) nokRow.style.display = '';
                // Clear conversion rate when switching to NOK price mode
                if (conversionField) conversionField.value = '';
            }
        }
    }
    
    function setDefaultValues() {
        const selectedCurrency = currencySelector.value;
        const inputMode = modeSelector.value;
        
        // Set default conversion rates
        if (inputMode === 'conversion_rate' && !conversionField.value) {
            const defaultRates = {
                'USD': '10.5',
                'EUR': '11.2', 
                'SEK': '0.95',
                'DKK': '1.55'
            };
            if (defaultRates[selectedCurrency]) {
                conversionField.value = defaultRates[selectedCurrency];
            }
        }
    }
    
    // Event listeners
    currencySelector.addEventListener('change', function() {
        updateFieldVisibility();
        setDefaultValues();
    });
    
    modeSelector.addEventListener('change', function() {
        updateFieldVisibility();
        setDefaultValues();
    });
    
    // Initialize on page load
    updateFieldVisibility();
    setDefaultValues();
    
    // Form validation
    const form = currencySelector.closest('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const selectedCurrency = currencySelector.value;
            const inputMode = modeSelector.value;
            
            if (selectedCurrency && selectedCurrency !== 'NOK') {
                if (inputMode === 'conversion_rate') {
                    const rate = parseFloat(conversionField.value) || 0;
                    if (rate <= 0) {
                        e.preventDefault();
                        alert('Please enter a valid conversion rate.');
                        conversionField.focus();
                        return false;
                    }
                } else if (inputMode === 'nok_price') {
                    const nokPrice = parseFloat(nokPriceField.value) || 0;
                    if (nokPrice <= 0) {
                        e.preventDefault();
                        alert('Please enter a valid NOK price.');
                        nokPriceField.focus();
                        return false;
                    }
                }
            }
        });
    }
});