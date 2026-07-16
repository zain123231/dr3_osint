/**
 * DR3 Intelligence Platform v3.0 — Main Application
 *
 * Intelligence Investigation Dashboard with live graph,
 * evidence tracking, terminal widget, and identity profile building.
 */

// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
const state = {
    ws: null,
    investigating: false,
    currentInvestigation: null,
    graphNodes: [],
    graphEdges: [],
    graphZoom: 1,
    graphOffset: { x: 0, y: 0 },
    selectedNode: null,
    dragging: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ═══════════════════════════════════════════════════════════
// INITIALIZE
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
    if (typeof GraphVisualization !== 'undefined') {
        window.graphVis = new GraphVisualization('graph-canvas');
    }
});

function setupEventListeners() {
    $('#search-btn').addEventListener('click', startInvestigation);
    $('#search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') startInvestigation();
    });
    $('#export-json')?.addEventListener('click', () => exportReport('json'));
    $('#export-html')?.addEventListener('click', () => exportReport('html'));
    $('#export-maltego')?.addEventListener('click', exportMaltego);
    $('#export-pdf')?.addEventListener('click', exportPDF);
    $('#new-search')?.addEventListener('click', resetToSearch);
    $('#save-watchlist')?.addEventListener('click', saveToWatchlist);

    // Graph controls
    $('#graph-zoom-in')?.addEventListener('click', () => { if(window.graphVis && window.graphVis.cy) { window.graphVis.cy.zoom(window.graphVis.cy.zoom() * 1.2); } });
    $('#graph-zoom-out')?.addEventListener('click', () => { if(window.graphVis && window.graphVis.cy) { window.graphVis.cy.zoom(window.graphVis.cy.zoom() / 1.2); } });
    $('#graph-reset')?.addEventListener('click', () => { if(window.graphVis && window.graphVis.cy) { window.graphVis.cy.fit(); } });

    // Case form toggle
    $('#toggle-case-form')?.addEventListener('click', () => {
        const form = $('#case-form-section');
        const btn = $('#toggle-case-form');
        if (form.style.display === 'none') {
            form.style.display = 'block';
            btn.style.background = 'rgba(0, 234, 255, 0.15)';
            btn.style.borderColor = 'var(--accent)';
            btn.style.color = 'var(--accent)';
        } else {
            form.style.display = 'none';
            btn.style.background = '';
            btn.style.borderColor = '';
            btn.style.color = '';
        }
    });

    // Case investigation button
    $('#case-investigate-btn')?.addEventListener('click', startCaseInvestigation);
}

// ═══════════════════════════════════════════════════════════
// LOAD STATS
// ═══════════════════════════════════════════════════════════
async function loadStats() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();

        setTextSafe('stat-sites', data.sites_enabled?.toLocaleString() || '0');
        setTextSafe('stat-platforms', data.sites_enabled?.toLocaleString() || '0');

        const aiText = data.ai_available ? 'Gemini AI' : 'Rule-Based';
        setTextSafe('stat-ai', aiText);
        setTextSafe('stat-ai-status', aiText);

        const aiEl = $('#stat-ai');
        if (aiEl) aiEl.className = `nav-badge ${data.ai_available ? '' : ''}`;

        // Investigation count
        if (data.database_stats) {
            setTextSafe('stat-investigations', data.database_stats.investigations || 0);
        }
    } catch (e) {
        console.warn('Failed to load stats:', e);
    }
}

// ═══════════════════════════════════════════════════════════
// TERMINAL WIDGET
// ═══════════════════════════════════════════════════════════
function terminalLog(message, type = 'info') {
    const body = $('#terminal-body');
    if (!body) return;

    const line = document.createElement('div');
    line.className = 'terminal-line';
    
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false });

    let prefix = '>';
    let color = '#00ff66';
    if (type === 'success') { prefix = '✓'; color = '#00ff66'; }
    if (type === 'warning') { prefix = '⚠'; color = '#ffb000'; }
    if (type === 'error')   { prefix = '✗'; color = '#ff3b3b'; }
    if (type === 'info')    { prefix = '>'; color = '#00eaff'; }
    if (type === 'search')  { prefix = '🔍'; color = '#00eaff'; }
    if (type === 'found')   { prefix = '✓'; color = '#00ff66'; }
    if (type === 'phase')   { prefix = '▸'; color = '#b53cff'; }

    line.innerHTML = `<span class="timestamp">[${time}]</span> <span class="prompt" style="color:${color}">${prefix}</span> ${escapeHtml(message)}`;
    
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;

    // Limit terminal lines to prevent memory bloat
    while (body.children.length > 100) {
        body.removeChild(body.firstChild);
    }
}

function clearTerminal() {
    const body = $('#terminal-body');
    if (body) body.innerHTML = '';
}

// ═══════════════════════════════════════════════════════════
// INVESTIGATION
// ═══════════════════════════════════════════════════════════
function startInvestigation() {
    const input = $('#search-input');
    const query = input.value.trim();
    if (!query || state.investigating) return;

    state.investigating = true;
    state.graphNodes = [];
    state.graphEdges = [];
    $('#search-btn').disabled = true;

    // Show progress, hide others
    $('#progress-section').classList.add('active');
    $('#results-section').classList.remove('active');
    $('#hero-section').style.display = 'none';

    // Reset phase indicators
    $$('.phase-dot').forEach(d => d.classList.remove('active', 'done'));
    $$('.phase-dot')[0]?.classList.add('active');

    // Initialize terminal
    clearTerminal();
    terminalLog('DR3 Intelligence Engine initialized', 'info');
    terminalLog(`Target: ${query}`, 'info');
    terminalLog('Connecting to investigation pipeline...', 'phase');

    connectAndInvestigate(query);
}

// ═══════════════════════════════════════════════════════════
// CASE-BASED INVESTIGATION (Multi-Evidence)
// ═══════════════════════════════════════════════════════════
function startCaseInvestigation() {
    if (state.investigating) return;

    // Collect evidence from form
    const caseName = $('#case-name')?.value.trim() || 'Case Investigation';
    const usernames = splitComma($('#case-usernames')?.value);
    const emails = splitComma($('#case-emails')?.value);
    const phones = splitComma($('#case-phones')?.value);
    const websites = splitComma($('#case-websites')?.value);
    const locations = splitComma($('#case-locations')?.value);
    const knownAccountsRaw = splitComma($('#case-known-accounts')?.value);
    const notes = $('#case-notes')?.value.trim() || '';

    // Parse known_accounts: "github:dr3, twitter:dr3sec" -> {github: 'dr3', twitter: 'dr3sec'}
    const known_accounts = {};
    knownAccountsRaw.forEach(item => {
        const [platform, username] = item.split(':').map(s => s.trim());
        if (platform && username) known_accounts[platform] = username;
    });

    // Validate: at least one evidence field
    if (usernames.length === 0 && emails.length === 0 && phones.length === 0 &&
        websites.length === 0 && Object.keys(known_accounts).length === 0) {
        alert('يرجى إدخال دليل واحد على الأقل (اسم مستخدم، بريد، هاتف، أو حساب معروف).');
        return;
    }

    state.investigating = true;
    state.graphNodes = [];
    state.graphEdges = [];
    $('#case-investigate-btn').disabled = true;
    $('#search-btn').disabled = true;

    // Show progress, hide hero
    $('#progress-section').classList.add('active');
    $('#results-section').classList.remove('active');
    $('#hero-section').style.display = 'none';

    // Reset phase indicators
    $$('.phase-dot').forEach(d => d.classList.remove('active', 'done'));
    $$('.phase-dot')[0]?.classList.add('active');

    // Terminal
    clearTerminal();
    terminalLog('DR3 Case Intelligence Engine initialized', 'info');
    terminalLog(`Case: ${caseName}`, 'info');
    terminalLog(`Evidence: ${usernames.length} usernames, ${emails.length} emails, ${phones.length} phones`, 'info');
    if (Object.keys(known_accounts).length > 0) {
        terminalLog(`Known accounts: ${Object.entries(known_accounts).map(([p,u]) => `${p}:${u}`).join(', ')}`, 'info');
    }
    terminalLog('Connecting to case investigation pipeline...', 'phase');

    // Connect via case WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/investigate-case`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        terminalLog('Connection established — Case Mode', 'success');
        state.ws.send(JSON.stringify({
            case_name: caseName,
            evidence: {
                usernames,
                emails,
                phone_numbers: phones,
                websites,
                locations,
                known_accounts,
                notes,
            }
        }));
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    state.ws.onerror = (error) => {
        console.error('Case WebSocket error:', error);
        terminalLog('Case connection error', 'error');
        showError('خطأ في الاتصال بمحرك التحقيق.');
        resetInvestigation();
        const caseBtn = $('#case-investigate-btn');
        if (caseBtn) caseBtn.disabled = false;
    };

    state.ws.onclose = () => {
        const caseBtn = $('#case-investigate-btn');
        if (caseBtn) caseBtn.disabled = false;
    };
}

function splitComma(str) {
    if (!str) return [];
    return str.split(',').map(s => s.trim()).filter(s => s.length > 0);
}

function connectAndInvestigate(query) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/investigate`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        terminalLog('Connection established', 'success');
        terminalLog('Launching investigation...', 'phase');
        
        state.ws.send(JSON.stringify({
            query: query,
            query_type: 'username',
            max_depth: 3,
            max_nodes: 50,
        }));
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        terminalLog('Connection error — ensure server is running', 'error');
        showError('خطأ في الاتصال. تأكد من تشغيل السيرفر.');
        resetInvestigation();
    };

    state.ws.onclose = () => {
        if (state.investigating) {
            console.warn('WebSocket closed unexpectedly');
        }
    };
}

function handleWSMessage(data) {
    switch (data.type) {
        case 'started':
            updatePhase('seed_resolution');
            updateProgress(2, `بدء التحقيق في '${data.query}'...`);
            terminalLog(`Investigation started: ${data.query}`, 'search');
            break;

        case 'progress':
            if (data.phase) {
                updatePhase(data.phase);
                terminalLog(`Phase: ${formatPhase(data.phase)}`, 'phase');
            }
            if (data.message) {
                terminalLog(data.message, 'info');
            }
            updateProgress(
                data.progress || 0,
                data.message || '',
                data.discovered_nodes || 0,
                data.discovered_edges || 0,
            );
            break;

        case 'complete':
            terminalLog('Investigation complete', 'success');
            terminalLog(`Nodes: ${data.investigation?.node_count || 0} | Edges: ${data.investigation?.edge_count || 0}`, 'success');
            terminalLog('Building intelligence dashboard...', 'phase');
            
            state.currentInvestigation = data.investigation;
            renderInvestigation(data.investigation);
            resetInvestigation();
            break;

        case 'error':
            terminalLog(`Error: ${data.error}`, 'error');
            showError(data.error);
            resetInvestigation();
            break;
    }
}

function formatPhase(phase) {
    const map = {
        'seed_resolution': 'Seed Resolution',
        'identity_expansion': 'Identity Expansion',
        'correlation': 'Correlation Analysis',
        'verification': 'Verification & SNA',
        'ai_analysis': 'AI Analysis',
        'profile_building': 'Profile Building',
        'image_intelligence': 'Image Intelligence',
        'complete': 'Complete',
    };
    return map[phase] || phase;
}

// ═══════════════════════════════════════════════════════════
// INTERACTIVE EXPANSION
// ═══════════════════════════════════════════════════════════
window.expandNode = function(query) {
    if (state.investigating || !state.currentInvestigation) return;

    state.investigating = true;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/investigate`;

    const ws = new WebSocket(wsUrl);

    // Show a mini loading toast or progress indicator
    $('#progress-section').classList.add('active');
    updateProgress(0, `جاري توسيع الشبكة للبحث عن '${query}'...`);
    terminalLog(`Expanding network for: ${query}`, 'search');

    ws.onopen = () => {
        ws.send(JSON.stringify({
            query: query,
            query_type: 'username',
            max_depth: 2,
            max_nodes: 20,
        }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            updateProgress(data.progress || 0, data.message || '');
        } else if (data.type === 'complete') {
            const newInv = data.investigation;
            
            // Merge nodes
            if (newInv.nodes) {
                Object.values(newInv.nodes).forEach(n => {
                    if (!state.currentInvestigation.nodes[n.id]) {
                        state.currentInvestigation.nodes[n.id] = n;
                    }
                });
            }
            
            // Merge edges
            if (newInv.edges) {
                Object.values(newInv.edges).forEach(e => {
                    if (!state.currentInvestigation.edges[e.id]) {
                        state.currentInvestigation.edges[e.id] = e;
                    }
                });
            }
            
            state.currentInvestigation.node_count = Object.keys(state.currentInvestigation.nodes).length;
            
            terminalLog(`Expansion complete: +${Object.keys(newInv.nodes || {}).length} nodes`, 'success');
            renderInvestigation(state.currentInvestigation);
            state.investigating = false;
            $('#progress-section').classList.remove('active');
            ws.close();
        } else if (data.type === 'error') {
            console.error(data.error);
            terminalLog(`Expansion error: ${data.error}`, 'error');
            state.investigating = false;
            $('#progress-section').classList.remove('active');
            ws.close();
        }
    };
    
    ws.onerror = () => {
        state.investigating = false;
        $('#progress-section').classList.remove('active');
    };
}

function updatePhase(phase) {
    const phases = ['seed_resolution', 'identity_expansion', 'correlation', 'verification', 'ai_analysis', 'profile_building', 'image_intelligence'];
    const idx = phases.indexOf(phase);

    $$('.phase-dot').forEach((dot, i) => {
        dot.classList.remove('active');
        if (i < idx) dot.classList.add('done');
        if (i === idx) dot.classList.add('active');
    });
}

function updateProgress(percent, message, nodes, edges) {
    const bar = $('#progress-bar');
    const pct = $('#progress-percent');
    const msg = $('#progress-message');

    if (bar) bar.style.width = `${percent}%`;
    if (pct) pct.textContent = `${Math.round(percent)}%`;
    if (msg) msg.textContent = message;

    if (nodes !== undefined) setTextSafe('live-nodes', nodes);
    if (edges !== undefined) setTextSafe('live-edges', edges);
}

function resetInvestigation() {
    state.investigating = false;
    const btn = $('#search-btn');
    if (btn) btn.disabled = false;
    if (state.ws) { state.ws.close(); state.ws = null; }
}

function resetToSearch() {
    $('#results-section').classList.remove('active');
    $('#progress-section').classList.remove('active');
    $('#hero-section').style.display = '';
    $('#search-input').value = '';
    state.currentInvestigation = null;
    state.graphNodes = [];
    state.graphEdges = [];
}

// ═══════════════════════════════════════════════════════════
// RENDER INVESTIGATION RESULTS
// ═══════════════════════════════════════════════════════════
function renderInvestigation(inv) {
    $('#progress-section').classList.remove('active');
    $('#results-section').classList.add('active');

    // Stats
    setTextSafe('result-checked', inv.total_platforms_checked || 0);
    setTextSafe('result-found', inv.node_count || 0);
    setTextSafe('result-confirmed', inv.confirmed_count || 0);

    const profile = inv.identity_profile;
    const overallConf = profile ? Math.round(profile.overall_confidence) : 0;
    setTextSafe('result-confidence', `${overallConf}%`);

    // Executive summary
    setTextSafe('exec-summary', inv.executive_summary || '');

    // Identity card
    renderIdentityCard(profile, inv);

    // Analysis cards
    renderAnalysis(inv);

    // Graph
    if (window.graphVis) {
        window.graphVis.clear();
        window.graphVis.updateGraph(inv);
        // Force cytoscape to recalculate dimensions after container becomes visible
        setTimeout(() => {
            if (window.graphVis.cy) {
                window.graphVis.cy.resize();
                window.graphVis.cy.fit();
            }
        }, 100);
    }

    // Profiles
    renderProfiles(inv.nodes, inv.seed_node_id);

    // Evidence
    renderEvidence(inv.edges);

    // Next steps
    renderNextSteps(inv.suggested_next_steps);
    
    // Chart and Map
    renderChart(inv);
    renderMap(inv);

    // Image Intelligence
    renderImageIntelligence(inv);

    // Duration
    setTextSafe('search-duration', `${inv.duration_seconds || 0}s`);
}

function renderIdentityCard(profile, inv) {
    const card = $('#identity-card');
    if (!profile || !profile.primary_name) {
        if (card) card.style.display = 'none';
        return;
    }

    card.style.display = '';

    setTextSafe('identity-name', profile.primary_name);

    // Avatar — try to find the best avatar from confirmed nodes
    const avatarEl = $('#identity-avatar');
    if (avatarEl && inv.nodes) {
        const nodes = Object.values(inv.nodes);
        const avatarNode = nodes.find(n => n.avatar_url && n.confidence >= 70);
        if (avatarNode && avatarNode.avatar_url) {
            avatarEl.innerHTML = `<img src="${escapeHtml(avatarNode.avatar_url)}" alt="Profile" onerror="this.parentElement.innerHTML='👤'">`;
        } else {
            avatarEl.innerHTML = '👤';
        }
    }

    // Confidence ring
    const confRing = card.querySelector('.confidence-ring');
    if (confRing) confRing.textContent = `${Math.round(profile.overall_confidence)}%`;

    // Meta info
    const metaEl = $('#identity-meta');
    if (metaEl) {
        let metaParts = [];
        if (profile.known_locations?.length) metaParts.push(`📍 ${profile.known_locations[0]}`);
        if (profile.known_languages?.length) metaParts.push(`🌐 ${profile.known_languages.join(', ')}`);
        if (profile.known_usernames?.length) metaParts.push(`👤 ${profile.known_usernames.slice(0, 3).join(', ')}`);
        if (profile.known_emails?.length) metaParts.push(`📧 ${profile.known_emails[0]}`);
        metaEl.innerHTML = metaParts.map(p => `<span class="identity-meta-item">${escapeHtml(p)}</span>`).join('');
    }

    // Details
    const detailsEl = $('#identity-details');
    if (detailsEl) {
        let html = '';
        if (profile.bio_summary) {
            html += `<div class="profile-bio">"${escapeHtml(profile.bio_summary.substring(0, 300))}"</div>`;
        }
        if (profile.confirmed_platforms?.length) {
            html += '<div class="identity-platforms">';
            html += '<strong>المنصات المؤكدة:</strong> ';
            html += profile.confirmed_platforms.map(p =>
                `<span class="platform-chip confirmed">${escapeHtml(p.platform)} (${p.confidence}%)</span>`
            ).join(' ');
            html += '</div>';
        }
        if (profile.risk_level) {
            html += `<div class="identity-risk"><strong>تقييم المخاطر:</strong> <span class="risk-${profile.risk_level}">${escapeHtml(profile.risk_explanation || profile.risk_level)}</span></div>`;
        }
        if (profile.confidence_explanation) {
            html += `<div class="identity-explanation"><strong>تفسير الثقة:</strong> ${escapeHtml(profile.confidence_explanation)}</div>`;
        }
        detailsEl.innerHTML = html;
    }
}

function renderAnalysis(inv) {
    const grid = $('#analysis-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const cards = [
        { title: 'التحليل عبر المنصات', content: inv.cross_platform_analysis, icon: '🔗' },
        { title: 'تحليل الذكاء الاصطناعي', content: inv.ai_analysis, icon: '🧠' },
        { title: 'تقييم المخاطر', content: inv.risk_assessment, icon: '⚠️' },
    ];

    cards.forEach((card, idx) => {
        if (!card.content) return;
        const div = document.createElement('div');
        div.className = 'analysis-card animate-fade-in';
        div.style.animationDelay = `${idx * 0.1}s`;
        div.innerHTML = `
            <div class="analysis-card-title">${card.icon} ${card.title}</div>
            <div class="analysis-card-content">${escapeHtml(card.content)}</div>
        `;
        grid.appendChild(div);
    });
}

// ═══════════════════════════════════════════════════════════
// PROFILES
// ═══════════════════════════════════════════════════════════
function renderProfiles(nodesObj, seedId) {
    const verifiedContainer = $('#verified-container');
    const possibleContainer = $('#possible-container');
    
    if (verifiedContainer) verifiedContainer.innerHTML = '';
    if (possibleContainer) possibleContainer.innerHTML = '';

    if (!nodesObj || Object.keys(nodesObj).length === 0) {
        if (verifiedContainer) verifiedContainer.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">لم يتم اكتشاف حسابات.</p>';
        if (possibleContainer) possibleContainer.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">لم يتم اكتشاف حسابات.</p>';
        return;
    }

    const nodes = Object.values(nodesObj)
        .filter(n => n.id !== seedId)
        .sort((a, b) => b.confidence - a.confidence);

    const verified = nodes.filter(n => n.confidence >= 70);
    const possible = nodes.filter(n => n.confidence < 70);

    setTextSafe('verified-count', `(${verified.length} حساب)`);
    setTextSafe('possible-count', `(${possible.length} حساب)`);

    const renderNode = (node, index, container) => {
        if (!container) return;
        const levelClass = getConfidenceClass(node.confidence);
        const levelLabel = getConfidenceLabel(node.confidence_level);

        // Evidence from evidence_summary
        let evidenceHtml = '';
        if (node.evidence_summary?.evidence) {
            evidenceHtml = node.evidence_summary.evidence.slice(0, 5).map(ev => {
                const isNeg = ev.category === 'negative';
                return `<div class="evidence-item ${isNeg ? 'negative' : ''}">
                    <span class="evidence-desc">${escapeHtml(ev.description)}</span>
                    <span class="evidence-weight ${isNeg ? 'neg' : ''}">${ev.weight > 0 ? '+' : ''}${ev.weight.toFixed(1)}</span>
                </div>`;
            }).join('');
        }

        // Avatar display: try avatar_url first, then favicon
        let avatarHtml = '';
        if (node.avatar_url) {
            avatarHtml = `
                <div class="profile-avatar-container">
                    <img class="profile-avatar" 
                         src="${escapeHtml(node.avatar_url)}" 
                         alt="${escapeHtml(node.platform)}"
                         loading="lazy"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <img class="profile-favicon" style="display:none;"
                         src="https://www.google.com/s2/favicons?domain=${encodeURIComponent(node.profile_url || '')}&sz=64"
                         alt="" loading="lazy"
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%231a1f2e%22/><text x=%2216%22 y=%2221%22 text-anchor=%22middle%22 fill=%22%2300eaff%22 font-size=%2214%22>${(node.platform || '?')[0]}</text></svg>'">
                </div>`;
        } else {
            avatarHtml = `
                <img class="profile-favicon"
                     src="https://www.google.com/s2/favicons?domain=${encodeURIComponent(node.profile_url || '')}&sz=64"
                     alt="" loading="lazy"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%231a1f2e%22/><text x=%2216%22 y=%2221%22 text-anchor=%22middle%22 fill=%22%2300eaff%22 font-size=%2214%22>${(node.platform || '?')[0]}</text></svg>'">`;
        }

        const card = document.createElement('div');
        card.className = 'profile-card animate-fade-in';
        card.dataset.nodeId = node.id;
        card.style.animationDelay = `${index * 0.04}s`;
        card.innerHTML = `
            ${avatarHtml}
            <div class="profile-main">
                <div class="profile-site-name">${escapeHtml(node.platform)}</div>
                <div class="profile-url"><a href="${escapeHtml(node.profile_url || '#')}" target="_blank" rel="noopener">${escapeHtml(node.profile_url || '')}</a></div>
                ${node.display_name ? `<div class="profile-display-name">${escapeHtml(node.display_name)}</div>` : ''}
                ${node.tags?.length ? `<div class="profile-tags">${node.tags.slice(0,4).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
            </div>
            <div class="confidence-badge ${levelClass}">
                ${Math.round(node.confidence)}%
                <span class="label">${levelLabel}</span>
            </div>
            <div class="profile-details">
                ${node.display_name ? `<p><strong>الاسم:</strong> ${escapeHtml(node.display_name)}</p>` : ''}
                ${node.bio ? `<p class="profile-bio">"${escapeHtml(node.bio.substring(0, 200))}"</p>` : ''}
                ${node.location ? `<p><strong>الموقع:</strong> ${escapeHtml(node.location)}</p>` : ''}
                ${node.email ? `<p><strong>البريد:</strong> ${escapeHtml(node.email)}</p>` : ''}
                ${node.website ? `<p><strong>الموقع:</strong> <a href="${escapeHtml(node.website)}" target="_blank" rel="noopener">${escapeHtml(node.website)}</a></p>` : ''}
                ${node.followers ? `<p><strong>المتابعون:</strong> ${node.followers.toLocaleString()}</p>` : ''}
                ${node.extra_data && node.extra_data.reverse_image ? 
                    `<div class="evidence-list"><strong style="font-size:0.8rem;color:var(--text-muted)">بحث عكسي للصور:</strong>
                    <div style="margin-top: 5px; display: flex; gap: 8px; flex-wrap: wrap;">
                        ${Object.entries(node.extra_data.reverse_image).map(([engine, link]) => `<a href="${link}" target="_blank" rel="noopener" class="tag" style="background:var(--accent-purple); color:#fff; border:none; padding:4px 8px;">${engine}</a>`).join('')}
                    </div></div>` : ''}
                ${evidenceHtml ? `<div class="evidence-list"><strong style="font-size:0.8rem;color:var(--text-muted)">الأدلة:</strong>${evidenceHtml}</div>` : ''}
            </div>
        `;

        card.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') return;
            card.classList.toggle('expanded');
        });

        container.appendChild(card);
    };

    verified.forEach((n, i) => renderNode(n, i, verifiedContainer));
    possible.forEach((n, i) => renderNode(n, i, possibleContainer));
}

// ═══════════════════════════════════════════════════════════
// EVIDENCE LOG
// ═══════════════════════════════════════════════════════════
function renderEvidence(edgesObj) {
    const log = $('#evidence-log');
    if (!log) return;

    if (!edgesObj || Object.keys(edgesObj).length === 0) {
        log.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:1rem;">لا توجد أدلة مسجلة.</p>';
        return;
    }

    const allEvidence = [];
    Object.values(edgesObj).forEach(edge => {
        if (edge.evidence?.evidence) {
            edge.evidence.evidence.forEach(ev => allEvidence.push(ev));
        }
    });

    allEvidence.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));

    log.innerHTML = allEvidence.slice(0, 30).map(ev => {
        const isNeg = ev.category === 'negative';
        const isMissing = ev.category === 'missing';
        const qualityClass = ev.quality || 'moderate';

        return `<div class="evidence-log-item ${isNeg ? 'negative' : ''} ${isMissing ? 'missing' : ''}">
            <div class="evidence-log-main">
                <span class="evidence-quality-badge quality-${qualityClass}">${qualityClass}</span>
                <span class="evidence-log-desc">${escapeHtml(ev.description)}</span>
            </div>
            <div class="evidence-log-weight ${isNeg ? 'neg' : ''}">${ev.weight > 0 ? '+' : ''}${ev.weight?.toFixed(1)}</div>
        </div>`;
    }).join('');
}

function renderNextSteps(steps) {
    const container = $('#next-steps');
    const list = $('#next-steps-list');
    if (!container || !list || !steps?.length) return;

    container.style.display = '';
    list.innerHTML = steps.map(s => `<li>${escapeHtml(s)}</li>`).join('');
}

// ═══════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════
async function exportReport(format) {
    if (!state.currentInvestigation) return;

    const id = state.currentInvestigation.id;

    if (format === 'json') {
        const blob = new Blob([JSON.stringify(state.currentInvestigation, null, 2)], { type: 'application/json' });
        downloadBlob(blob, `dr3_investigation_${id}.json`);
    } else if (format === 'html') {
        try {
            const res = await fetch(`/api/investigations/${id}/report/export?format=html`);
            if (res.ok) {
                const html = await res.text();
                const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
                downloadBlob(blob, `dr3_dossier_${id}.html`);
                terminalLog('HTML dossier exported successfully', 'success');
            } else {
                terminalLog('HTML export failed — investigation may not be saved yet', 'warning');
                // Fallback: export raw JSON
                const blob = new Blob([JSON.stringify(state.currentInvestigation, null, 2)], { type: 'application/json' });
                downloadBlob(blob, `dr3_investigation_${id}.json`);
            }
        } catch (e) {
            console.error('Export failed:', e);
            terminalLog('Export error: ' + e.message, 'error');
        }
    }
}

function exportPDF() {
    if (!state.currentInvestigation) return;

    const id = state.currentInvestigation.id;

    // Fetch the professional dossier HTML and open it for printing
    fetch(`/api/investigations/${id}/report/export?format=html`)
        .then(res => {
            if (!res.ok) throw new Error('Report not available');
            return res.text();
        })
        .then(html => {
            // Open in new window and trigger print
            const printWindow = window.open('', '_blank');
            if (printWindow) {
                printWindow.document.write(html);
                printWindow.document.close();
                // Wait for fonts and styles to load
                setTimeout(() => {
                    printWindow.print();
                }, 1500);
                terminalLog('PDF print dialog opened', 'success');
            }
        })
        .catch(e => {
            console.error('PDF export error:', e);
            terminalLog('PDF export: using fallback screenshot method', 'warning');
            // Fallback: html2pdf on current page
            if (window.html2pdf) {
                const resultsSection = $('#results-section');
                if (!resultsSection) return;
                html2pdf().set({
                    margin: 0.3,
                    filename: `dr3_investigation_${id}.pdf`,
                    image: { type: 'jpeg', quality: 0.95 },
                    html2canvas: { scale: 2, useCORS: true, backgroundColor: '#050505' },
                    jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' }
                }).from(resultsSection).save();
            }
        });
}

function exportMaltego() {
    if (!state.currentInvestigation) return;
    
    let csvContent = "Entity Type,Value,Weight,Source,Target,Link Type\n";
    
    const inv = state.currentInvestigation;
    const nodes = inv.nodes ? Object.values(inv.nodes) : [];
    const edges = inv.edges ? Object.values(inv.edges) : [];
    
    // Add nodes
    nodes.forEach(n => {
        let type = 'maltego.Alias';
        if (n.platform === 'LeakCheck / Breach Data') type = 'maltego.Breach';
        if (n.platform === 'Wayback Machine') type = 'maltego.URL';
        csvContent += `${type},"${n.username}",${n.confidence || 0},"","",""\n`;
    });
    
    // Add edges
    edges.forEach(e => {
        let sourceNode = nodes.find(n => String(n.id) === String(e.source_id));
        let targetNode = nodes.find(n => String(n.id) === String(e.target_id));
        let sType = sourceNode ? sourceNode.platform : 'Unknown';
        let tType = targetNode ? targetNode.platform : 'Unknown';
        csvContent += `maltego.Link,"${sType} to ${tType}",${e.strength || 0},"${e.source_id}","${e.target_id}","${e.type || 'connected_to'}"\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `dr3_maltego_export_${inv.id}.csv`);
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════
function getConfidenceClass(score) {
    if (score >= 90) return 'confidence-very-high';
    if (score >= 70) return 'confidence-high';
    if (score >= 50) return 'confidence-medium';
    if (score >= 30) return 'confidence-low';
    return 'confidence-possible';
}

function getConfidenceLabel(level) {
    const map = {
        'confirmed': 'مؤكد', 'high': 'عالي', 'moderate': 'متوسط',
        'low': 'منخفض', 'speculative': 'تخميني', 'unsubstantiated': 'غير موثق',
    };
    return map[level] || level || 'غير معروف';
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function setTextSafe(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function showError(message) {
    const progress = $('#progress-section');
    if (progress) {
        progress.innerHTML = `
            <div class="progress-card" style="border-color: var(--accent-red);">
                <div class="progress-header">
                    <span class="progress-title" style="color: var(--accent-red);">خطأ</span>
                </div>
                <p class="progress-message" style="color: var(--accent-red);">${escapeHtml(message)}</p>
                <button class="btn" style="margin-top: 1rem;" onclick="resetToSearch()">حاول مرة أخرى</button>
            </div>
        `;
    }
}

// ═══════════════════════════════════════════════════════════
// MAP & CHART RENDERING
// ═══════════════════════════════════════════════════════════
let mapInstance = null;
let chartInstance = null;

function renderChart(inv) {
    const ctx = document.getElementById('confidence-chart');
    if (!ctx) return;
    
    const nodes = inv.nodes ? Object.values(inv.nodes) : [];
    let high = 0, med = 0, low = 0;
    nodes.forEach(n => {
        if(n.confidence >= 70) high++;
        else if(n.confidence >= 40) med++;
        else low++;
    });

    if (chartInstance) chartInstance.destroy();
    
    if (window.Chart) {
        chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['ثقة عالية (High)', 'ثقة متوسطة (Medium)', 'ثقة منخفضة (Low)'],
                datasets: [{
                    data: [high, med, low],
                    backgroundColor: ['#00ff66', '#ffb000', '#ff3b3b'],
                    borderWidth: 0,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { 
                        labels: { 
                            color: '#8b9bb4',
                            font: { family: "'Share Tech Mono', monospace", size: 12 },
                            padding: 15,
                        }
                    }
                },
                cutout: '65%',
            }
        });
    }
}

function renderMap(inv) {
    const container = document.getElementById('map-container');
    if (!container || !window.L) return;
    
    if (!mapInstance) {
        mapInstance = L.map('map-container', {
            zoomControl: true,
            attributionControl: true,
        }).setView([20.0, 0.0], 2);
        
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; CARTO',
            maxZoom: 18,
        }).addTo(mapInstance);
    }
    
    // Clear old markers
    mapInstance.eachLayer(layer => {
        if (layer instanceof L.Marker) {
            mapInstance.removeLayer(layer);
        }
    });

    // Geocode nodes that have location data
    const nodes = inv.nodes ? Object.values(inv.nodes) : [];
    let geocodeDelay = 0;

    nodes.forEach(n => {
        let loc = n.location;
        if (!loc && n.extra_data && n.extra_data.location) loc = n.extra_data.location;
        if (!loc && n.bio) {
            const bioLower = n.bio.toLowerCase();
            const cities = ['london', 'new york', 'paris', 'dubai', 'tokyo', 'riyadh', 'cairo', 'baghdad', 'istanbul', 'berlin', 'moscow'];
            for(let c of cities) {
                if(bioLower.includes(c)) { loc = c; break; }
            }
        }
        
        if (loc) {
            geocodeDelay += 1100; // OpenStreetMap rate limit: 1 req/sec
            setTimeout(() => {
                fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(loc)}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.length > 0) {
                            const lat = parseFloat(data[0].lat);
                            const lon = parseFloat(data[0].lon);
                            
                            // Custom marker with glow effect
                            const icon = L.divIcon({
                                className: 'custom-marker',
                                html: `<div style="
                                    width: 14px; height: 14px;
                                    background: var(--accent, #00eaff);
                                    border-radius: 50%;
                                    box-shadow: 0 0 10px rgba(0,234,255,0.5), 0 0 20px rgba(0,234,255,0.2);
                                    border: 2px solid rgba(255,255,255,0.3);
                                "></div>`,
                                iconSize: [14, 14],
                                iconAnchor: [7, 7],
                            });
                            
                            L.marker([lat, lon], { icon })
                                .addTo(mapInstance)
                                .bindPopup(`<div style="font-family:'Inter',sans-serif;"><b>${escapeHtml(n.platform)}</b><br>${escapeHtml(loc)}<br><span style="color:#888;">Confidence: ${Math.round(n.confidence)}%</span></div>`);
                        }
                    }).catch(e => console.error("Geocoding error:", e));
            }, geocodeDelay);
        }
    });
    
    setTimeout(() => mapInstance.invalidateSize(), 500);
}

// ═══════════════════════════════════════════════════════════
// WATCHLIST
// ═══════════════════════════════════════════════════════════
async function saveToWatchlist() {
    if (!state.currentInvestigation || !state.currentInvestigation.initial_query) {
        alert('لا يوجد تحقيق نشط لحفظه!');
        return;
    }
    
    const query = state.currentInvestigation.initial_query;
    try {
        const res = await fetch('/api/watchlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        
        if (res.ok) {
            alert(`تمت إضافة '${query}' إلى قائمة المراقبة بنجاح!`);
        } else {
            alert('حدث خطأ أثناء الإضافة للمراقبة.');
        }
    } catch (e) {
        console.error(e);
        alert('خطأ في الاتصال بالخادم.');
    }
}

// ═══════════════════════════════════════════════════════════
// IMAGE GEOLOCATION INTELLIGENCE RENDERER v2
// ═══════════════════════════════════════════════════════════
let _imgIntelData = null;  // Global ref for filter/sort

function renderImageIntelligence(inv) {
    const section = $('#image-intelligence-section');
    if (!section) return;

    const imgData = inv.extra_data?.image_intelligence;
    if (!imgData || imgData.total_images_collected === 0) {
        section.style.display = 'none';
        return;
    }

    _imgIntelData = imgData;
    section.style.display = '';

    // Subtitle
    setTextSafe('img-intel-subtitle',
        `${imgData.total_images_collected} images · ${imgData.total_images_analyzed || 0} analyzed`
    );

    // Assessment
    setTextSafe('img-intel-assessment-text', imgData.assessment || '—');

    // ── Geolocation Report Card ──
    const geo = imgData.geolocation;
    if (geo && geo.most_probable_location) {
        const geoCard = $('#geo-report-card');
        if (geoCard) {
            geoCard.style.display = '';
            setTextSafe('geo-location-name', geo.most_probable_location);
            setTextSafe('geo-confidence-value', `${Math.round(geo.most_probable_confidence * 100)}%`);
            setTextSafe('geo-evidence-text', geo.evidence_summary || '');
            setTextSafe('geo-stat-images', geo.total_images || 0);
            setTextSafe('geo-stat-located', geo.total_with_location || 0);
            setTextSafe('geo-stat-landmarks', (geo.repeated_landmarks || []).length);
            setTextSafe('geo-stat-gps', geo.total_with_gps || 0);
        }
    }

    // ── Populate filter dropdowns ──
    _populateFilters(imgData);

    // ── Render Image Gallery ──
    _renderGallery(imgData);

    // ── Interactive Map ──
    _renderGeoMap(imgData);

    // ── Location Distribution ──
    _renderDistribution(imgData);

    // ── Movement Timeline ──
    _renderTimeline(imgData);

    // ── Face Matches ──
    _renderFaceMatches(imgData);

    // ── AI Analysis ──
    _renderAIAnalysis(imgData);

    // ── OCR & Objects ──
    _renderOCRObjects(imgData);

    // ── Correlations ──
    _renderCorrelations(imgData);
}

// ── Gallery Rendering ──
function _renderGallery(imgData) {
    const galleryGrid = $('#img-gallery-grid');
    if (!galleryGrid) return;

    const images = imgData.images || [];
    const analyses = imgData.analyses || [];
    const analysisMap = {};
    analyses.forEach(a => { if (a.image_id) analysisMap[a.image_id] = a; });

    if (images.length === 0) return;
    setTextSafe('img-gallery-count', `${images.length} images`);

    galleryGrid.innerHTML = images.map((img, idx) => {
        const analysis = analysisMap[img.id] || {};
        const locText = analysis.estimated_city || analysis.estimated_country || '';
        const confPct = analysis.location_confidence ? Math.round(analysis.location_confidence * 100) : 0;

        return `
            <div class="img-gallery-card animate-fade-in"
                 data-idx="${idx}" data-platform="${escapeHtml(img.source_platform)}"
                 data-country="${escapeHtml(analysis.estimated_country || '')}"
                 data-confidence="${confPct}" data-date="${escapeHtml(img.date || '')}"
                 onclick="openLightbox(${idx})">
                <span class="img-gallery-type">${escapeHtml(img.source_type)}</span>
                <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.source_platform)}"
                     loading="lazy" onerror="this.style.display='none'">
                <div class="img-gallery-meta">
                    <div class="img-gallery-platform">${escapeHtml(img.source_platform)}</div>
                    <div class="img-gallery-username">@${escapeHtml(img.source_username)}</div>
                    ${locText ? `<div class="img-gallery-location">📍 ${escapeHtml(locText)}</div>` : ''}
                    ${confPct > 0 ? `<div class="img-gallery-confidence">${confPct}% confidence</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function _populateFilters(imgData) {
    const platformSelect = $('#img-filter-platform');
    const countrySelect = $('#img-filter-country');
    if (!platformSelect || !countrySelect) return;

    const platforms = new Set();
    const countries = new Set();
    (imgData.images || []).forEach(img => { if (img.source_platform) platforms.add(img.source_platform); });
    (imgData.analyses || []).forEach(a => { if (a.estimated_country) countries.add(a.estimated_country); });

    platformSelect.innerHTML = '<option value="">All Platforms</option>' +
        [...platforms].map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('');
    countrySelect.innerHTML = '<option value="">All Countries</option>' +
        [...countries].map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
}

// ── Map ──
function _renderGeoMap(imgData) {
    const mapSection = $('#img-map-section');
    const markers = imgData.geolocation?.map_markers || imgData.gps_points || [];
    if (!mapSection || markers.length === 0) return;

    mapSection.style.display = '';
    setTextSafe('img-map-subtitle', `${markers.length} estimated locations`);

    try {
        if (window._imgMap) window._imgMap.remove();
        const mapEl = document.getElementById('img-map-container');
        const map = L.map(mapEl).setView([markers[0].lat, markers[0].lon], 5);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '© CartoDB', maxZoom: 18,
        }).addTo(map);

        const markerGroup = L.featureGroup();
        markers.forEach(m => {
            const popup = `
                <div style="font-family:monospace;font-size:11px;max-width:250px;color:#222;">
                    <div style="margin-bottom:4px;"><img src="${m.image_url}" style="max-width:100%;max-height:120px;border-radius:4px;" onerror="this.style.display='none'"></div>
                    <b>📍 ${m.location || 'Unknown'}</b><br>
                    <b>Platform:</b> ${m.platform}<br>
                    <b>User:</b> @${m.username}<br>
                    <b>Confidence:</b> ${Math.round((m.confidence||0)*100)}%<br>
                    ${(m.reasons||[]).length > 0 ? '<b>Reasons:</b> ' + m.reasons.join(', ') : ''}
                    ${m.post_url ? `<br><a href="${m.post_url}" target="_blank">Open Source</a>` : ''}
                </div>
            `;
            const marker = L.circleMarker([m.lat, m.lon], {
                radius: 8, fillColor: '#00ff66', color: '#00ff66',
                weight: 2, opacity: 0.9, fillOpacity: 0.5,
            }).bindPopup(popup);
            markerGroup.addLayer(marker);
        });
        markerGroup.addTo(map);

        // Fit bounds
        if (markers.length > 1) {
            map.fitBounds(markerGroup.getBounds().pad(0.1));
        }
        window._imgMap = map;
        setTimeout(() => map.invalidateSize(), 200);
    } catch (e) {
        console.warn('Map error:', e);
    }
}

// ── Distribution ──
function _renderDistribution(imgData) {
    const distSection = $('#geo-distribution-section');
    const distGrid = $('#geo-distribution-grid');
    const geo = imgData.geolocation;
    if (!distSection || !distGrid || !geo) return;

    const countries = geo.country_distribution || {};
    const cities = geo.city_distribution || {};
    if (Object.keys(countries).length === 0 && Object.keys(cities).length === 0) return;

    distSection.style.display = '';
    const maxCount = Math.max(...Object.values(countries), ...Object.values(cities), 1);

    let html = '';
    if (Object.keys(countries).length > 0) {
        html += `<div class="geo-dist-card"><div class="geo-dist-card-title">Countries</div>`;
        Object.entries(countries).forEach(([name, count]) => {
            const pct = Math.round((count / maxCount) * 100);
            html += `<div class="geo-dist-bar">
                <span class="geo-dist-bar-label">${escapeHtml(name)}</span>
                <div class="geo-dist-bar-fill"><div class="geo-dist-bar-fill-inner" style="width:${pct}%"></div></div>
                <span class="geo-dist-bar-count">${count}</span>
            </div>`;
        });
        html += `</div>`;
    }
    if (Object.keys(cities).length > 0) {
        html += `<div class="geo-dist-card"><div class="geo-dist-card-title">Cities</div>`;
        Object.entries(cities).forEach(([name, count]) => {
            const pct = Math.round((count / maxCount) * 100);
            html += `<div class="geo-dist-bar">
                <span class="geo-dist-bar-label">${escapeHtml(name)}</span>
                <div class="geo-dist-bar-fill"><div class="geo-dist-bar-fill-inner" style="width:${pct}%"></div></div>
                <span class="geo-dist-bar-count">${count}</span>
            </div>`;
        });
        html += `</div>`;
    }
    distGrid.innerHTML = html;
}

// ── Timeline ──
function _renderTimeline(imgData) {
    const tlSection = $('#movement-timeline-section');
    const tlContainer = $('#movement-timeline');
    const events = imgData.geolocation?.movement_timeline || [];
    if (!tlSection || !tlContainer || events.length === 0) return;

    const withContent = events.filter(e => e.location || e.date);
    if (withContent.length === 0) return;

    tlSection.style.display = '';
    tlContainer.innerHTML = withContent.map(e => `
        <div class="timeline-event animate-fade-in">
            <div class="timeline-event-header">
                <img class="timeline-event-img" src="${escapeHtml(e.image_url)}" alt=""
                     onerror="this.style.display='none'">
                <div>
                    <div class="timeline-event-date">${escapeHtml(e.date ? e.date.split('T')[0] : '—')}</div>
                    <div class="timeline-event-location">📍 ${escapeHtml(e.location || 'Unknown')}</div>
                </div>
                <span class="timeline-event-platform">${escapeHtml(e.platform)}</span>
                ${e.confidence > 0 ? `<span class="timeline-event-confidence">${Math.round(e.confidence*100)}%</span>` : ''}
            </div>
        </div>
    `).join('');
}

// ── Face Matches ──
function _renderFaceMatches(imgData) {
    const faceSection = $('#face-match-section');
    const faceGrid = $('#face-match-grid');
    if (!faceSection || !faceGrid || !imgData.face_matches?.length) return;

    faceSection.style.display = '';
    faceGrid.innerHTML = imgData.face_matches.map(match => {
        const simPct = Math.round(match.similarity * 100);
        const simClass = simPct >= 90 ? 'high' : 'moderate';
        return `
            <div class="face-match-card animate-fade-in">
                <img class="face-match-img" src="${escapeHtml(match.image_a_url)}" onerror="this.style.display='none'">
                <span class="face-match-arrow">⟷</span>
                <img class="face-match-img" src="${escapeHtml(match.image_b_url)}" onerror="this.style.display='none'">
                <div class="face-match-info">
                    <div class="face-match-platforms">${escapeHtml(match.image_a_platform)} ↔ ${escapeHtml(match.image_b_platform)}</div>
                    <div class="face-match-detail">@${escapeHtml(match.image_a_username)} ↔ @${escapeHtml(match.image_b_username)}</div>
                </div>
                <div class="face-match-similarity ${simClass}">${simPct}%</div>
            </div>
        `;
    }).join('');
}

// ── AI Analysis ──
function _renderAIAnalysis(imgData) {
    const aiSection = $('#ai-analysis-section');
    const aiGrid = $('#ai-analysis-grid');
    if (!aiSection || !aiGrid || !imgData.analyses?.length) return;

    const withGeo = imgData.analyses.filter(a =>
        a.description || a.estimated_country || a.landmarks?.length > 0 || a.estimated_city
    );
    if (withGeo.length === 0) return;

    aiSection.style.display = '';
    aiGrid.innerHTML = withGeo.map(analysis => {
        const rows = [];
        if (analysis.description) rows.push(['Description', analysis.description]);
        if (analysis.estimated_country) rows.push(['Country', analysis.estimated_country]);
        if (analysis.estimated_city) rows.push(['City', analysis.estimated_city]);
        if (analysis.estimated_district) rows.push(['District', analysis.estimated_district]);
        if (analysis.location_confidence) rows.push(['Confidence', `${Math.round(analysis.location_confidence*100)}%`]);
        if (analysis.scene_type) rows.push(['Scene', analysis.scene_type]);
        if (analysis.architecture_style) rows.push(['Architecture', analysis.architecture_style]);
        if (analysis.vegetation_type) rows.push(['Vegetation', analysis.vegetation_type]);
        if (analysis.language_detected) rows.push(['Language', analysis.language_detected]);
        if (analysis.weather) rows.push(['Weather', analysis.weather]);
        if (analysis.time_of_day) rows.push(['Time', analysis.time_of_day]);
        if (analysis.season) rows.push(['Season', analysis.season]);
        if (analysis.faces_detected > 0) rows.push(['Faces', `${analysis.faces_detected}`]);
        if (analysis.exif_camera) rows.push(['Camera', analysis.exif_camera]);
        if (analysis.exif_datetime) rows.push(['EXIF Date', analysis.exif_datetime]);

        const reasonsHtml = (analysis.location_reasons || []).length > 0
            ? `<div style="margin-top:4px;font-size:9px;color:var(--text-dim);">
                <b>Reasons:</b> ${analysis.location_reasons.slice(0,5).map(r => escapeHtml(r)).join(', ')}
               </div>` : '';

        return `
            <div class="ai-analysis-card animate-fade-in">
                <div class="ai-analysis-card-header">
                    <img src="${escapeHtml(analysis.image_url)}" alt="" onerror="this.style.display='none'">
                    <div>
                        <div class="ai-analysis-card-title">${escapeHtml(analysis.source_platform)}</div>
                        <div class="ai-analysis-card-subtitle">@${escapeHtml(analysis.source_username)}</div>
                    </div>
                </div>
                ${rows.map(([k,v]) => `<div class="ai-analysis-row"><span class="ai-analysis-key">${escapeHtml(k)}</span><span class="ai-analysis-val">${escapeHtml(String(v))}</span></div>`).join('')}
                ${reasonsHtml}
            </div>
        `;
    }).join('');
}

// ── OCR & Objects ──
function _renderOCRObjects(imgData) {
    const ocrSection = $('#ocr-objects-section');
    const ocrGrid = $('#ocr-objects-grid');
    if (!ocrSection || !ocrGrid) return;

    const hasOcr = imgData.all_ocr_text?.length > 0;
    const hasObj = imgData.all_objects?.length > 0;
    const hasLandmarks = imgData.all_landmarks?.length > 0;
    if (!hasOcr && !hasObj && !hasLandmarks) return;

    ocrSection.style.display = '';
    let cards = '';
    if (hasLandmarks) {
        cards += `<div class="ai-analysis-card animate-fade-in"><div class="analysis-card-title">◈ Landmarks</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">
                ${imgData.all_landmarks.map(l => `<span class="tag" style="border-color:rgba(0,229,255,0.2);color:var(--cyan)">${escapeHtml(l)}</span>`).join('')}
            </div></div>`;
    }
    if (hasOcr) {
        cards += `<div class="ai-analysis-card animate-fade-in"><div class="analysis-card-title">◈ OCR Text</div>
            ${imgData.all_ocr_text.map(t => `<div class="ai-analysis-row"><span class="ai-analysis-val" style="max-width:100%">${escapeHtml(t)}</span></div>`).join('')}
            </div>`;
    }
    if (hasObj) {
        cards += `<div class="ai-analysis-card animate-fade-in"><div class="analysis-card-title">◈ Objects</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">
                ${imgData.all_objects.map(o => `<span class="tag">${escapeHtml(o)}</span>`).join('')}
            </div></div>`;
    }
    ocrGrid.innerHTML = cards;
}

// ── Correlations ──
function _renderCorrelations(imgData) {
    const corrSection = $('#img-correlations-section');
    const corrLog = $('#img-correlations-log');
    if (!corrSection || !corrLog || !imgData.correlations?.length) return;

    corrSection.style.display = '';
    corrLog.innerHTML = imgData.correlations.map(corr => {
        const typeColor = {
            'face_match': 'var(--neon)', 'location_match': 'var(--cyan)',
            'text_match': 'var(--amber)', 'timeline_match': 'var(--purple)',
        }[corr.type] || 'var(--text-muted)';
        const confPct = Math.round((corr.confidence||0) * 100);
        return `
            <div class="evidence-item animate-fade-in">
                <span class="evidence-type positive" style="border-color:${typeColor};color:${typeColor}">
                    ${escapeHtml((corr.type||'').replace('_', ' '))}
                </span>
                <span class="evidence-desc">${escapeHtml(corr.description)}</span>
                <span class="evidence-weight positive" style="color:${typeColor}">${confPct}%</span>
            </div>
        `;
    }).join('');
}

// ── Lightbox ──
window.openLightbox = function(idx) {
    const imgData = _imgIntelData;
    if (!imgData) return;
    const img = (imgData.images || [])[idx];
    if (!img) return;

    const analysisMap = {};
    (imgData.analyses || []).forEach(a => { if (a.image_id) analysisMap[a.image_id] = a; });
    const analysis = analysisMap[img.id] || {};

    const lightbox = $('#img-lightbox');
    const lbImage = $('#lightbox-image');
    const sidebar = $('#lightbox-sidebar');
    if (!lightbox || !lbImage || !sidebar) return;

    lbImage.src = img.url;
    lightbox.style.display = 'flex';

    // Build sidebar
    let html = '';
    html += `<div class="lightbox-section-title">Source</div>`;
    html += `<div class="lightbox-row"><span class="lightbox-key">Platform</span><span class="lightbox-val">${escapeHtml(img.source_platform)}</span></div>`;
    html += `<div class="lightbox-row"><span class="lightbox-key">User</span><span class="lightbox-val">@${escapeHtml(img.source_username)}</span></div>`;
    html += `<div class="lightbox-row"><span class="lightbox-key">Type</span><span class="lightbox-val">${escapeHtml(img.source_type)}</span></div>`;
    if (img.date) html += `<div class="lightbox-row"><span class="lightbox-key">Date</span><span class="lightbox-val">${escapeHtml(img.date.split('T')[0])}</span></div>`;
    if (img.caption) html += `<div class="lightbox-row"><span class="lightbox-key">Caption</span><span class="lightbox-val">${escapeHtml(img.caption.substring(0,100))}</span></div>`;
    if (img.post_url) html += `<div class="lightbox-row"><span class="lightbox-key">Source</span><span class="lightbox-val"><a href="${escapeHtml(img.post_url)}" target="_blank" style="color:var(--cyan)">Open ↗</a></span></div>`;

    if (analysis.estimated_country || analysis.estimated_city) {
        html += `<div class="lightbox-section-title">Location Estimate</div>`;
        if (analysis.estimated_country) html += `<div class="lightbox-row"><span class="lightbox-key">Country</span><span class="lightbox-val">${escapeHtml(analysis.estimated_country)}</span></div>`;
        if (analysis.estimated_state) html += `<div class="lightbox-row"><span class="lightbox-key">State</span><span class="lightbox-val">${escapeHtml(analysis.estimated_state)}</span></div>`;
        if (analysis.estimated_city) html += `<div class="lightbox-row"><span class="lightbox-key">City</span><span class="lightbox-val">${escapeHtml(analysis.estimated_city)}</span></div>`;
        if (analysis.estimated_district) html += `<div class="lightbox-row"><span class="lightbox-key">District</span><span class="lightbox-val">${escapeHtml(analysis.estimated_district)}</span></div>`;
        if (analysis.location_confidence) html += `<div class="lightbox-row"><span class="lightbox-key">Confidence</span><span class="lightbox-val" style="color:var(--neon)">${Math.round(analysis.location_confidence*100)}%</span></div>`;
        if (analysis.estimated_coords) html += `<div class="lightbox-row"><span class="lightbox-key">Coords</span><span class="lightbox-val">${analysis.estimated_coords.lat}, ${analysis.estimated_coords.lon}</span></div>`;
    }

    if (analysis.location_reasons?.length > 0) {
        html += `<div class="lightbox-section-title">Reasons</div>`;
        analysis.location_reasons.forEach(r => { html += `<div class="lightbox-tag">${escapeHtml(r)}</div>`; });
    }

    if (analysis.description || analysis.scene_type) {
        html += `<div class="lightbox-section-title">Visual Analysis</div>`;
        if (analysis.description) html += `<div class="lightbox-row"><span class="lightbox-key">Desc</span><span class="lightbox-val">${escapeHtml(analysis.description.substring(0,120))}</span></div>`;
        if (analysis.scene_type) html += `<div class="lightbox-row"><span class="lightbox-key">Scene</span><span class="lightbox-val">${escapeHtml(analysis.scene_type)}</span></div>`;
        if (analysis.architecture_style) html += `<div class="lightbox-row"><span class="lightbox-key">Architecture</span><span class="lightbox-val">${escapeHtml(analysis.architecture_style)}</span></div>`;
        if (analysis.weather) html += `<div class="lightbox-row"><span class="lightbox-key">Weather</span><span class="lightbox-val">${escapeHtml(analysis.weather)}</span></div>`;
        if (analysis.language_detected) html += `<div class="lightbox-row"><span class="lightbox-key">Language</span><span class="lightbox-val">${escapeHtml(analysis.language_detected)}</span></div>`;
    }

    if (analysis.landmarks?.length > 0) {
        html += `<div class="lightbox-section-title">Landmarks</div>`;
        analysis.landmarks.forEach(l => { html += `<div class="lightbox-tag" style="border-color:rgba(0,229,255,0.2);color:var(--cyan)">${escapeHtml(l)}</div>`; });
    }

    if (analysis.ocr_text?.length > 0) {
        html += `<div class="lightbox-section-title">OCR Text</div>`;
        analysis.ocr_text.forEach(t => { html += `<div class="lightbox-tag">${escapeHtml(t)}</div>`; });
    }

    if (analysis.objects?.length > 0) {
        html += `<div class="lightbox-section-title">Objects</div>`;
        analysis.objects.forEach(o => { html += `<div class="lightbox-tag">${escapeHtml(o)}</div>`; });
    }

    if (analysis.exif_camera || analysis.exif_datetime || analysis.exif_gps) {
        html += `<div class="lightbox-section-title">EXIF Data</div>`;
        if (analysis.exif_camera) html += `<div class="lightbox-row"><span class="lightbox-key">Camera</span><span class="lightbox-val">${escapeHtml(analysis.exif_camera)}</span></div>`;
        if (analysis.exif_datetime) html += `<div class="lightbox-row"><span class="lightbox-key">Date</span><span class="lightbox-val">${escapeHtml(analysis.exif_datetime)}</span></div>`;
        if (analysis.exif_gps) html += `<div class="lightbox-row"><span class="lightbox-key">GPS</span><span class="lightbox-val">${analysis.exif_gps.lat}, ${analysis.exif_gps.lon}</span></div>`;
    }

    sidebar.innerHTML = html;
};

window.closeLightbox = function(event) {
    const lightbox = $('#img-lightbox');
    if (lightbox) lightbox.style.display = 'none';
};

// ── View Toggle ──
window.setImgView = function(mode) {
    const grid = $('#img-gallery-grid');
    if (!grid) return;
    if (mode === 'list') {
        grid.classList.add('list-view');
        $('#img-view-grid')?.classList.remove('active');
        $('#img-view-list')?.classList.add('active');
    } else {
        grid.classList.remove('list-view');
        $('#img-view-grid')?.classList.add('active');
        $('#img-view-list')?.classList.remove('active');
    }
};

// ── Filter ──
window.filterImages = function() {
    const platform = $('#img-filter-platform')?.value || '';
    const country = $('#img-filter-country')?.value || '';
    const cards = $$('#img-gallery-grid .img-gallery-card');
    cards.forEach(card => {
        const cPlatform = card.dataset.platform || '';
        const cCountry = card.dataset.country || '';
        const showP = !platform || cPlatform === platform;
        const showC = !country || cCountry === country;
        card.style.display = (showP && showC) ? '' : 'none';
    });
};

// ── Sort ──
window.sortImages = function() {
    const sortBy = $('#img-sort')?.value || 'confidence';
    const grid = $('#img-gallery-grid');
    if (!grid) return;
    const cards = [...grid.querySelectorAll('.img-gallery-card')];
    cards.sort((a, b) => {
        if (sortBy === 'confidence') return (parseInt(b.dataset.confidence)||0) - (parseInt(a.dataset.confidence)||0);
        if (sortBy === 'date') return (b.dataset.date||'').localeCompare(a.dataset.date||'');
        if (sortBy === 'platform') return (a.dataset.platform||'').localeCompare(b.dataset.platform||'');
        return 0;
    });
    cards.forEach(c => grid.appendChild(c));
};

// ESC to close lightbox
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});

