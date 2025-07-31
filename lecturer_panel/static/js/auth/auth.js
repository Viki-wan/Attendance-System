// Authentication UI logic for lecturer panel

document.addEventListener('DOMContentLoaded', function() {
    // Password strength checker
    function checkPasswordStrength(password) {
        let score = 0;
        let feedback = [];
        if (password.length >= 8) {
            score += 20;
            if (password.length >= 12) score += 20;
        } else {
            feedback.push('Password should be at least 8 characters');
        }
        if (/[A-Z]/.test(password)) score += 15; else feedback.push('Add uppercase letters');
        if (/[a-z]/.test(password)) score += 15; else feedback.push('Add lowercase letters');
        if (/[0-9]/.test(password)) score += 15; else feedback.push('Add numbers');
        if (/[^A-Za-z0-9]/.test(password)) score += 15; else feedback.push('Add special characters (!@#$%^&*)');
        let color = 'bg-danger';
        if (score >= 80) color = 'bg-success';
        else if (score >= 50) color = 'bg-warning';
        return { score, color, feedback };
    }

    // Password strength for setup and change password forms
    const passwordInput = document.getElementById('password') || document.getElementById('new_password');
    const strengthBar = document.getElementById('password-strength-bar') || document.getElementById('new-password-strength-bar');
    const strengthText = document.getElementById('password-strength-text') || document.getElementById('new-password-strength-text');
    if (passwordInput && strengthBar && strengthText) {
        passwordInput.addEventListener('input', function() {
            const { score, color, feedback } = checkPasswordStrength(this.value);
            strengthBar.style.width = score + '%';
            strengthBar.className = 'progress-bar ' + color;
            strengthText.textContent = feedback.length > 0 ? 'Suggestions: ' + feedback.join(', ') : 'Excellent password!';
            checkPasswordsMatch();
        });
    }

    // Password match check
    function checkPasswordsMatch() {
        const password = document.getElementById('password') ? document.getElementById('password').value : (document.getElementById('new_password') ? document.getElementById('new_password').value : '');
        const confirm = document.getElementById('confirm_password');
        const matchText = document.getElementById('password-match-text');
        const submitBtn = document.getElementById('setup-btn') || document.getElementById('change-password-btn');
        if (!confirm || !matchText || !submitBtn) return;
        if (!confirm.value) {
            matchText.textContent = '';
            submitBtn.disabled = true;
            return;
        }
        if (password === confirm.value) {
            matchText.textContent = '✓ Passwords match';
            matchText.className = 'text-success';
            const { score } = checkPasswordStrength(password);
            submitBtn.disabled = !(score >= 50);
        } else {
            matchText.textContent = "✗ Passwords don't match";
            matchText.className = 'text-danger';
            submitBtn.disabled = true;
        }
    }
    const confirmInput = document.getElementById('confirm_password');
    if (confirmInput) confirmInput.addEventListener('input', checkPasswordsMatch);

    // Password visibility toggles
    function setupToggle(toggleId, inputId) {
        const toggle = document.getElementById(toggleId);
        const input = document.getElementById(inputId);
        if (toggle && input) {
            toggle.addEventListener('click', function() {
                input.type = input.type === 'password' ? 'text' : 'password';
                const icon = this.querySelector('i');
                if (icon) {
                    icon.classList.toggle('fa-eye');
                    icon.classList.toggle('fa-eye-slash');
                }
            });
        }
    }
    setupToggle('toggle-password', 'password');
    setupToggle('toggle-new-password', 'new_password');

    // Loading state for submit buttons
    function setupLoading(formId, btnId) {
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
    setupLoading('setup-form', 'setup-btn');
    setupLoading('change-password-form', 'change-password-btn');
    setupLoading('forgot-password-form', 'forgot-password-btn');

    // Auto-dismiss flash messages
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        });
    }, 5000);
}); 