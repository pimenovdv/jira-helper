document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/health')
        .then(response => response.json())
        .then(data => {
            const dashboard = document.getElementById('dashboard');
            dashboard.innerHTML = ''; // clear loading

            if (data.status === 'active') {
                data.clients.forEach(client => {
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.innerHTML = `
                        <h3>${client.service}</h3>
                        <p>Status: <span class="${client.status === 'ok' ? 'status-ok' : 'status-error'}">${client.status.toUpperCase()}</span></p>
                        <p>Connection: <code>${client.url || client.uri}</code></p>
                    `;
                    dashboard.appendChild(card);
                });
            } else {
                dashboard.innerHTML = '<p class="status-error">System is down or not properly configured.</p>';
            }
        })
        .catch(err => {
            document.getElementById('dashboard').innerHTML = `<p class="status-error">Error fetching health data: ${err}</p>`;
        });
});
