/**
 * SpotifAI — app.js
 * Client-side logic for playlist generation, results rendering,
 * profile sync, and Spotify save flow.
 *
 * No frameworks, no build step — vanilla JS (ES2020+).
 * Each section is clearly delimited for readability.
 */

/* ==========================================================================
   1. DOM References
   Cache all elements we'll interact with to avoid repeated querySelector calls.
   ========================================================================== */

const dom = {
    // Form
    promptInput: document.getElementById('prompt-input'),
    btnGenerate: document.getElementById('btn-generate'),
    btnSync: document.getElementById('btn-sync'),
    alertZone: document.getElementById('alert-zone'),

    // Generation status
    genStatus: document.getElementById('generation-status'),
    genStep: document.getElementById('generation-step'),

    // Results section
    resultsSection: document.getElementById('results-section'),
    resultsTitle: document.getElementById('results-title'),
    resultsTrackCount: document.getElementById('results-track-count'),
    resultsDate: document.getElementById('results-date'),
    playlistDesc: document.getElementById('playlist-description'),
    trackList: document.getElementById('track-list'),

    // Actions
    btnSave: document.getElementById('btn-save'),
    btnRegenerate: document.getElementById('btn-regenerate'),
    saveBanner: document.getElementById('save-banner'),
    saveBannerLink: document.getElementById('save-banner-link'),

    // Prompt chips
    chips: document.querySelectorAll('.chip'),

    // Sync dot
    syncDot: document.getElementById('sync-dot'),
};

/* ==========================================================================
   2. Application State
   A single object holding all mutable state, avoids scattered globals.
   ========================================================================== */

const state = {
    isGenerating: false,   // API call in progress
    currentPlaylist: null,    // Last generated playlist data object
    currentAudio: null,    // HTMLAudioElement for track previews
    currentTrackEl: null,    // DOM element of the currently playing track
};

/* ==========================================================================
   3. Helper Utilities
   ========================================================================== */

/**
 * Format a duration in milliseconds to "m:ss" string.
 * e.g. 223456 → "3:43"
 * @param {number} ms
 * @returns {string}
 */
function formatDuration(ms) {
    if (!ms || ms <= 0) return '—';
    const totalSec = Math.floor(ms / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = String(totalSec % 60).padStart(2, '0');
    return `${min}:${sec}`;
}

/**
 * Format a UTC date string to a readable locale date.
 * e.g. "2026-03-05T14:23:00" → "5 mars 2026"
 * @param {string} isoString
 * @returns {string}
 */
function formatDate(isoString) {
    if (!isoString) return '—';
    return new Date(isoString).toLocaleDateString('fr-FR', {
        year: 'numeric', month: 'long', day: 'numeric',
    });
}

/**
 * Sanitize a string for safe DOM insertion via textContent.
 * Using textContent (not innerHTML) is inherently safe,
 * but this is a reminder to never use innerHTML with user data.
 * @param {string} str
 * @returns {string}
 */
function sanitize(str) {
    return String(str || '');
}

/**
 * Escape HTML entities for use inside HTML attributes (e.g. alt text).
 * @param {string} str
 * @returns {string}
 */
function escapeAttr(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/* ==========================================================================
   4. Alert / Notification System
   Displays errors and messages inside #alert-zone without page reload.
   ========================================================================== */

/**
 * Show a message in the alert zone.
 * @param {string} message  - Human-readable message
 * @param {'error'|'success'|'info'} type - Alert style
 */
function showAlert(message, type = 'info') {
    if (!dom.alertZone) return;

    dom.alertZone.innerHTML = ''; // Clear previous

    const alert = document.createElement('div');
    alert.className = `alert alert--${type}`;
    alert.setAttribute('role', 'alert');

    // Icon (text-based, no external dep)
    const icons = { error: '✕', success: '✓', info: 'ℹ' };
    const icon = document.createElement('span');
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = icons[type] || 'ℹ';

    const text = document.createElement('span');
    text.textContent = sanitize(message); // textContent is safe — no XSS risk

    alert.appendChild(icon);
    alert.appendChild(text);
    dom.alertZone.appendChild(alert);

    // Auto-dismiss success/info after 5s
    if (type !== 'error') {
        setTimeout(() => clearAlert(), 5000);
    }
}

/**
 * Clear the alert zone.
 */
function clearAlert() {
    if (dom.alertZone) dom.alertZone.innerHTML = '';
}

/* ==========================================================================
   5. Loading / Step Animation
   Updates the status text during the generation pipeline.
   ========================================================================== */

// Steps shown in sequence during generation
// Each step matches roughly what's happening server-side
const GENERATION_STEPS = [
    'Analyse de ta demande…',
    'Chargement de ton profil musical…',
    'Extraction des paramètres via Claude…',
    'Recherche des tracks sur Spotify…',
    'Génération du titre et de la description…',
    'Finalisation…',
];

let stepInterval = null;

/**
 * Start cycling through generation step messages.
 * Uses setInterval to give the illusion of progress.
 */
function startStepAnimation() {
    let index = 0;
    if (dom.genStep) dom.genStep.textContent = GENERATION_STEPS[0];

    stepInterval = setInterval(() => {
        index++;
        if (index < GENERATION_STEPS.length && dom.genStep) {
            dom.genStep.textContent = GENERATION_STEPS[index];
        }
    }, 2200); // Switch every ~2.2s
}

/**
 * Stop the step animation and optionally show a final message.
 * @param {string} [finalMessage]
 */
function stopStepAnimation(finalMessage) {
    clearInterval(stepInterval);
    if (finalMessage && dom.genStep) {
        dom.genStep.textContent = finalMessage;
    }
}

/* ==========================================================================
   6. UI State Management
   Functions that toggle visibility and button states
   ========================================================================== */

/**
 * Show the generation spinner and hide the results section.
 */
function showGenerationStatus() {
    if (dom.genStatus) dom.genStatus.classList.add('is-visible');
    if (dom.resultsSection) dom.resultsSection.classList.remove('is-visible');
    clearAlert();
}

/**
 * Hide the generation spinner.
 */
function hideGenerationStatus() {
    if (dom.genStatus) dom.genStatus.classList.remove('is-visible');
}

/**
 * Show the results section (with animation via CSS).
 */
function showResultsSection() {
    if (dom.resultsSection) dom.resultsSection.classList.add('is-visible');
}

/**
 * Set the generate button to loading state.
 * Disables it and shows spinner via CSS.
 */
function setButtonLoading(loading) {
    if (!dom.btnGenerate) return;

    if (loading) {
        dom.btnGenerate.classList.add('btn--loading');
        dom.btnGenerate.disabled = true;
        dom.btnGenerate.setAttribute('aria-busy', 'true');
    } else {
        dom.btnGenerate.classList.remove('btn--loading');
        dom.btnGenerate.disabled = false;
        dom.btnGenerate.removeAttribute('aria-busy');
    }
}

/* ==========================================================================
   7. Track Rendering
   Builds the track list DOM from API response data.
   ========================================================================== */

/**
 * Render a single track as a <li> element.
 * Option A: each track has an individual link to Spotify.
 *
 * @param {Object} track  - Track object from API response
 * @param {number} index  - 1-based track position
 * @returns {HTMLLIElement}
 */
function renderTrack(track, index) {
    const li = document.createElement('li');
    li.className = 'track-item';
    li.setAttribute('role', 'listitem');

    // Store preview URL as data attribute for the audio player
    if (track.preview_url) {
        li.dataset.previewUrl = track.preview_url;
    }

    // Determine artwork: use provided image or fallback placeholder
    const artSrc = track.album_image || '';
    const artAlt = escapeAttr(`Pochette de l'album ${track.album_name || track.name}`);

    // Duration formatting
    const duration = formatDuration(track.duration_ms);

    // Spotify track URL
    const spotifyUrl = track.external_url || `https://open.spotify.com/track/${track.id}`;

    // Artist string — could be multiple artists
    const artists = Array.isArray(track.artists)
        ? track.artists.join(' · ')
        : (track.artist || '—');

    // Build inner HTML using a template literal.
    // NOTE: all user-facing strings use escapeAttr() for attributes
    // and are set via textContent where possible to prevent XSS.
    // The few places we use innerHTML are constructed from controlled data.
    li.innerHTML = `
    <div class="track-item__index" aria-hidden="true">
      <span class="track-num text-faint text-mono">${index}</span>
      <span class="icon-play" aria-hidden="true">▶</span>
    </div>

    ${artSrc
            ? `<img class="track-item__art"
              src="${escapeAttr(artSrc)}"
              alt="${artAlt}"
              width="48"
              height="48"
              loading="lazy">`
            : `<div class="track-item__art track-item__art--placeholder" aria-hidden="true">♪</div>`
        }

    <div class="track-item__info">
      <span class="track-item__name"></span>
      <span class="track-item__artist"></span>
    </div>

    <div class="track-item__meta">
      ${track.preview_url ? `
        <div class="track-item__preview" aria-hidden="true" title="Preview disponible">
          <span class="preview-bar"></span>
          <span class="preview-bar"></span>
          <span class="preview-bar"></span>
        </div>` : ''
        }
      <span class="track-item__duration text-faint text-mono">${escapeAttr(duration)}</span>
      <a href="${escapeAttr(spotifyUrl)}"
         class="track-item__link"
         target="_blank"
         rel="noopener noreferrer"
         aria-label="Ouvrir ${escapeAttr(track.name)} dans Spotify">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/>
          <line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
      </a>
    </div>
  `;

    // Set text content AFTER innerHTML to safely insert untrusted strings
    // (track name and artist come from Spotify — treat as untrusted)
    li.querySelector('.track-item__name').textContent = sanitize(track.name);
    li.querySelector('.track-item__artist').textContent = sanitize(artists);

    // Click handler for preview audio (if available)
    if (track.preview_url) {
        li.addEventListener('click', (e) => {
            // Don't intercept clicks on the Spotify link itself
            if (e.target.closest('.track-item__link')) return;
            togglePreview(li, track.preview_url);
        });

        li.style.cursor = 'pointer';
        li.setAttribute('role', 'button');
        li.setAttribute('tabindex', '0');
        li.setAttribute('aria-label', `Écouter un aperçu de ${sanitize(track.name)}`);

        // Keyboard support for the preview
        li.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                togglePreview(li, track.preview_url);
            }
        });
    }

    return li;
}

/**
 * Render the full track list.
 * Clears previous results and appends new tracks with staggered animation.
 *
 * @param {Array} tracks  - Array of track objects from API
 */
function renderTrackList(tracks) {
    if (!dom.trackList) return;
    dom.trackList.innerHTML = ''; // Clear previous results

    if (!tracks || tracks.length === 0) {
        const empty = document.createElement('li');
        empty.className = 'empty-state';
        empty.innerHTML = `
      <div class="empty-state__icon" aria-hidden="true">♪</div>
      <p class="empty-state__title text-muted">Aucun track trouvé</p>
      <p class="empty-state__text text-faint">
        Essaie de modifier ta description ou d'élargir les critères.
      </p>
    `;
        dom.trackList.appendChild(empty);
        return;
    }

    // Append each track with a small delay for staggered entrance animation
    tracks.forEach((track, i) => {
        const li = renderTrack(track, i + 1);

        // Stagger using CSS animation-delay
        li.style.animationDelay = `${i * 40}ms`;

        dom.trackList.appendChild(li);
    });
}

/* ==========================================================================
   8. Preview Audio Player
   Plays 30-second Spotify previews inline.
   Only one track plays at a time — clicking another stops the current one.
   ========================================================================== */

/**
 * Toggle preview playback for a track item.
 * If the same track is clicked again, pause it.
 * Otherwise, stop the current and start the new one.
 *
 * @param {HTMLElement} trackEl   - The .track-item element
 * @param {string}      previewUrl - The 30s MP3 preview URL
 */
function togglePreview(trackEl, previewUrl) {
    // Clicking the currently playing track → pause it
    if (state.currentTrackEl === trackEl && state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
        trackEl.classList.remove('is-playing');
        state.currentTrackEl = null;
        return;
    }

    // Stop any currently playing track
    stopCurrentPreview();

    // Create and play new audio
    const audio = new Audio(previewUrl);
    audio.volume = 0.8;

    audio.play().catch((err) => {
        // Browser may block autoplay — silently ignore
        console.warn('[SpotifAI] Preview playback blocked:', err.message);
    });

    audio.addEventListener('ended', () => {
        trackEl.classList.remove('is-playing');
        state.currentAudio = null;
        state.currentTrackEl = null;
    });

    state.currentAudio = audio;
    state.currentTrackEl = trackEl;
    trackEl.classList.add('is-playing');
}

/**
 * Stop and clean up the currently playing preview.
 */
function stopCurrentPreview() {
    if (state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
    }
    if (state.currentTrackEl) {
        state.currentTrackEl.classList.remove('is-playing');
        state.currentTrackEl = null;
    }
}

/* ==========================================================================
   9. Playlist Generation — Main Flow
   Sends prompt to /api/generate, handles loading states and renders results.
   ========================================================================== */

/**
 * Main generation handler.
 * Called when the user clicks "Générer la playlist".
 */
async function handleGenerate() {
    const prompt = dom.promptInput ? dom.promptInput.value.trim() : '';

    // Validation
    if (!prompt) {
        showAlert('Décris ce que tu veux écouter avant de générer.', 'error');
        dom.promptInput && dom.promptInput.focus();
        return;
    }

    if (prompt.length < 5) {
        showAlert('La description est trop courte. Ajoute plus de détails.', 'error');
        dom.promptInput && dom.promptInput.focus();
        return;
    }

    // Stop any playing preview before generating
    stopCurrentPreview();

    // --- Start loading state ---
    state.isGenerating = true;
    setButtonLoading(true);
    showGenerationStatus();
    startStepAnimation();

    try {
        // POST to FastAPI /api/generate
        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // CSRF protection: FastAPI session cookie is sent automatically
                // via credentials: 'same-origin' (default for same-origin fetch)
            },
            body: JSON.stringify({ prompt }),
        });

        // Handle HTTP errors (4xx / 5xx)
        if (!response.ok) {
            let errorMessage = `Erreur ${response.status} du serveur.`;
            try {
                const errData = await response.json();
                if (errData.detail) errorMessage = errData.detail;
            } catch { /* ignore JSON parse error */ }
            throw new Error(errorMessage);
        }

        const data = await response.json();

        // Validate the response shape
        if (!data || !data.tracks || !Array.isArray(data.tracks)) {
            throw new Error('Réponse invalide du serveur. Réessaie.');
        }

        // Store in state for the save flow
        state.currentPlaylist = data;

        // --- Render results ---
        stopStepAnimation('Playlist prête !');

        // Short pause to let the user see the "Playlist prête" message
        await sleep(500);

        hideGenerationStatus();
        renderResults(data);
        showResultsSection();

        // Scroll to results smoothly
        dom.resultsSection && dom.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (error) {
        stopStepAnimation();
        hideGenerationStatus();
        showAlert(error.message || 'Une erreur inattendue est survenue.', 'error');
        console.error('[SpotifAI] Generation error:', error);
    } finally {
        // Always reset loading state
        state.isGenerating = false;
        setButtonLoading(false);
    }
}

/**
 * Render the full results section with playlist metadata and tracks.
 * @param {Object} data - API response object
 */
function renderResults(data) {
    // Playlist title
    if (dom.resultsTitle) {
        dom.resultsTitle.textContent = sanitize(data.title || 'Playlist générée');
    }

    // Track count
    if (dom.resultsTrackCount) {
        dom.resultsTrackCount.textContent = `${data.tracks.length} tracks`;
    }

    // Generation date
    if (dom.resultsDate) {
        dom.resultsDate.textContent = formatDate(data.created_at || new Date().toISOString());
    }

    // Description
    if (dom.playlistDesc) {
        dom.playlistDesc.textContent = sanitize(data.description || '');
    }

    // Track list
    renderTrackList(data.tracks);

    // Hide the save banner (it may be visible from a previous generation)
    if (dom.saveBanner) dom.saveBanner.classList.remove('is-visible');
    if (dom.btnSave) dom.btnSave.disabled = false;
}

/* ==========================================================================
   10. Save to Spotify
   POSTs the current playlist data to /api/save to create it in the user's account.
   ========================================================================== */

/**
 * Handle "Sauvegarder dans Spotify" button click.
 *
 * ADR-009 — Option A: Spotify /playlists/{id}/tracks is blocked in Development
 * mode. We create an empty playlist and return the link. The user adds tracks
 * manually via the individual links in the track list above.
 *
 * Payload: title + description + metadata for DuckDB persistence only.
 * No track URIs sent — adding tracks returns 403 anyway (handled server-side
 * with graceful degradation).
 */
async function handleSave() {
    if (!state.currentPlaylist) {
        showAlert('Génère d\'abord une playlist avant de la sauvegarder.', 'error');
        return;
    }

    if (!dom.btnSave) return;

    // Loading state on the save button
    dom.btnSave.classList.add('btn--loading');
    dom.btnSave.disabled = true;

    try {
        const response = await fetch('/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: state.currentPlaylist.title,
                description: state.currentPlaylist.description,
                // track_count stored in DuckDB for history display — no URIs needed
                track_count: state.currentPlaylist.tracks.length,
                // LLM params + original prompt for DuckDB persistence
                llm_params: state.currentPlaylist.llm_params,
                user_prompt: dom.promptInput ? dom.promptInput.value.trim() : '',
            }),
        });

        if (!response.ok) {
            let msg = `Erreur ${response.status} lors de la sauvegarde.`;
            try {
                const err = await response.json();
                if (err.detail) msg = err.detail;
            } catch { /* ignore */ }
            throw new Error(msg);
        }

        const saved = await response.json();

        // Show the success banner with direct Spotify link
        if (dom.saveBannerLink && saved.spotify_url) {
            dom.saveBannerLink.href = saved.spotify_url;
        }

        if (dom.saveBanner) dom.saveBanner.classList.add('is-visible');

        // Disable the save button — playlist already saved
        dom.btnSave.disabled = true;
        dom.btnSave.classList.remove('btn--loading');

        showAlert('Playlist sauvegardée dans ton compte Spotify !', 'success');

    } catch (error) {
        dom.btnSave.disabled = false;
        dom.btnSave.classList.remove('btn--loading');
        showAlert(error.message || 'Erreur lors de la sauvegarde.', 'error');
        console.error('[SpotifAI] Save error:', error);
    }
}

/* ==========================================================================
   11. Profile Sync
   Calls /api/sync-profile and updates the sync bar.
   ========================================================================== */

/**
 * Handle "Sync mon profil" button click.
 * Triggers a full profile resync from Spotify API.
 */
async function handleSync() {
    if (!dom.btnSync) return;

    dom.btnSync.classList.add('btn--loading');
    dom.btnSync.disabled = true;

    // Update dot to pending state
    if (dom.syncDot) {
        dom.syncDot.className = 'profile-bar__dot profile-bar__dot--pending';
    }

    try {
        const response = await fetch('/sync-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            throw new Error(`Erreur ${response.status} lors de la synchronisation.`);
        }

        // Update sync dot to synced state
        if (dom.syncDot) {
            dom.syncDot.className = 'profile-bar__dot profile-bar__dot--synced';
        }

        // Update the sync date text
        const profileText = document.querySelector('.profile-bar__text');
        if (profileText) {
            const now = new Date().toLocaleDateString('fr-FR', {
                day: 'numeric', month: 'long', year: 'numeric',
            });
            profileText.innerHTML = `Profil musical synchronisé — <strong>${now}</strong>`;
        }

        showAlert('Profil musical synchronisé avec succès.', 'success');

    } catch (error) {
        // Revert dot to default (unsynced) state
        if (dom.syncDot) {
            dom.syncDot.className = 'profile-bar__dot';
        }
        showAlert(error.message || 'Erreur lors de la synchronisation.', 'error');
        console.error('[SpotifAI] Sync error:', error);
    } finally {
        dom.btnSync.classList.remove('btn--loading');
        dom.btnSync.disabled = false;
    }
}

/* ==========================================================================
   12. Prompt Chips — Quick Fill
   Clicking a chip fills the textarea with a preset prompt.
   ========================================================================== */

/**
 * Initialise click handlers on all prompt suggestion chips.
 */
function initChips() {
    dom.chips.forEach((chip) => {
        chip.addEventListener('click', () => {
            const prompt = chip.dataset.prompt;
            if (prompt && dom.promptInput) {
                dom.promptInput.value = prompt;
                dom.promptInput.focus();
                // Auto-resize the textarea to fit the pasted content
                autoResizeTextarea(dom.promptInput);
            }
        });
    });
}

/* ==========================================================================
   13. Textarea Auto-Resize
   Makes the textarea grow with its content instead of scrolling.
   ========================================================================== */

/**
 * Resize a textarea to fit its content.
 * @param {HTMLTextAreaElement} el
 */
function autoResizeTextarea(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
}

/* ==========================================================================
   14. Regenerate
   Runs the generation flow again with the same prompt.
   ========================================================================== */

function handleRegenerate() {
    if (state.isGenerating) return;
    // Stop any playing preview
    stopCurrentPreview();
    // Simply re-trigger generation with the current textarea value
    handleGenerate();
}

/* ==========================================================================
   15. Utility — sleep
   Tiny promise-based delay, used for UI pacing.
   ========================================================================== */

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

/* ==========================================================================
   16. Event Listeners — Wire Everything Together
   ========================================================================== */

/**
 * Attach all event listeners after the DOM is ready.
 */
function init() {
    // --- Generate button ---
    if (dom.btnGenerate) {
        dom.btnGenerate.addEventListener('click', handleGenerate);
    }

    // --- Ctrl+Enter / Cmd+Enter shortcut in textarea ---
    if (dom.promptInput) {
        dom.promptInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                handleGenerate();
            }
        });

        // Auto-resize as user types
        dom.promptInput.addEventListener('input', () => {
            autoResizeTextarea(dom.promptInput);
        });
    }

    // --- Save button ---
    if (dom.btnSave) {
        dom.btnSave.addEventListener('click', handleSave);
    }

    // --- Regenerate button ---
    if (dom.btnRegenerate) {
        dom.btnRegenerate.addEventListener('click', handleRegenerate);
    }

    // --- Profile sync button ---
    if (dom.btnSync) {
        dom.btnSync.addEventListener('click', handleSync);
    }

    // --- Prompt chips ---
    initChips();

    // --- Keyboard hint in form footer ---
    // Show "Ctrl+Entrée" hint once user starts typing
    if (dom.promptInput) {
        dom.promptInput.addEventListener('focus', () => {
            const hint = document.getElementById('track-count-hint');
            if (hint && !hint.dataset.enhanced) {
                hint.textContent += ' · Ctrl+Entrée pour générer';
                hint.dataset.enhanced = '1';
            }
        }, { once: true });
    }
}

/* ==========================================================================
   17. Bootstrap
   Run init() when DOM is ready.
   Using DOMContentLoaded as the script is at the end of <body>,
   but it's good practice to be explicit.
   ========================================================================== */

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init(); // DOM already ready (script deferred or at bottom of body)
}