document.getElementById('addUserForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: document.getElementById('newUsername').value,
            password: document.getElementById('newPassword').value,
            full_name: document.getElementById('newFullName').value,
            role: document.getElementById('newRole').value,
        })
    });
    if (res.ok) location.reload();
    else alert((await res.json()).detail || 'Error');
});

document.querySelectorAll('.role-select').forEach(sel => {
    sel.addEventListener('change', async () => {
        const row = sel.closest('tr');
        await fetch(`/api/users/${row.dataset.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: sel.value })
        });
    });
});

document.querySelectorAll('.active-check').forEach(cb => {
    cb.addEventListener('change', async () => {
        const row = cb.closest('tr');
        await fetch(`/api/users/${row.dataset.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: cb.checked ? 1 : 0 })
        });
    });
});

document.querySelectorAll('.del-user').forEach(btn => {
    btn.addEventListener('click', async () => {
        if (!confirm('Delete this user?')) return;
        const row = btn.closest('tr');
        await fetch(`/api/users/${row.dataset.id}`, { method: 'DELETE' });
        row.remove();
    });
});
