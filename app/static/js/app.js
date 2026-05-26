/* F1 Strategic Analyzer - Client-side JS */

document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');
    if (toggle && links) {
        toggle.addEventListener('click', function () {
            links.classList.toggle('show');
        });
    }
});

async function triggerRefresh(type) {
    try {
        const resp = await fetch('/config/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_type: type })
        });
        const data = await resp.json();
        alert('Refresh ' + (data.status === 'success' ? 'completed' : 'failed') + ': ' + JSON.stringify(data));
        location.reload();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}
