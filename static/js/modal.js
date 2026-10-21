// Společný kód pro práci s modálními okny
document.addEventListener('DOMContentLoaded', function () {
    // Zavření kliknutím na tlačítko Zavřít nebo křížek
    document.addEventListener('click', function (event) {
        if (event.target.hasAttribute('onclick') &&
            event.target.getAttribute('onclick').includes('closeModal()') ||
            event.target.classList.contains('close')) {
            closeModal();
        }
    });

});

// Funkce pro otevření modálního okna
function openModal(modalId = 'modal') {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        console.log(`Otevírám modální okno s ID: ${modalId}`);
    } else {
        console.error(`Modální okno s ID "${modalId}" nebylo nalezeno`);
    }
}

// Funkce pro zavření modálního okna
function closeModal(modalId) {
    // Pokud není ID modálního okna specifikováno, zkusíme najít všechna viditelná modální okna
    if (!modalId) {
        const modals = document.querySelectorAll('.modal');
        let closed = false;

        modals.forEach(modal => {
            if (modal.style.display === 'block') {
                modal.style.display = 'none';
                console.log(`Zavírám modální okno s ID: ${modal.id}`);
                closed = true;
            }
        });

        if (!closed) {
            // Zkusíme konkrétní ID která používá naše aplikace
            const commonModalIds = ['modal', 'serverModal', 'certifikatModal'];
            for (let id of commonModalIds) {
                const modal = document.getElementById(id);
                if (modal) {
                    modal.style.display = 'none';
                    console.log(`Zavírám modální okno s ID: ${id}`);
                    closed = true;
                    break;
                }
            }
        }

        if (!closed) {
            console.error('Žádné otevřené modální okno nebylo nalezeno');
        }
    } else {
        // Pokud je ID specifikováno, zavřeme pouze to konkrétní modální okno
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            console.log(`Zavírám modální okno s ID: ${modalId}`);
        } else {
            console.error(`Modální okno s ID "${modalId}" nebylo nalezeno`);
        }
    }
}

// Modální okna se zavírají jen křížkem nebo tlačítkem uvnitř okna (Zavřít / Zrušit).
// Kliknutí na pozadí ani klávesa Escape okno nezavře, aby se nepřišlo o rozepsané změny.
