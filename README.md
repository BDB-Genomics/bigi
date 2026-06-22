<div align="center">

# 🌐 BiGI — Blast-radius Impact Graph Indexer

**See what breaks before you break it.**

[![CI](https://github.com/BDB-Genomics/BiGI/actions/workflows/ci.yml/badge.svg)](https://github.com/BDB-Genomics/BiGI/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![npm](https://img.shields.io/badge/npx-bigi-CB3837.svg)](https://www.npmjs.com/)

<img src="assets/bigi_hero.jpg" width="800" alt="BiGI Interactive Dependency Graph">

> BiGI statically analyzes your entire project — pipelines, scripts, functions — and builds an interactive dependency graph.
> Change a function? BiGI instantly shows you every downstream rule, script, and data output that will break.

</div>

---

## Why BiGI?

Modern bioinformatics and data science projects are tangled webs of pipeline rules, R scripts, Python modules, and shell commands. Changing one function can silently break a rule three steps downstream. **BiGI makes that invisible blast radius visible.**

| Without BiGI | With BiGI |
|---|---|
| "I changed `normalize.R` — what breaks?" 🤷 | Instant visual map of every affected rule and output |
| Manual grep through Snakefiles | Automated cross-language dependency tracing |
| PR reviews miss downstream impacts | GitHub Action comments the blast radius on every PR |
| Pipeline failures discovered at runtime | Impact analysis before you even commit |

---

## ✨ Features

### 🔗 Cross-Language Dependency Graph
BiGI doesn't just map pipelines — it dives *into* your scripts. It connects Snakemake rules and Nextflow processes to the Python functions, R scripts, and shell commands they execute, giving you a complete, multi-layer dependency graph.

### 🚦 Git-Aware Blast Radius
Modified files glow **red** in the graph. Everything downstream that could break glows **orange**. You see the blast radius instantly, before you push.

### 🤖 AI Auto-Remediation
Point BiGI at a broken rule and describe the problem. It uses Gemini AI with full downstream-impact context to suggest a targeted code fix.

### 📡 Live Execution Overlay
Run `bigi monitor` alongside your Snakemake or Nextflow pipeline. Graph nodes light up in real-time: 🟡 running, 🔵 done, 🔴 failed.

### 🗂️ Data Contract Detection
BiGI infers DataFrame column dependencies (`df["gene_name"]`) and traces them through the pipeline. If a step drops a column that a downstream step needs, you'll know.

### 🌍 Org-Wide Meta-Graphs
Analyze multiple repositories simultaneously. BiGI stitches cross-repo function calls and shared data dependencies into a single unified graph.

### 🛠️ Universal Language Support
| Native Parsers (AST-level) | Generic Parser (regex-based) |
|---|---|
| Python | Bash / Shell |
| R / RScript | JavaScript / TypeScript |
| Snakemake | Rust / Go / C / C++ |
| Nextflow | Perl / Julia / MATLAB / Ruby |

---

## 🚀 Installation

### pip (recommended)
```bash
pip install git+https://github.com/BDB-Genomics/BiGI.git
```

### From source
```bash
git clone https://github.com/BDB-Genomics/BiGI.git
cd BiGI
pip install -e .
```

### npx (Node.js wrapper)
```bash
npx bigi --help
```

---

## 📖 Usage

### Analyze a project
Generate an interactive HTML graph for any local project:
```bash
bigi analyze path/to/project --html graph.html
```
Open `graph.html` in your browser — no server required.

### Analyze a remote GitHub repository
```bash
bigi analyze https://github.com/owner/repo --html graph.html
```

### Check what breaks
Query the blast radius of a specific function or rule:
```bash
bigi impact normalize_data --pipeline-dir my_pipeline/
```
Output:
```
Symbol: function: normalize_data (in scripts/normalize.R, lines 12-45)
Downstream Impact (what breaks if changed):
  → rule: normalise (HIGH confidence)
    → rule: plot_data (HIGH confidence)
```

### AI Auto-Remediation
Let Gemini AI suggest a fix with full downstream context:
```bash
export GEMINI_API_KEY="your-key"
bigi remediate failing_rule --prompt "Fix the missing column error"
```

### Live Execution Monitor
Watch your pipeline run in real-time:
```bash
# Terminal 1: Run your pipeline
snakemake -j 4 2>&1 | tee run.log

# Terminal 2: Launch the live overlay
bigi monitor --html graph.html --log run.log
```
Open `http://localhost:8080` to see nodes light up as rules execute.

### Export to GraphML
Import your graph into Cytoscape, Gephi, or any graph analysis tool:
```bash
bigi analyze . && bigi export graph.graphml
```

### Org-Wide Meta-Graph
Stitch multiple repositories into one unified graph:
```bash
bigi analyze repo1/ repo2/ repo3/ --html org_graph.html
```

---

## 🤖 GitHub Action — PR Blast Radius Bot

BiGI includes a reusable GitHub Action that automatically comments on Pull Requests showing the downstream impact of every changed file.

### Quick Setup

Add this workflow to your repository at `.github/workflows/bigi.yml`:

```yaml
name: BiGI Blast Radius
on:
  pull_request:
    branches: [main, master]

permissions:
  pull-requests: write
  contents: read

jobs:
  blast-radius:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: BDB-Genomics/BiGI@main
        with:
          pipeline-dir: '.'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

That's it. Every PR will now get an automated comment like:

```
💥 BiGI Blast Radius Report 💥

The following rules/functions were modified in this PR:

Impact of `normalize_data`:
  → rule: normalise (HIGH confidence)
    → rule: plot_data (HIGH confidence)

Please ensure all impacted downstream rules have been re-tested before merging.
```

---

## 🏗️ Architecture

```
bigi/
├── cli.py              # CLI entry point and sub-command dispatch
├── graph.py            # Core graph builder, impact tracer, and graph stitcher
├── server.py           # Live execution overlay HTTP server
├── constants.py        # R built-in function whitelist
├── parsers/
│   ├── snakemake.py    # Snakefile/SMK rule parser
│   ├── nextflow.py     # Nextflow .nf process parser
│   ├── python.py       # Python AST visitor (defs, calls, schemas)
│   ├── generic.py      # Regex-based universal parser
│   └── r_parser.R      # R script parser (via Rscript)
├── render/
│   ├── html_template.py  # Self-contained interactive HTML visualization
│   └── template.html     # Source HTML template
api/
└── index.py            # Vercel serverless function (web interface)
```

**How it works:**
1. **Parse** — BiGI walks your project directory and runs language-specific parsers to extract function definitions, function calls, rule inputs/outputs, and script references.
2. **Build** — All parsed data is unified into a single directed graph where nodes are rules, functions, data schemas, and environments — and edges represent dependencies.
3. **Trace** — Given a modified file or function, BiGI performs a DFS traversal to find every downstream node that could be affected.
4. **Visualize** — The graph is rendered as a self-contained HTML file with an interactive force-directed layout powered by a custom WebAssembly physics engine.

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bigi --cov-report=term-missing
```

---

## 🌐 Web Interface (Vercel)

BiGI can be deployed to Vercel as a serverless web app. Visit your deployment URL and append any GitHub `owner/repo` to instantly generate a graph:

```
https://your-bigi-app.vercel.app/BDB-Genomics/BiGI
```

No installation required — the server downloads the repository, analyzes it, and returns an interactive visualization.

### Deploy Your Own

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/BDB-Genomics/BiGI)

---

## 📋 CLI Reference

| Command | Description |
|---|---|
| `bigi analyze <dir\|url> [--html out.html]` | Build the dependency graph and optionally export HTML |
| `bigi impact <symbol> [--pipeline-dir .]` | Trace downstream blast radius of a function or rule |
| `bigi pr-report [--pipeline-dir .] [--output report.md]` | Generate a markdown blast radius report for CI |
| `bigi remediate <symbol> --prompt "..."` | AI-powered code fix suggestion using Gemini |
| `bigi monitor --html graph.html [--log run.log]` | Live execution overlay server |
| `bigi export <output.graphml>` | Export graph to GraphML format |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-thing`)
3. Write tests for your changes
4. Ensure CI passes (`pytest tests/`)
5. Open a Pull Request — BiGI will automatically analyze its own blast radius!

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by [BDB-Genomics](https://github.com/BDB-Genomics)**

*"What breaks if I change this code?" — Now you know.*

</div>
