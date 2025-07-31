// Password toggle functionality
const passwordInput = document.getElementById('password');
const confirmPasswordInput = document.getElementById('confirm_password');
const togglePassword = document.getElementById('toggle-password');
if (togglePassword) {
    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        this.querySelector('i').classList.toggle('fa-eye');
        this.querySelector('i').classList.toggle('fa-eye-slash');
    });
}
// Password strength checker
if (passwordInput) {
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        const strengthBar = document.getElementById('password-strength-bar');
        const strengthText = document.getElementById('password-strength-text');
        let strength = 0;
        let feedback = '';
        if (password.length >= 8) strength++;
        if (password.match(/[a-z]/)) strength++;
        if (password.match(/[A-Z]/)) strength++;
        if (password.match(/[0-9]/)) strength++;
        if (password.match(/[^a-zA-Z0-9]/)) strength++;
        strengthBar.className = 'progress-bar';
        switch(strength) {
            case 0:
            case 1:
                strengthBar.style.width = '20%';
                strengthBar.classList.add('bg-danger');
                feedback = 'Very weak';
                break;
            case 2:
                strengthBar.style.width = '40%';
                strengthBar.classList.add('bg-danger');
                feedback = 'Weak';
                break;
            case 3:
                strengthBar.style.width = '60%';
                strengthBar.classList.add('bg-warning');
                feedback = 'Fair';
                break;
            case 4:
                strengthBar.style.width = '80%';
                strengthBar.classList.add('bg-success');
                feedback = 'Good';
                break;
            case 5:
                strengthBar.style.width = '100%';
                strengthBar.classList.add('bg-success');
                feedback = 'Strong';
                break;
        }
        strengthText.textContent = feedback;
        checkPasswordMatch();
    });
}
// Password match checker
function checkPasswordMatch() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const matchText = document.getElementById('password-match-text');
    if (confirmPassword === '') {
        matchText.textContent = '';
        matchText.className = '';
        return;
    }
    if (password === confirmPassword) {
        matchText.textContent = '✓ Passwords match';
        matchText.className = 'text-success';
        confirmPasswordInput.classList.remove('is-invalid');
        confirmPasswordInput.classList.add('is-valid');
    } else {
        matchText.textContent = '✗ Passwords do not match';
        matchText.className = 'text-danger';
        confirmPasswordInput.classList.remove('is-valid');
        confirmPasswordInput.classList.add('is-invalid');
    }
}
if (confirmPasswordInput) {
    confirmPasswordInput.addEventListener('input', checkPasswordMatch);
} 