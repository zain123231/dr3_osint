/**
 * DR3 OSINT Intelligence Platform — Main Application
 * Handles WebSocket communication, search, and UI rendering.
 */

// ── State ──
const state = {
    ws: null,
    searching: false,
    currentReport: null,
    dbStats: null,
};

// ── DOM Elements ──
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Initialize ──
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    // Search
    $('#search-btn').addEventListener('click', startSearch);
    $('#search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') startSearch();
    });

    // Export buttons
    $('#export-json')?.addEventListener('click', () => exportReport('json'));
    $('#export-html')?.addEventListener('click', () => exportReport('html'));

    // New search button
    $('#new-search')?.addEventListener('click', resetToSearch);
}

// ── Load Stats ──
async function loadStats() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        state.dbStats = data;

        const sitesEl = $('#stat-sites');
        if (sitesEl) sitesEl.textContent = data.sites_enabled?.toLocaleString() || '0';

        const aiEl = $('#stat-ai');
        if (aiEl) {
            aiEl.textContent = data.ai_available ? 'Active' : 'Rules';
            aiEl.className = `stat-value ${data.ai_available ? 'green' : 'amber'}`;
        }
    } catch (e) {
        console.warn('Failed to load stats:', e);
    }
}

// ── Search ──
function startSearch() {
    const input = $('#search-input');
    const username = input.value.trim();
    if (!username || state.searching) return;

    state.searching = true;
    $('#search-btn').disabled = true;

    // Get options
    const topSites = $('#option-sites')?.value || 3000;
    const tags = [];

    // Show progress, hide results
    $('.progress-section').classList.add('active');
    $('.results-section').classList.remove('active');
    $('.hero').style.display = 'none';

    // Connect WebSocket
    connectAndSearch(username, parseInt(topSites), tags);
}

function connectAndSearch(username, topSites, tags) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/search`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        // Send search request
        state.ws.send(JSON.stringify({
            username: username,
            top_sites: topSites,
            tags: tags,
        }));
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showError('Connection error. Please check if the server is running.');
        resetSearch();
    };

    state.ws.onclose = () => {
        if (state.searching) {
            // Unexpected close
            console.warn('WebSocket closed unexpectedly');
        }
    };
}

function handleWSMessage(data) {
    switch (data.type) {
        case 'started':
            updateProgress(0, `Starting investigation for '${data.username}'...`);
            break;

        case 'progress':
            updateProgress(
                data.progress,
                data.message,
                data.checked_sites,
                data.total_sites,
                data.found_count
            );
            break;

        case 'complete':
            state.currentReport = data.report;
            renderResults(data.report);
            resetSearch();
            break;

        case 'error':
            showError(data.error);
            resetSearch();
            break;
    }
}

function updateProgress(percent, message, checked, total, found) {
    const bar = $('.progress-bar-inner');
    const pct = $('.progress-percent');
    const msg = $('.progress-message');

    if (bar) bar.style.width = `${percent}%`;
    if (pct) pct.textContent = `${Math.round(percent)}%`;
    if (msg) msg.textContent = message;

    // Update stats
    if (checked !== undefined) {
        const statsEl = $('.progress-stats');
        if (statsEl) {
            statsEl.innerHTML = `
                <span>Checked: ${checked}/${total || '?'}</span>
                <span>Found: ${found || 0}</span>
            `;
        }
    }
}

function resetSearch() {
    state.searching = false;
    const btn = $('#search-btn');
    if (btn) btn.disabled = false;
    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }
}

function resetToSearch() {
    $('.results-section').classList.remove('active');
    $('.progress-section').classList.remove('active');
    $('.hero').style.display = '';
    $('#search-input').value = '';
    state.currentReport = null;
}

// ── Render Results ──
function renderResults(report) {
    // Hide progress, show results
    $('.progress-section').classList.remove('active');
    $('.results-section').classList.add('active');

    // Update stats bar
    updateResultStats(report);

    // Executive summary
    const summaryEl = $('#exec-summary');
    if (summaryEl) summaryEl.textContent = report.executive_summary;

    // Analysis cards
    renderAnalysis(report);

    // Profile cards
    renderProfiles(report.profiles);

    // Next steps
    renderNextSteps(report.suggested_next_steps);

    // Duration
    const durationEl = $('#search-duration');
    if (durationEl) durationEl.textContent = `${report.duration_seconds}s`;
}

function updateResultStats(report) {
    const set = (id, val) => {
        const el = $(`#result-${id}`);
        if (el) el.textContent = val;
    };

    set('checked', report.total_sites_checked);
    set('found', report.total_found);
    set('confirmed', report.total_confirmed);
    set('confidence', `${Math.round(report.overall_confidence)}%`);
}

function renderAnalysis(report) {
    const grid = $('#analysis-grid');
    if (!grid) return;

    grid.innerHTML = '';

    const cards = [
        { title: 'Cross-Platform Analysis', content: report.cross_platform_analysis },
        { title: 'Risk Assessment', content: report.risk_assessment },
        { title: 'Intelligence Analysis', content: report.ai_analysis },
    ];

    cards.forEach(card => {
        if (!card.content) return;
        const div = document.createElement('div');
        div.className = 'analysis-card animate-fade-in';
        div.innerHTML = `
            <div class="analysis-card-title">${card.title}</div>
            <div class="analysis-card-content">${escapeHtml(card.content)}</div>
        `;
        grid.appendChild(div);
    });
}

function renderProfiles(profiles) {
    const container = $('#profiles-container');
    if (!container) return;

    container.innerHTML = '';

    if (!profiles || profiles.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No accounts found.</p>';
        return;
    }

    profiles.forEach((profile, index) => {
        const levelClass = getConfidenceClass(profile.confidence_level);
        const levelLabel = formatConfidenceLabel(profile.confidence_level);

        // Evidence HTML
        const evidenceHtml = (profile.evidence || []).map(ev =>
            `<div class="evidence-item">
                <span class="evidence-desc">${escapeHtml(ev.description)}</span>
                <span class="evidence-weight">+${ev.weight.toFixed(0)}</span>
            </div>`
        ).join('');

        // Tags HTML
        let tagsHtml = (profile.tags || []).slice(0, 4).map(tag =>
            `<span class="tag">${escapeHtml(tag)}</span>`
        ).join('');

        if (profile.fallback_used) {
            tagsHtml += `<span class="tag" style="background: rgba(168, 85, 247, 0.15); border-color: rgba(168, 85, 247, 0.3); color: var(--accent-purple); font-weight: bold;">⚡ DEEP SEARCH</span>`;
        }

        const card = document.createElement('div');
        card.className = 'profile-card';
        card.style.animationDelay = `${index * 0.05}s`;
        card.innerHTML = `
            <img class="profile-favicon"
                 src="https://www.google.com/s2/favicons?domain=${encodeURIComponent(profile.url)}&sz=64"
                 alt=""
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%231a1f2e%22/><text x=%2216%22 y=%2221%22 text-anchor=%22middle%22 fill=%22%2300d4ff%22 font-size=%2214%22>${profile.site_name[0]}</text></svg>'">
            <div class="profile-main">
                <div class="profile-site-name">${escapeHtml(profile.site_name)}</div>
                <div class="profile-url">${escapeHtml(profile.url)}</div>
                ${tagsHtml ? `<div class="profile-tags">${tagsHtml}</div>` : ''}
            </div>
            <div class="confidence-badge ${levelClass}">
                ${Math.round(profile.confidence_score)}%
                <span class="label">${levelLabel}</span>
            </div>
            <div class="profile-details">
                ${profile.display_name ? `<p><strong>Display Name:</strong> ${escapeHtml(profile.display_name)}</p>` : ''}
                ${profile.bio ? `<p class="profile-bio">"${escapeHtml(profile.bio.substring(0, 200))}"</p>` : ''}
                ${evidenceHtml ? `<div class="evidence-list"><strong style="font-size:0.8rem;color:var(--text-muted)">Evidence:</strong>${evidenceHtml}</div>` : ''}
            </div>
        `;

        // Toggle expand
        card.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') return;
            card.classList.toggle('expanded');
        });

        container.appendChild(card);
    });
}

function renderNextSteps(steps) {
    const container = $('#next-steps-list');
    if (!container || !steps) return;

    container.innerHTML = steps.map(step =>
        `<li>${escapeHtml(step)}</li>`
    ).join('');
}

// ── Export ──
async function exportReport(format) {
    if (!state.currentReport) return;

    const searchId = state.currentReport.search_id;

    if (format === 'json') {
        const blob = new Blob([JSON.stringify(state.currentReport, null, 2)], { type: 'application/json' });
        downloadBlob(blob, `dr3_report_${state.currentReport.target_username}.json`);
    } else if (format === 'html') {
        try {
            const res = await fetch(`/api/report/${searchId}/export?format=html`);
            const html = await res.text();
            const blob = new Blob([html], { type: 'text/html' });
            downloadBlob(blob, `dr3_report_${state.currentReport.target_username}.html`);
        } catch (e) {
            console.error('Export failed:', e);
        }
    }
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// ── Helpers ──
function getConfidenceClass(level) {
    const map = {
        'very_high': 'confidence-very-high',
        'high': 'confidence-high',
        'medium': 'confidence-medium',
        'low': 'confidence-low',
        'possible': 'confidence-possible',
    };
    return map[level] || 'confidence-possible';
}

function formatConfidenceLabel(level) {
    const map = {
        'very_high': 'Confirmed',
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'possible': 'Possible',
    };
    return map[level] || 'Unknown';
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showError(message) {
    const progress = $('.progress-section');
    if (progress) {
        progress.innerHTML = `
            <div class="progress-card" style="border-color: var(--accent-red);">
                <div class="progress-header">
                    <span class="progress-title" style="color: var(--accent-red);">Error</span>
                </div>
                <p class="progress-message" style="color: var(--accent-red);">${escapeHtml(message)}</p>
                <button class="btn" style="margin-top: 1rem;" onclick="resetToSearch()">Try Again</button>
            </div>
        `;
    }
}
