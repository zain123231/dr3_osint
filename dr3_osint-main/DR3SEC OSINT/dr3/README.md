<div align="center">

# 🔍 DR3SEC OSINT

### **Advanced Username Intelligence & Digital Footprint Analyzer**

<img src="photo_2025-06-15_16-30-17.jpg" height="280"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.5.0a1-FF4500?style=for-the-badge)](https://github.com/DR3SEC/dr3)
[![License](https://img.shields.io/badge/License-MIT-00C853?style=for-the-badge)](LICENSE)
[![Sites](https://img.shields.io/badge/Sites-3000+-7C4DFF?style=for-the-badge)](sites.md)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Dockerfile)

**Collect a complete dossier on any person by username only — scanning 3000+ websites, extracting personal data, and mapping digital footprints across the internet.**

*A powerful fork of [Maigret](https://github.com/soxoj/maigret) by [Sherlock Project](https://github.com/sherlock-project/sherlock), enhanced and maintained by **DR3SEC**.*

---

</div>

## 📋 Table of Contents

- [About](#-about)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Usage](#-usage)
- [Web Interface](#-web-interface)
- [Output Reports](#-output-reports)
- [CLI Reference](#-cli-reference)
- [Project Structure](#-project-structure)
- [Docker](#-docker)
- [Contributing](#-contributing)
- [Disclaimer](#-disclaimer)
- [License](#-license)

---

## 🎯 About

**DR3SEC OSINT** is a command-line intelligence tool that builds a comprehensive digital dossier on a target using **only a username**. It searches across **3,000+ websites** simultaneously, extracts personal information from profile pages, discovers linked accounts, and generates detailed reports in multiple formats.

No API keys are required. The tool uses direct HTTP requests with intelligent detection of account presence through response analysis, page parsing, and error detection.

### How It Works

```
                    ┌─────────────┐
                    │  Username   │
                    │   Input     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  DR3SEC     │
                    │  Engine     │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
   │  3000+ Site │ │   Profile   │ │  Recursive  │
   │   Scanner   │ │   Parser    │ │  ID Search  │
   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Reports   │
                    │ HTML/PDF/   │
                    │ CSV/XMind   │
                    └─────────────┘
```

---

## ⚡ Key Features

| Feature | Description |
|---|---|
| 🌐 **3000+ Sites** | Scans social media, forums, dating sites, tech platforms, and more |
| 🔄 **Recursive Search** | Discovers new usernames from found profiles and searches those too |
| 📊 **Profile Parsing** | Extracts personal info, bios, links, and connected accounts |
| 🏷️ **Tag Filtering** | Filter searches by category (social, dating, photo, etc.) or country |
| 🌍 **Tor & I2P Support** | Search through `.onion` and `.i2p` sites via proxy |
| 🛡️ **Anti-Detection** | Handles CAPTCHAs, rate limits, and censorship with smart retries |
| 📄 **Multi-Format Reports** | Export to HTML, PDF, CSV, XMind, JSON, and TXT |
| 🔗 **Graph Visualization** | Interactive network graph showing account relationships |
| 🌐 **Web Interface** | Built-in Flask web UI for browser-based searches |
| 🐳 **Docker Ready** | One-command deployment via Docker |
| 🔍 **URL Parsing** | Extract usernames and IDs from any profile URL |
| 🔀 **Username Permutation** | Generate and test variations of usernames |

---

## 🚀 Installation

### Prerequisites

- **Python 3.10+** (Python 3.11 recommended)
- **pip** package manager

### Method 1: pip Install (Recommended)

```bash
pip install .
```

### Method 2: Clone & Install

```bash
git clone https://github.com/DR3SEC/dr3.git
cd dr3
pip install .
```

### Method 3: Windows Installer

Double-click `Installer.bat` and follow the on-screen instructions. Requires administrator privileges.

### Method 4: Docker

```bash
# Build the image
docker build -t dr3sec .

# Run a search
docker run -v /mydir:/app/reports dr3sec username --html
```

---

## ▶️ Usage

### Basic Search

```bash
# Search for a single username
dr3 username

# Search for multiple usernames
dr3 user1 user2 user3

# Search across ALL 3000+ sites (default: top 500)
dr3 username -a
```

### Filtered Search

```bash
# Search only on sites tagged as "social"
dr3 username --tags social

# Search only on sites tagged with country "us"
dr3 username --tags us

# Search on specific sites only
dr3 username --site Instagram --site Twitter --site GitHub

# Search by tags: photo & dating
dr3 username --tags photo,dating
```

### Report Generation

```bash
# Generate HTML report (interactive, with graphs)
dr3 username --html

# Generate PDF report
dr3 username --pdf

# Generate CSV report
dr3 username --csv

# Generate XMind mind map
dr3 username --xmind

# Generate all report types
dr3 username --html --pdf --csv
```

### Advanced Options

```bash
# Use a proxy (SOCKS5/HTTP)
dr3 username --proxy socks5://127.0.0.1:1080

# Search through Tor network
dr3 username --tor-proxy socks5://127.0.0.1:9050

# Search through I2P network
dr3 username --i2p-proxy http://127.0.0.1:4444

# Parse a URL to extract usernames, then search
dr3 --parse https://example.com/profile/user123

# Enable domain checking (experimental)
dr3 username --with-domains

# Set custom timeout (default: 30s)
dr3 username --timeout 60

# Control concurrent connections
dr3 username --max-connections 100

# Disable recursive search
dr3 username --no-recursion

# Print sites where username was NOT found
dr3 username --print-not-found

# Permute usernames to find variations
dr3 user1 user2 --permute

# Show database statistics
dr3 --stats
```

---

## 🌐 Web Interface

DR3SEC includes a built-in web interface powered by Flask:

```bash
# Launch web UI on default port 5000
dr3 --web

# Launch on custom port
dr3 --web 8080
```

Then open `http://127.0.0.1:5000` in your browser.

**Features:**
- Enter usernames through a clean web form
- View results as an interactive network graph
- Browse found accounts in a searchable table
- Download reports (HTML, PDF, CSV) directly

---

## 📊 Output Reports

| Format | Command | Description |
|---|---|---|
| **HTML** | `--html` | Interactive report with graphs, links, and extracted data |
| **PDF** | `--pdf` | Printable formatted report |
| **CSV** | `--csv` | Spreadsheet-compatible data export |
| **XMind** | `--xmind` | Mind map visualization (XMind 8 compatible) |
| **JSON** | `--json` | Machine-readable structured data |
| **TXT** | `--txt` | Plain text summary |
| **Graph** | `--graph` | Interactive network graph (HTML + PyVis) |

Reports are saved to the `reports/` directory by default. Use `--folderoutput PATH` to change the output directory.

---

## 📖 CLI Reference

```
dr3 [USERNAMES] [OPTIONS]

Positional Arguments:
  USERNAMES                  One or more usernames to search

General Options:
  --version                  Show version info
  --timeout TIMEOUT          Request timeout in seconds (default: 30)
  --retries RETRIES          Retry count for failed requests
  -n, --max-connections N    Max concurrent connections (default: 100)
  --no-recursion             Disable recursive search
  --no-extracting            Disable page parsing for extra data
  --id-type TYPE             Identifier type (username, email, etc.)
  --permute                  Generate username permutations
  --db DB_FILE               Custom database file path
  --cookies-jar-file FILE    Custom cookies file
  --ignore-ids IDS           Skip specific usernames/IDs
  --proxy PROXY_URL          HTTP/SOCKS5 proxy URL
  --tor-proxy URL            Tor gateway URL
  --i2p-proxy URL            I2P gateway URL
  --with-domains             Enable domain checking

Site Filtering:
  -a, --all-sites            Scan all 3000+ sites
  --top-sites N              Scan top N sites by rank
  --tags TAGS                Filter by tags (comma-separated)
  --site SITE_NAME           Limit to specific sites
  --use-disabled-sites       Include disabled sites

Operating Modes:
  --parse URL                Extract IDs from a profile URL
  --submit URL               Submit a new site to the database
  --self-check               Validate database entries
  --stats                    Show database statistics
  --web [PORT]               Launch web interface (default: 5000)

Output Options:
  --print-not-found          Show sites with no results
  --print-errors             Show check error details
  --verbose, -v              Enable verbose output
  --info, -vv                Enable extra verbose output
  --debug                    Enable debug mode
  --no-color                 Disable colored output
  --no-progressbar           Disable progress bar
```

---

## 📁 Project Structure

```
dr3/
│
├── dr3/                          # 🔍 Core package
│   ├── __init__.py               #     Package initialization
│   ├── __main__.py               #     Entry point
│   ├── __version__.py            #     Version (0.5.0a1)
│   ├── dr3.py                    #     CLI & main logic
│   ├── checking.py               #     Site checking engine
│   ├── sites.py                  #     Site database management
│   ├── report.py                 #     Report generation (HTML/PDF/CSV/XMind)
│   ├── notify.py                 #     Console output & notifications
│   ├── executors.py              #     Async execution handlers
│   ├── submit.py                 #     New site submission logic
│   ├── activation.py             #     Account activation detection
│   ├── errors.py                 #     Error handling & classification
│   ├── permutator.py             #     Username permutation generator
│   ├── result.py                 #     Result data structures
│   ├── settings.py               #     Configuration management
│   ├── utils.py                  #     Utility functions
│   ├── types.py                  #     Type definitions
│   ├── resources/                #     Data files & templates
│   └── web/                      #     🌐 Flask web interface
│       ├── app.py                #         Web application
│       ├── static/               #         CSS, JS assets
│       └── templates/            #         HTML templates
│
├── tests/                        # 🧪 Test suite
├── docs/                         # 📚 Documentation
├── static/                       # 🖼️ Screenshots & demo files
├── reports/                      # 📊 Generated reports output
├── utils/                        # 🔧 Utility scripts
│
├── pyproject.toml                # 📦 Poetry project config
├── poetry.lock                   # 🔒 Dependency lock file
├── Dockerfile                    # 🐳 Docker image definition
├── Installer.bat                 # ⚡ Windows installer script
├── Makefile                      # 🛠️ Build automation
├── sites.md                      # 📋 Full list of supported sites
├── cookies.txt                   # 🍪 Cookie jar for authenticated requests
├── LICENSE                       # ⚖️ MIT License
├── CHANGELOG.md                  # 📝 Version history
├── CONTRIBUTING.md               # 🤝 Contribution guidelines
└── CODE_OF_CONDUCT.md            # 📜 Community standards
```

---

## 🐳 Docker

### Build

```bash
docker build -t dr3sec .
```

### Run

```bash
# Basic search
docker run dr3sec username

# With HTML report (mount volume for output)
docker run -v $(pwd)/reports:/app/reports dr3sec username --html

# With proxy
docker run dr3sec username --proxy socks5://host:port
```

---

## 🤝 Contributing

Contributions are welcome! You can:

1. **Add new sites** — Edit `data.json` to add website definitions
2. **Fix false positives** — Improve detection patterns
3. **Submit bug reports** — Open an issue on GitHub
4. **Improve documentation** — Update docs or README

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## ⚠️ Disclaimer

**This tool is intended for educational and lawful purposes only.** The developers do not endorse or encourage any illegal activities or misuse of this tool. Regulations regarding the collection and use of personal data vary by country and region, including but not limited to GDPR in the EU, CCPA in the USA, and similar laws worldwide.

It is your sole responsibility to ensure that your use of this tool complies with all applicable laws and regulations in your jurisdiction. Any illegal use of this tool is strictly prohibited, and you are fully accountable for your actions.

The authors and developers of this tool bear no responsibility for any misuse or unlawful activities conducted by its users.

---

## ⚖️ License

MIT © [DR3SEC](https://github.com/DR3SEC)<br/>
MIT © [Maigret](https://github.com/soxoj/maigret)<br/>
MIT © [Sherlock Project](https://github.com/sherlock-project/)<br/>
Original Creator of Sherlock Project — [Siddharth Dushantha](https://github.com/sdushantha)

---

<div align="center">

**Built by 🇮🇶 DR3SEC**

*Intelligence Starts With a Username.*

</div>
