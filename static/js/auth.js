document.addEventListener('DOMContentLoaded', function () {
  // Password strength indicator for signup form
  const passwordInput = document.getElementById('password');
  const confirmPasswordInput = document.getElementById('confirm_password');
  const passwordStrength = document.getElementById('password-strength');
  const passwordMatch = document.getElementById('password-match');

  function evaluatePassword() {
    const password = passwordInput.value;
    let strength = 0;
    let feedback = '';

    if (password.length >= 8) strength += 1;
    if (password.match(/[A-Z]/)) strength += 1;
    if (password.match(/[a-z]/)) strength += 1;
    if (password.match(/[0-9]/)) strength += 1;
    if (password.match(/[^A-Za-z0-9]/)) strength += 1;

    switch (strength) {
      case 0:
      case 1:
        feedback = 'Weak';
        passwordStrength.className = 'password-strength weak';
        break;
      case 2:
      case 3:
        feedback = 'Medium';
        passwordStrength.className = 'password-strength medium';
        break;
      case 4:
      case 5:
        feedback = 'Strong';
        passwordStrength.className = 'password-strength strong';
        break;
    }
    passwordStrength.textContent = feedback;
  }

  if (passwordInput && passwordStrength) {
    passwordInput.addEventListener('input', evaluatePassword);
  }

  // Check if passwords match
  function checkPasswordMatch() {
    if (passwordInput.value === confirmPasswordInput.value) {
      passwordMatch.textContent = 'Passwords match';
      passwordMatch.className = 'password-match match';
    } else {
      passwordMatch.textContent = 'Passwords do not match';
      passwordMatch.className = 'password-match no-match';
    }
  }

  if (confirmPasswordInput && passwordMatch) {
    confirmPasswordInput.addEventListener('input', checkPasswordMatch);
    passwordInput.addEventListener('input', function () {
      if (confirmPasswordInput.value) {
        checkPasswordMatch();
      }
    });
  }

  // Flash message auto-dismiss
  const flashMessages = document.querySelectorAll('.flash-message');
  if (flashMessages.length > 0) {
    setTimeout(() => {
      flashMessages.forEach((msg) => {
        msg.style.opacity = '0';
        setTimeout(() => {
          msg.style.display = 'none';
        }, 500);
      });
    }, 5000);
  }

  // Mobile menu toggle
  const menuToggle = document.getElementById('menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (menuToggle && navMenu) {
    menuToggle.addEventListener('click', function () {
      navMenu.classList.toggle('active');
      menuToggle.classList.toggle('active');
    });
  }
});
