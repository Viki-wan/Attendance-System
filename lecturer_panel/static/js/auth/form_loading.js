// Form loading state module
export function setupFormLoading(formId, btnId) {
    const form = document.getElementById(formId);
    const btn = document.getElementById(btnId);
    if (form && btn) {
        form.addEventListener('submit', function() {
            btn.disabled = true;
            const spinner = btn.querySelector('.spinner-border');
            const btnText = btn.querySelector('.btn-text');
            if (spinner) spinner.classList.remove('d-none');
            if (btnText) btnText.style.display = 'none';
        });
    }
} 