/**
 * Currency conversion handling for License Instance forms
 */

document.addEventListener('DOMContentLoaded', function() {
    const currencySelector = document.querySelector('.currency-selector');
    const priceField = document.querySelector('.price-field');
    const conversionField = document.querySelector('.conversion-rate-field');
    const nokPriceField = document.querySelector('.nok-price-field');
    
    if (!currencySelector || !priceField || !conversionField || !nokPriceField) {
        return; // Fields not found, exit early
    }
    
    function updateFields() {
        const selectedCurrency = currencySelector.value;
        const isNOK = selectedCurrency === 'NOK' || selectedCurrency === '';
        
        // Show/hide conversion fields based on currency selection
        const conversionRow = conversionField.closest('.form-group') || conversionField.closest('tr');
        const nokRow = nokPriceField.closest('.form-group') || nokPriceField.closest('tr');
        
        if (conversionRow) {
            conversionRow.style.display = isNOK ? 'none' : '';
        }
        if (nokRow) {
            nokRow.style.display = isNOK ? 'none' : '';
        }
        
        if (isNOK) {
            // Clear conversion fields for NOK
            conversionField.value = '';
            nokPriceField.value = '';
            nokPriceField.removeAttribute('readonly');
            return;
        }
        
        // Set readonly for NOK field when conversion is active
        nokPriceField.setAttribute('readonly', true);
        
        // Set default conversion rate if empty
        if (!conversionField.value) {
            const defaultRates = {
                'USD': 10.5,
                'EUR': 11.2,
                'SEK': 0.95
            };
            if (defaultRates[selectedCurrency]) {
                conversionField.value = defaultRates[selectedCurrency];
            }
        }
        
        calculateNOKPrice();
    }
    
    function calculateNOKPrice() {
        const price = parseFloat(priceField.value) || 0;
        const rate = parseFloat(conversionField.value) || 0;
        
        if (price > 0 && rate > 0) {
            const nokPrice = price * rate;
            nokPriceField.value = nokPrice.toFixed(2);
        } else {
            nokPriceField.value = '';
        }
    }
    
    function calculateConversionRate() {
        const price = parseFloat(priceField.value) || 0;
        const nokPrice = parseFloat(nokPriceField.value) || 0;
        
        if (price > 0 && nokPrice > 0) {
            const rate = nokPrice / price;
            conversionField.value = rate.toFixed(6);
        }
    }
    
    // Event listeners
    currencySelector.addEventListener('change', updateFields);
    
    priceField.addEventListener('input', function() {
        if (currencySelector.value && currencySelector.value !== 'NOK') {
            calculateNOKPrice();
        }
    });
    
    conversionField.addEventListener('input', function() {
        if (currencySelector.value && currencySelector.value !== 'NOK') {
            calculateNOKPrice();
        }
    });
    
    nokPriceField.addEventListener('input', function() {
        if (currencySelector.value && currencySelector.value !== 'NOK' && !nokPriceField.hasAttribute('readonly')) {
            calculateConversionRate();
        }
    });
    
    // Initialize on page load
    updateFields();
    
    // Handle form submission validation
    const form = currencySelector.closest('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const selectedCurrency = currencySelector.value;
            
            if (selectedCurrency && selectedCurrency !== 'NOK') {
                const rate = parseFloat(conversionField.value) || 0;
                
                if (rate <= 0) {
                    e.preventDefault();
                    alert('Please enter a valid conversion rate for the selected currency.');
                    conversionField.focus();
                    return false;
                }
            }
        });
    }
});