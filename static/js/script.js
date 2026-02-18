// Funkce pro přepnutí zobrazení import formuláře
function toggleImport() {
    const form = document.getElementById('importForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

// Funkce pro zobrazení detailu certifikátu
function zobrazitDetail(id) {
    fetch(`/evidence_certifikatu/detail/${id}`)
        .then(response => response.text())
        .then(html => {
            document.querySelector('#detailModal .modal-content').innerHTML = html;
            document.getElementById('detailModal').style.display = 'block';
        });
}

// Funkce pro zavření modálního okna
function closeModal() {
    document.getElementById('detailModal').style.display = 'none';
}

// Funkce pro úpravu certifikátu
function upravitCertifikat(id) {
    fetch(`/evidence_certifikatu/get-edit-form/${id}`)
        .then(response => response.text())
        .then(html => {
            document.querySelector('#detailModal .modal-content').innerHTML = html;
            document.getElementById('detailModal').style.display = 'block';
        });
}

// Funkce pro smazání certifikátu – s 10s undo
// Funkce pro smazání certifikátu – s 10s undo
const pendingDeletes = new Map();

function smazatCertifikat(id) {
    id = String(id);
    if (pendingDeletes.has(id)) return;

    // Find the row and cert name before hiding
    const row = document.querySelector(`tr td.actions .button[onclick*="smazatCertifikat(${id})"], tr td.actions .button[onclick*="smazatCertifikat('${id}')"]`);
    const tr = row ? row.closest('tr') : null;
    const certName = tr ? (tr.children[2]?.textContent || tr.children[0]?.textContent || `#${id}`) : `#${id}`;

    // Hide row immediately
    if (tr) {
        tr.style.transition = 'opacity 0.3s, max-height 0.3s';
        tr.style.opacity = '0';
        setTimeout(() => { tr.style.display = 'none'; }, 300);
    }

    // Build undo toast
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast toast-warning toast-undo';
    toast.innerHTML = `
        <div class="toast-undo-body">
            <i class="fas fa-trash"></i>
            <span>Smazáno: <strong>${certName.trim()}</strong></span>
            <div class="toast-actions">
                <button class="toast-btn confirm" onclick="confirmDelete(${id})">Smazat hned</button>
                <button class="toast-btn" onclick="undoDelete(${id})">Vrátit</button>
            </div>
        </div>
        <div class="toast-progress"><div class="toast-progress-bar"></div></div>
    `;
    if (container) container.appendChild(toast);

    // Start 10s countdown then actually delete
    const timer = setTimeout(() => {
        executeDelete(id);
    }, 10000);

    pendingDeletes.set(id, { timer, toast, tr });
}

function executeDelete(id) {
    id = String(id);
    const pending = pendingDeletes.get(id);
    if (!pending) return;

    clearTimeout(pending.timer);
    pendingDeletes.delete(id);

    if (pending.toast) {
        pending.toast.classList.add('removing');
        setTimeout(() => pending.toast.remove(), 300);
    }

    fetch(`/evidence_certifikatu/smazat/${id}`, { method: 'POST' })
        .then(response => {
            if (response.ok || response.redirected) {
                if (pending.tr) pending.tr.remove();
                if (typeof showToast === 'function') showToast('Certifikát smazán', 'success');
            }
        });
}

function confirmDelete(id) {
    id = String(id);
    executeDelete(id);
}

function undoDelete(id) {
    id = String(id);
    const pending = pendingDeletes.get(id);
    if (!pending) return;

    clearTimeout(pending.timer);
    pendingDeletes.delete(id);

    // Restore the row
    if (pending.tr) {
        pending.tr.style.display = '';
        setTimeout(() => pending.tr.style.opacity = '1', 10);
    }
    if (pending.toast) {
        pending.toast.classList.add('removing');
        setTimeout(() => pending.toast.remove(), 300);
    }
    if (typeof showToast === 'function') showToast('Smazání zrušeno', 'info');
}

// Ensure pending deletes are sent if user navigates away
window.addEventListener('unload', () => {
    pendingDeletes.forEach((val, id) => {
        navigator.sendBeacon(`/evidence_certifikatu/smazat/${id}`);
    });
});

// Funkce pro smazání celé databáze
function smazatDB() {
    if (confirm('Opravdu chcete smazat všechny certifikáty? Tato akce je nevratná!')) {
        fetch('/evidence_certifikatu/smazat-vse', { method: 'POST' })
            .then(response => {
                if (response.ok || response.redirected) {
                    window.location.reload();
                }
            });
    }
}

// Funkce pro zpracování importu
function handleImport(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            const messageDiv = document.getElementById('importMessage');
            messageDiv.textContent = data.message;
            messageDiv.style.display = 'block';

            if (data.success) {
                messageDiv.className = 'import-message success';
                setTimeout(() => window.location.reload(), 2000);
            } else {
                messageDiv.className = 'import-message error';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const messageDiv = document.getElementById('importMessage');
            messageDiv.textContent = 'Došlo k chybě při importu';
            messageDiv.className = 'import-message error';
            messageDiv.style.display = 'block';
        });
}

// Funkce pro zpracování úpravy certifikátu
function handleEdit(event, id) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(`/evidence_certifikatu/upravit/${id}`, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Zavřeme modální okno
                closeModal();

                // Obnovíme tabulku pro aktuální server
                const activeServer = document.querySelector('.nav-item.active');
                if (activeServer) {
                    fetch(`/evidence_certifikatu/get-certificates/${activeServer.dataset.server}`)
                        .then(response => response.json())
                        .then(data => updateTable(data))
                        .catch(error => console.error('Error:', error));
                } else {
                    // Pokud není vybrán server, obnovíme celou stránku
                    window.location.reload();
                }
            } else {
                alert(data.message || 'Došlo k chybě při ukládání změn');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Došlo k chybě při ukládání změn');
        });
}

// Funkce pro automatické skrytí flash zpráv
function setupFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.remove();
            }, 300); // Počkáme na dokončení fade-out animace
        }, 3000); // Zpráva zmizí po 3 sekundách
    });
}

// Event listener pro navigaci serverů
document.addEventListener('DOMContentLoaded', function () {
    setupFlashMessages();
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            const server = this.dataset.server;

            // Aktualizace aktivní třídy
            navItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');

            currentServer = server;

            // Načtení certifikátů pro vybraný server
            fetch(`/evidence_certifikatu/server/${server}`)
                .then(response => response.json())
                .then(data => {
                    updateTable(data);
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        });
    });
});

// Funkce pro aktualizaci tabulky
function updateTable(data) {
    const tbody = document.querySelector('table tbody');
    tbody.innerHTML = '';

    // Podpora pro starý formát (pole) i nový (objekt s pagination)
    const certificates = Array.isArray(data) ? data : (data.items || []);
    const pagination = data.pagination || null;

    if (certificates.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-secondary)">Žádné certifikáty</td></tr>';
    } else {
        certificates.forEach(cert => {
            const row = document.createElement('tr');
            row.className = cert.expiry_class || '';
            row.innerHTML = `
                <td class="col-check">
                    <input type="checkbox" class="cert-check" value="${cert.id}" onchange="updateBulkToolbar()">
                </td>
                <td>${cert.server}</td>
                <td>${cert.cesta}</td>
                <td>${cert.nazev}</td>
                <td>${formatDate(cert.expirace)}</td>
                <td class="actions">
                    <a class="button small info" onclick="zobrazitDetail(${cert.id})" title="Detail">
                        <i class="fas fa-eye"></i>
                    </a>
                    <a class="button small primary" onclick="upravitCertifikat(${cert.id})" title="Upravit">
                        <i class="fas fa-edit"></i>
                    </a>
                    <a class="button small danger" onclick="smazatCertifikat(${cert.id})" title="Smazat">
                        <i class="fas fa-trash"></i>
                    </a>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    // Update pagination
    renderPagination(pagination);
    // Reset bulk toolbar
    deselectAll();
}

function renderPagination(p) {
    const container = document.getElementById('pagination');
    if (!container) return;

    if (!p || p.pages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '';

    // Prev
    if (p.has_prev) {
        html += `<a href="#" class="page-link" onclick="loadPage(${p.prev_num}); return false;"><i class="fas fa-chevron-left"></i> Předchozí</a>`;
    }

    // Numbers
    // Simple logic: 1 ... current-1 current current+1 ... total
    const pages = [];
    pages.push(1);

    let start = Math.max(2, p.page - 2);
    let end = Math.min(p.pages - 1, p.page + 2);

    if (start > 2) pages.push(null); // ellipsis

    for (let i = start; i <= end; i++) {
        pages.push(i);
    }

    if (end < p.pages - 1) pages.push(null); // ellipsis

    if (p.pages > 1) pages.push(p.pages);

    pages.forEach(pg => {
        if (pg === null) {
            html += `<span class="page-ellipsis">…</span>`;
        } else {
            const active = pg === p.page ? 'active' : '';
            html += `<a href="#" class="page-link ${active}" onclick="loadPage(${pg}); return false;">${pg}</a>`;
        }
    });

    // Next
    if (p.has_next) {
        html += `<a href="#" class="page-link" onclick="loadPage(${p.next_num}); return false;">Další <i class="fas fa-chevron-right"></i></a>`;
    }

    container.innerHTML = html;
}

let currentServer = null;

function loadPage(page) {
    const server = currentServer || document.querySelector('.nav-item.active')?.dataset.server;
    if (server) {
        fetch(`/evidence_certifikatu/server/${server}?page=${page}`)
            .then(response => response.json())
            .then(data => updateTable(data));
    } else {
        // Fallback for initial page if we want to support AJAX paging there too
        window.location.href = `?page=${page}`;
    }
}

// Pomocná funkce pro formátování data
function formatDate(dateStr) {
    // Očekáváme formát 'dd.mm.yyyy'
    if (!dateStr) return '';

    // Pokud je datum již ve správném formátu, vrátíme ho
    if (dateStr.includes('.')) {
        return dateStr;
    }

    try {
        // Rozdělíme datum na části
        const parts = dateStr.split('.');
        if (parts.length === 3) {
            return dateStr; // Už je ve správném formátu
        }

        // Pokud není ve formátu s tečkami, zkusíme vytvořit nové datum
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            console.error('Neplatné datum:', dateStr);
            return 'Neplatné datum';
        }

        // Formátování data do českého formátu
        return date.toLocaleDateString('cs-CZ', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    } catch (e) {
        console.error('Chyba při zpracování data:', e);
        return 'Chyba data';
    }
}

/* ─── Fulltext search ─── */
function filterTable(query) {
    const tbody = document.querySelector('.table-container tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    const q = query.toLowerCase().trim();
    rows.forEach(row => {
        if (!q) { row.style.display = ''; return; }
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(q) ? '' : 'none';
    });
}