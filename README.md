<div align="center">

# 🔍 DR3 INTELLIGENCE

### Military-Grade Digital Identity Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-00ff66?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0-00ff66?style=for-the-badge)]()

**Investigate digital identities across 1,195+ platforms with AI-powered analysis, evidence-based confidence scoring, multi-evidence case investigations, and professional intelligence dossiers.**

*Not a username checker — a digital intelligence platform.*

---

</div>

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI-Powered Analysis** | Gemini AI integration for intelligent identity correlation (with rule-based fallback) |
| 📊 **Evidence-Based Confidence** | Every result scored with explainable evidence chains — no random numbers |
| 📋 **Multi-Evidence Cases** | Case Mode: investigate with usernames, emails, phones, websites, locations, known accounts simultaneously |
| 🔗 **Cross-Evidence Correlation** | Auto-correlates emails, websites, and known accounts with discovered profiles |
| 📑 **Intelligence Dossiers** | 7-section professional HTML dossiers with print-ready PDF export |
| 🕸 **Identity Graph** | Cytoscape.js-powered link analysis visualization with neon-glow styling |
| ⚡ **Real-Time WebSocket** | Live investigation progress with terminal log and phase indicators |
| 🎨 **Cyber SOC Interface** | Military-grade dark interface with Matrix rain, HUD overlays, terminal panels |
| 👁️ **Watchlist Monitoring** | Add targets to watchlist for ongoing monitoring |

## 🏗️ Architecture

```
dr3/
├── core/                  # Models, enums, evidence system, constants
├── search/                # Sites database, dorking engine
├── investigation/         # 8-phase orchestrator, seed resolver, identity expander
├── intelligence/          # Confidence engine, evidence engine
├── collectors/            # Platform-specific API collectors (GitHub, Reddit, etc.)
├── graph/                 # Identity graph construction
├── storage/               # SQLite persistence layer
├── reporting/             # Professional dossier generator (HTML/JSON)
├── api/                   # FastAPI + WebSocket endpoints
├── web/                   # Frontend (Cyber SOC dashboard)
│   ├── static/css/        # Military design system
│   ├── static/js/         # App logic, graph viz, Matrix background engine
│   └── index.html         # HUD-enabled SPA
├── timeline/              # Investigation timeline tracking
└── data/                  # Sites database (1,373 sites, 1,195 enabled)
```

### Investigation Pipeline

```
Target Input → Seed Resolution → Identity Expansion → Platform Scanning (1,195 sites)
    → Validation & False Positive Filtering
    → Cross-Platform Correlation → Evidence Scoring
    → AI Analysis (Gemini / Rule-based)
    → Profile Building → Intelligence Dossier
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/zain123231/dr3_osint.git
cd dr3_osint

# Install dependencies
pip install fastapi uvicorn[standard] aiohttp websockets

# (Optional) Install AI support
pip install google-generativeai
```

### Configuration (Optional)

```bash
# Copy environment template
cp .env.example .env

# Add your Gemini API key for AI analysis (optional)
# Edit .env and set: GEMINI_API_KEY=your_api_key_here
```

### Run

```bash
# Start the platform
python -m dr3

# Or specify a custom port
python -m dr3 --port 9000

# Debug mode
python -m dr3 --debug
```

Then open **http://127.0.0.1:8000** in your browser.

### 🏃‍♂️ طريقة التشغيل (بالعربية)

1. افتح موجه الأوامر (Terminal أو CMD) داخل مجلد المشروع.
2. قم بتثبيت المتطلبات (لأول مرة فقط):
   ```bash
   pip install fastapi uvicorn[standard] aiohttp websockets google-generativeai
   ```
3. لتشغيل الأداة، اكتب هذا الأمر:
   ```bash
   python -m dr3
   ```
4. افتح المتصفح على الرابط **http://127.0.0.1:8000**

## 📋 Investigation Modes

### Quick Search
Enter a username, email, or URL in the search console. The platform scans 1,195+ sites and builds an identity profile.

### Case Mode (Multi-Evidence)
Click **◈ CASE MODE** to open the multi-evidence form. Provide:

| Field | Example |
|-------|---------|
| **Case Name** | Target Alpha |
| **Usernames** | dr3, dr3sec, dr3_iq |
| **Emails** | user@example.com |
| **Phone Numbers** | +964XXXXXXXXX |
| **Websites** | https://example.com |
| **Locations** | Iraq, Baghdad |
| **Known Accounts** | github:dr3, twitter:dr3sec |
| **Notes** | Free-text investigator notes |

Cross-correlation automatically boosts confidence: email match +15%, website match +10%, known account +20%.

## 📊 Confidence Scoring

Every discovered account receives an **evidence-based confidence score**.

| Score | Level | Meaning |
|-------|-------|---------|
| 90-100% | ✅ Confirmed | Multiple strong evidence points confirm this account |
| 70-89% | 🟢 High | Strong evidence suggests this account belongs to the target |
| 50-69% | 🟡 Moderate | Moderate evidence, manual verification recommended |
| 30-49% | 🟠 Low | Limited evidence, result is uncertain |
| 0-29% | ⚪ Speculative | Insufficient evidence, not confirmed |

### Evidence Types & Weights

| Evidence | Weight | Description |
|----------|--------|-------------|
| Exact username match | +30 | Username matches exactly |
| Similar username | +15 | Username is very similar (80%+) |
| Same display name | +20 | Identical display name across platforms |
| Similar bio | +20 | Biography text matches across platforms |
| Same avatar | +25 | Same profile picture detected |
| Same location | +15 | Geographic location matches |
| Email match (Case Mode) | +15% | Email found in discovered profile |
| Known account (Case Mode) | +20% | Pre-confirmed account match |
| Website match (Case Mode) | +10% | Website URL matches profile |

## 📑 Intelligence Dossiers

Each investigation generates a 7-section professional dossier:

| Section | Content |
|---------|---------|
| §1 Subject Overview | Target identity, risk badge, confidence bar, stats grid |
| §2 Executive Summary | High-level investigation overview |
| §3 Analysis | AI analysis + cross-platform correlation |
| §4 Confirmed Accounts | Table with platform, username, confidence, tags, links |
| §5 Probable Matches | Lower-confidence matches |
| §6 Evidence Log | All evidence with category, quality, weight |
| §7 Recommended Actions | Suggested next investigation steps |

**Export formats:** HTML Dossier, JSON, PDF (via print), Maltego CSV

## 🧠 AI Integration

DR3 integrates with **Google Gemini API** for intelligent analysis:

- **Cross-Platform Identity Correlation** — AI evaluates whether discovered accounts belong to the same person
- **Risk Assessment** — Automated digital footprint risk evaluation
- **Evidence Synthesis** — AI explains *why* it believes accounts are correlated
- **Investigation Recommendations** — AI suggests next investigation steps

> **Without API key:** The system works perfectly using rule-based analysis. AI is optional but enhances results.

## 🎨 Cyber SOC Interface

The interface is designed to look and feel like **military cyber intelligence software**:

- **Matrix rain background** — 7-layer animated canvas (Japanese/hex characters, binary streams, network constellation, scan lines, ambient glow)
- **Terminal panels** — Every component is a terminal window with LED status indicators
- **HUD overlay** — Corner decorations (CLASSIFIED, ENCRYPTED, SESSION ID, STATUS)
- **Command bar** — Navigation with ONLINE/ENCRYPTED LED indicators
- **Search console** — Terminal prompt (`root@dr3:~$`)
- **Neon-green palette** — `#00ff66` on `#040404` void black
- **Cyber fonts** — Orbitron, JetBrains Mono, Share Tech Mono
- **Glitch animations** — Title glitch effect, scan line sweeps, LED blinking

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI (Python) |
| Frontend | Vanilla HTML/CSS/JS |
| Graph | Cytoscape.js |
| Background | Canvas 2D (7-layer) |
| AI Engine | Google Gemini API |
| Real-Time | WebSocket |
| Storage | SQLite |
| Reports | HTML Dossier Generator |
| Database | JSON (1,373 sites) |

## 🔒 Security

- No hardcoded secrets — environment variables for all sensitive data
- Input validation on all user inputs
- CORS configuration
- Graceful error handling with no information leakage
- Rate limiting ready architecture

## 🗺️ Roadmap

- [x] Multi-stage investigation pipeline
- [x] Evidence-based confidence scoring
- [x] Cross-platform identity correlation
- [x] AI analysis (Gemini integration)
- [x] Real-time WebSocket progress
- [x] Professional intelligence dossiers (7-section HTML)
- [x] PDF export (via print dialog)
- [x] Military Cyber SOC interface
- [x] Matrix rain background engine
- [x] Multi-evidence case investigations
- [x] Cross-evidence correlation engine
- [x] Watchlist monitoring
- [x] Maltego CSV export
- [ ] Profile image comparison (perceptual hashing)
- [ ] Docker containerization
- [ ] API authentication & rate limiting
- [ ] CLI mode

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Zain** — Designed & Engineered

---

<div align="center">

**Built for intelligence analysts. Not for script kiddies.**

*Evidence over assumptions. Accuracy over speed. Intelligence over data.*

</div>
