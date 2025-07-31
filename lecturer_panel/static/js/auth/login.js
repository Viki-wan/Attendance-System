// Login page JS for lecturer panel

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const togglePassword = document.getElementById('togglePassword');
    const passwordField = document.getElementById('passwordField');
    const phoneField = document.getElementById('phone');

    // Password toggle functionality
    if (togglePassword && passwordField) {
        togglePassword.addEventListener('click', function() {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            const icon = this.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye');
                icon.classList.toggle('fa-eye-slash');
            }
        });
    }

    // Form submission with loading state
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            const loginText = submitBtn.querySelector('.login-text');
            const loadingText = submitBtn.querySelector('.loading');
            submitBtn.disabled = true;
            if (loginText) loginText.style.display = 'none';
            if (loadingText) loadingText.style.display = 'inline';
        });
    }

    // Auto-focus on first empty field
    if (phoneField && !phoneField.value) {
        phoneField.focus();
    } else if (passwordField && !passwordField.value) {
        passwordField.focus();
    }

    // Phone number formatting
    if (phoneField) {
        phoneField.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 0 && !value.startsWith('0')) {
                value = '0' + value;
            }
            if (value.length > 10) {
                value = value.substring(0, 10);
            }
            e.target.value = value;
        });
        // Enter key navigation
        phoneField.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && passwordField) {
                e.preventDefault();
                passwordField.focus();
            }
        });
    }

    // Clear any form errors on input
    if (loginForm) {
        const inputs = loginForm.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                const errorDiv = this.parentNode.nextElementSibling;
                if (errorDiv && errorDiv.classList.contains('text-danger')) {
                    errorDiv.style.display = 'none';
                }
            });
        });
    }

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        });
    }, 5000);
}); 