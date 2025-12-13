const form = document.getElementById('login-form');
const errorMessage = document.getElementById('error-message');
form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorMessage.textContent = '';
    const formData = new FormData(form);
    const response = await fetch('/login', { // Changed from /token
        method: 'POST',
        body: formData
    })
    if (response.ok) {
        // The server now handles redirects, so we just follow it.
        window.location.href = response.url;
    } else {
        errorMessage.textContent = 'Incorrect username or password.';
    }
});