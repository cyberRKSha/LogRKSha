// static/js/theme.js

// This function reads from localStorage and applies the .dark-mode class
export function applyTheme() {
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
}

// This function handles the toggle click, updates localStorage, and applies the theme
export function toggleDarkMode() {
    if (localStorage.getItem('darkMode') === 'enabled') {
        localStorage.setItem('darkMode', 'disabled');
    } else {
        localStorage.setItem('darkMode', 'enabled');
    }
    applyTheme();
}