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
let _pendingDelete = null;

function smazatCertifikat(id) {
    // Find the row and cert name before hiding
    const row = document.querySelector(`tr td.actions .button[onclick*="smazatCertifikat(${id})"], tr td.actions .button[onclick*="smazatCertifikat('${id}')"]`);
    const tr = row ? row.closest('tr') : null;
    const certName = tr ? (tr.children[2]?.textContent || tr.children[0]?.textContent || `#${id}`) : `#${id}`;

    // Cancel any previous pending delete
    if (_pendingDelete) {
        clearTimeout(_pendingDelete.timer);
        if (_pendingDelete.toast) _pendingDelete.toast.remove();
    }

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
            <button class="toast-undo-btn" onclick="undoDelete()">Vrátit zpět</button>
        </div>
        <div class="toast-progress"><div class="toast-progress-bar"></div></div>
    `;
    if (container) container.appendChild(toast);

    // Start 10s countdown then actually delete
    const timer = setTimeout(() => {
        // Actually perform the delete
        fetch(`/evidence_certifikatu/smazat/${id}`, { method: 'POST' })
            .then(response => {
                if (response.ok || response.redirected) {
                    if (tr) tr.remove();
                    if (typeof showToast === 'function') showToast('Certifikát smazán', 'success');
                }
            });
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
        _pendingDelete = null;
    }, 10000);

    _pendingDelete = { id, timer, toast, tr };
}

function undoDelete() {
    if (!_pendingDelete) return;
    clearTimeout(_pendingDelete.timer);
    // Restore the row
    if (_pendingDelete.tr) {
        _pendingDelete.tr.style.display = '';
        _pendingDelete.tr.style.opacity = '1';
    }
    if (_pendingDelete.toast) {
        _pendingDelete.toast.classList.add('removing');
        setTimeout(() => _pendingDelete.toast.remove(), 300);
    }
    if (typeof showToast === 'function') showToast('Smazání zrušeno', 'info');
    _pendingDelete = null;
}

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

            // Načtení certifikátů pro vybraný server
            fetch(`/evidence_certifikatu/get-certificates/${server}`)
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
function updateTable(certificates) {
    const tbody = document.querySelector('table tbody');
    tbody.innerHTML = '';

    certificates.forEach(cert => {
        const row = document.createElement('tr');
        row.className = cert.expiry_class || '';
        row.innerHTML = `
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