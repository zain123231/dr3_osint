<div align="center">

# 🔍 DR3 OSINT

### AI-Powered Digital Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-00d4ff?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-00ff88?style=for-the-badge)]()

**Investigate digital identities across 2,600+ platforms with AI-powered analysis, evidence-based confidence scoring, and professional investigation reports.**

*Not a username checker — a digital investigation platform.*

---

</div>

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI-Powered Analysis** | Gemini AI integration for intelligent identity correlation (with rule-based fallback) |
| 📊 **Confidence Scoring** | Every result has an evidence-based confidence score with explainable reasoning |
| 🔍 **Multi-Stage Pipeline** | 5-stage search pipeline: Preprocessing → Searching → Validating → Analyzing → Reporting |
| 🛡️ **False Positive Reduction** | Multi-layer validation to eliminate incorrect matches |
| 📈 **Cross-Platform Correlation** | Compares profiles across platforms to find shared identities |
| 📋 **Professional Reports** | Investigation reports with Executive Summary, Risk Assessment, and Evidence Analysis |
| ⚡ **Real-Time Updates** | WebSocket-powered live progress during investigations |
| 🌐 **2,600+ Sites** | Database covering social media, forums, coding platforms, and more |
| 🎨 **Premium Dashboard** | Dark-mode cybersecurity dashboard with responsive design |

## 🏗️ Architecture

```
dr3/
├── core/                  # Data models, enums, constants, exceptions
├── search/                # Multi-stage search engine with async HTTP checker
├── intelligence/          # AI analyzer, confidence scorer, cross-platform correlator
├── api/                   # FastAPI backend with WebSocket support
├── web/                   # Frontend SPA (cybersecurity dashboard)
│   ├── static/css/        # Design system
│   └── static/js/         # Application logic
├── reporting/             # Report generation (HTML, PDF, JSON)
├── utils/                 # Helper utilities
└── data/                  # Sites database (3,100+ sites)
```

### System Flow

```
User Input → Pre-processing → Parallel HTTP Checks (2,600+ sites)
    → Validation & False Positive Filtering
    → AI Analysis & Identity Correlation
    → Confidence Scoring (evidence-based)
    → Smart Ranking → Professional Report
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/dr3_osint.git
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

## 📊 Confidence Scoring

Every discovered account receives an **evidence-based confidence score**. No random numbers — every score is justified.

| Score | Level | Meaning |
|-------|-------|---------|
| 90-100% | ✅ Very High | Multiple strong evidence points confirm this account |
| 70-89% | 🟢 High | Strong evidence suggests this account belongs to the target |
| 50-69% | 🟡 Medium | Moderate evidence, manual verification recommended |
| 30-49% | 🟠 Low | Limited evidence, result is uncertain |
| 0-29% | ⚪ Possible | Insufficient evidence, not confirmed |

### Evidence Types & Weights

| Evidence | Weight | Description |
|----------|--------|-------------|
| Exact username match | +30 | Username matches exactly |
| Similar username | +15 | Username is very similar (80%+) |
| Same display name | +20 | Identical display name across platforms |
| Similar bio | +20 | Biography text matches across platforms |
| Same avatar | +25 | Same profile picture detected |
| Same location | +15 | Geographic location matches |
| Platform reliability | +5-10 | Based on platform tier (GitHub, Twitter = Tier 1) |

## 🧠 AI Integration

DR3 OSINT integrates with **Google Gemini API** for intelligent analysis:

- **Cross-Platform Identity Correlation** — AI evaluates whether discovered accounts belong to the same person
- **Risk Assessment** — Automated digital footprint risk evaluation
- **Evidence Synthesis** — AI explains *why* it believes accounts are correlated
- **Investigation Recommendations** — AI suggests next investigation steps

> **Without API key:** The system works perfectly using rule-based analysis. AI is optional but enhances results.

## 📋 Investigation Reports

Each investigation generates a comprehensive report with:

- **Executive Summary** — High-level investigation overview
- **Cross-Platform Analysis** — Patterns across discovered platforms
- **Risk Assessment** — Digital footprint risk level
- **Intelligence Analysis** — AI/rule-based identity correlation analysis
- **Detected Accounts** — All found profiles with confidence scores
- **Evidence Summary** — All supporting evidence
- **Suggested Next Steps** — Recommended follow-up actions

Reports can be exported as **JSON** or **HTML**.

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI (Python) |
| Frontend | Vanilla HTML/CSS/JS (SPA) |
| Search Engine | aiohttp (async) |
| AI Engine | Google Gemini API |
| Real-Time | WebSocket |
| Database | JSON (3,100+ sites) |

## 🔒 Security

- No hardcoded secrets — environment variables for all sensitive data
- Input validation on all user inputs
- CORS configuration
- Graceful error handling with no information leakage
- Rate limiting ready architecture

## 📁 Project Structure

```
dr3_osint/
├── dr3/                    # Main package
│   ├── __init__.py
│   ├── __main__.py         # Entry point
│   ├── config.py           # Central configuration
│   ├── core/               # Models, enums, exceptions, constants
│   ├── search/             # Search engine, HTTP checker, sites DB
│   ├── intelligence/       # AI analyzer, confidence scorer
│   ├── api/                # FastAPI application
│   ├── web/                # Frontend (HTML/CSS/JS)
│   └── data/               # Sites database
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
├── .env.example            # Environment template
└── README.md
```

## 🗺️ Roadmap

- [x] Multi-stage search pipeline
- [x] Evidence-based confidence scoring
- [x] Cross-platform identity correlation
- [x] AI analysis (Gemini integration)
- [x] Real-time WebSocket progress
- [x] Professional investigation reports
- [x] Premium cybersecurity dashboard
- [ ] Profile image comparison (perceptual hashing)
- [ ] Historical search archive
- [ ] CLI mode
- [ ] Docker containerization
- [ ] PDF report export
- [ ] Multi-language support
- [ ] API authentication

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**DR3** — [Telegram](https://t.me/DR3IQ)

---

<div align="center">

**Built with precision for professional OSINT investigations.**

*Quality over quantity. Accuracy over speed. Evidence over assumptions.*

</div>
