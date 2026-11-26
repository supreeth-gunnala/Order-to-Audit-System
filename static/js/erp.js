/**
 * Order-to-Audit ERP - Client-Side Enhancements
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Initialize Bootstrap Tooltips
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

  // 2. Auto-dismiss alerts after 5 seconds
  const autoAlerts = document.querySelectorAll('.alert-dismissible');
  autoAlerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 5000);
  });

  // 3. Double-submit prevention on forms
  const forms = document.querySelectorAll('form:not(.no-disable-on-submit)');
  forms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (form.checkValidity()) {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn && !submitBtn.classList.contains('no-spin')) {
          submitBtn.disabled = true;
          const origHtml = submitBtn.innerHTML;
          submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
        }
      }
    });
  });

  // 4. Quick Table Search Filters (elements with data-filter-table="#tableId")
  const searchInputs = document.querySelectorAll('[data-filter-table]');
  searchInputs.forEach(function (input) {
    const targetTableId = input.getAttribute('data-filter-table');
    const table = document.querySelector(targetTableId);
    if (!table) return;

    input.addEventListener('input', function () {
      const term = this.value.toLowerCase().trim();
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        const text = row.textContent.toLowerCase();
        row.style.display = text.indexOf(term) > -1 ? '' : 'none';
      });
    });
  });
});

/**
 * Global helper to format currency in Indian format
 */
function formatINR(val) {
  const num = parseFloat(val) || 0;
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}
