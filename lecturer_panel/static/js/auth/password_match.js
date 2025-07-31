// Password match check module
export function setupPasswordMatch(passwordId, confirmId, matchTextId, submitBtnId, strengthChecker) {
    const passwordInput = document.getElementById(passwordId);
    const confirmInput = document.getElementById(confirmId);
    const matchText = document.getElementById(matchTextId);
    const submitBtn = document.getElementById(submitBtnId);
    if (!passwordInput || !confirmInput || !matchText || !submitBtn) return;
    function checkMatch() {
        const password = passwordInput.value;
        const confirm = confirmInput.value;
        if (!confirm) {
            matchText.textContent = '';
            submitBtn.disabled = true;
            return;
        }
        if (password === confirm) {
            matchText.textContent = '✓ Passwords match';
            matchText.className = 'text-success';
            if (strengthChecker) {
                const { score } = strengthChecker(password);
                submitBtn.disabled = !(score >= 50);
            } else {
                submitBtn.disabled = false;
            }
        } else {
            matchText.textContent = "✗ Passwords don't match";
            matchText.className = 'text-danger';
            submitBtn.disabled = true;
        }
    }
    confirmInput.addEventListener('input', checkMatch);
    passwordInput.addEventListener('input', checkMatch);
} 