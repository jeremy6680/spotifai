/**
 * SpotifAI — history.js
 * Client-side logic specific to the /history page.
 * Handles multi-select, delete confirmation modal, and DELETE API call.
 *
 * Loaded only on history.html — no overlap with app.js.
 */

/* ==========================================================================
   1. DOM References
   ========================================================================== */

const historyDom = {
    cards:           document.querySelectorAll('.history-card'),
    checkboxes:      document.querySelectorAll('.history-card__checkbox'),
    selectionBar:    document.getElementById('selection-bar'),
    selectionCount:  document.getElementById('selection-count'),
    selectionLabel:  document.getElementById('selection-label'),
    btnDeselectAll:  document.getElementById('btn-deselect-all'),
    btnDeleteSelected: document.getElementById('btn-delete-selected'),

    // Modal
    modal:           document.getElementById('delete-modal'),
    modalCount:      document.getElementById('modal-count'),
    btnModalCancel:  document.getElementById('btn-modal-cancel'),
    btnModalConfirm: document.getElementById('btn-modal-confirm'),
};

/* ==========================================================================
   2. Selection State
   ========================================================================== */

/**
 * Set of currently selected playlist IDs.
 * Using a Set for O(1) add/delete/has operations.
 */
const selected = new Set();

/* ==========================================================================
   3. Selection Helpers
   ========================================================================== */

/**
 * Update the selection bar visibility and count text.
 * Called after every change to the `selected` Set.
 */
function updateSelectionBar() {
    const count = selected.size;

    if (count === 0) {
        historyDom.selectionBar.classList.remove('is-visible');
        return;
    }

    historyDom.selectionBar.classList.add('is-visible');

    // Update count
    historyDom.selectionCount.textContent = count;

    // Pluralise label
    historyDom.selectionLabel.textContent =
        count === 1 ? ' playlist sélectionnée' : ' playlists sélectionnées';
}

/**
 * Toggle selection state for a given card.
 * Syncs the card's CSS class, the checkbox, and the `selected` Set.
 *
 * @param {HTMLElement} card  - The .history-card article element
 * @param {string}      id    - The playlist UUID (data-id)
 * @param {boolean}     force - If provided, force selected (true) or deselected (false)
 */
function toggleCard(card, id, force) {
    const checkbox = card.querySelector('.history-card__checkbox');
    const shouldSelect = force !== undefined ? force : !selected.has(id);

    if (shouldSelect) {
        selected.add(id);
        card.classList.add('is-selected');
        if (checkbox) checkbox.checked = true;
    } else {
        selected.delete(id);
        card.classList.remove('is-selected');
        if (checkbox) checkbox.checked = false;
    }

    updateSelectionBar();
}

/**
 * Deselect all cards.
 */
function deselectAll() {
    historyDom.cards.forEach((card) => {
        toggleCard(card, card.dataset.id, false);
    });
}

/* ==========================================================================
   4. Modal Helpers
   ========================================================================== */

/**
 * Open the confirmation modal with the correct count in its body.
 */
function openModal() {
    const count = selected.size;
    historyDom.modalCount.textContent =
        count === 1
            ? '1 playlist'
            : `${count} playlists`;

    historyDom.modal.classList.add('is-visible');

    // Focus the cancel button for keyboard accessibility
    // (safer default: user has to actively click Confirm)
    historyDom.btnModalCancel && historyDom.btnModalCancel.focus();
}

/**
 * Close the confirmation modal.
 */
function closeModal() {
    historyDom.modal.classList.remove('is-visible');
}

/* ==========================================================================
   5. Delete Handler
   ========================================================================== */

/**
 * Send DELETE /playlists with the list of selected IDs.
 * On success: remove cards from the DOM with a fade animation.
 */
async function handleDelete() {
    const ids = Array.from(selected);
    if (!ids.length) return;

    // Loading state on the confirm button
    historyDom.btnModalConfirm.classList.add('btn--loading');
    historyDom.btnModalConfirm.disabled = true;

    try {
        const response = await fetch('/playlists', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids }),
        });

        if (!response.ok) {
            // Re-use parseFetchError from app.js (loaded before history.js)
            const msg = typeof parseFetchError === 'function'
                ? await parseFetchError(response)
                : `Erreur ${response.status} lors de la suppression.`;
            if (!msg) return;
            throw new Error(msg);
        }

        closeModal();

        // Remove deleted cards from the DOM with a fade-out animation
        ids.forEach((id) => {
            const card = document.querySelector(`.history-card[data-id="${id}"]`);
            if (!card) return;

            card.style.transition = 'opacity 250ms ease, transform 250ms ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.96)';

            setTimeout(() => {
                card.remove();
                checkEmptyState();
            }, 260);
        });

        selected.clear();
        updateSelectionBar();

    } catch (error) {
        closeModal();
        // Show error in a simple alert — history page doesn't have an alert zone
        alert(error.message || 'Erreur lors de la suppression.');
        console.error('[SpotifAI] Delete error:', error);
    } finally {
        historyDom.btnModalConfirm.classList.remove('btn--loading');
        historyDom.btnModalConfirm.disabled = false;
    }
}

/**
 * Show the empty state if all cards have been deleted.
 */
function checkEmptyState() {
    const remaining = document.querySelectorAll('.history-card');
    if (remaining.length > 0) return;

    const grid = document.querySelector('.history-grid');
    const section = document.querySelector('[aria-label="Historique des playlists générées"]');

    if (section) {
        section.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__icon" aria-hidden="true">♫</div>
        <h2 class="empty-state__title">Aucune playlist pour l'instant</h2>
        <p class="empty-state__text">
          Génère ta première playlist et elle apparaîtra ici.
        </p>
        <a href="/" class="btn btn--primary" style="margin-top: 1.5rem">
          Générer une playlist
        </a>
      </div>
    `;
    }
}

/* ==========================================================================
   6. Event Listeners
   ========================================================================== */

function initHistory() {
    // --- Card click: toggle selection ---
    // We listen on the card but ignore clicks on interactive children
    // (links, buttons) so they keep working normally.
    historyDom.cards.forEach((card) => {
        card.addEventListener('click', (e) => {
            // Let links and buttons handle their own clicks
            if (e.target.closest('a, button')) return;
            toggleCard(card, card.dataset.id);
        });
    });

    // --- Checkbox change: sync with card state ---
    // The checkbox is inside the card, so its click event bubbles up.
    // We stop propagation to avoid double-toggling from the card listener.
    historyDom.checkboxes.forEach((checkbox) => {
        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            const card = checkbox.closest('.history-card');
            toggleCard(card, card.dataset.id, checkbox.checked);
        });

        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });

    // --- Deselect all ---
    if (historyDom.btnDeselectAll) {
        historyDom.btnDeselectAll.addEventListener('click', deselectAll);
    }

    // --- Open delete modal ---
    if (historyDom.btnDeleteSelected) {
        historyDom.btnDeleteSelected.addEventListener('click', openModal);
    }

    // --- Modal: cancel ---
    if (historyDom.btnModalCancel) {
        historyDom.btnModalCancel.addEventListener('click', closeModal);
    }

    // --- Modal: confirm delete ---
    if (historyDom.btnModalConfirm) {
        historyDom.btnModalConfirm.addEventListener('click', handleDelete);
    }

    // --- Modal: close on backdrop click ---
    if (historyDom.modal) {
        historyDom.modal.addEventListener('click', (e) => {
            // Only close if the click was directly on the backdrop, not the modal box
            if (e.target === historyDom.modal) closeModal();
        });
    }

    // --- Keyboard: Escape closes modal ---
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && historyDom.modal.classList.contains('is-visible')) {
            closeModal();
        }
    });
}

/* ==========================================================================
   7. Bootstrap
   ========================================================================== */

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHistory);
} else {
    initHistory();
}
