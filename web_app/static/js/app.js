document.getElementById('themeToggle')?.addEventListener('click', () => {
    const isDark = document.body.classList.toggle('dark');
    document.cookie = `theme=${isDark ? 'dark' : 'light'};path=/;max-age=31536000`;
});

if (document.cookie.includes('theme=dark')) {
    document.body.classList.add('dark');
}
