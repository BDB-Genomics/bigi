<div align="center">

# 🌐 BiGI: Blast-radius Impact Graph Indexer
**Universal Software Pipeline Intelligence & Static Analysis**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/BDB-Genomics/BiGI/commits/main)

> **"What breaks if I upgrade this package or modify this function?"**  
> BiGI is a blazing-fast static analysis engine that maps the execution topology of your massive software pipelines. It bridges the gap between high-level orchestrators (Snakemake, Nextflow) and the underlying scripts (Python, Rust, C++, Bash), generating an interactive, force-directed "Blast Radius" visualization.

</div>

---

## ✨ Core Capabilities

- 🔗 **Cross-Layer Traceability**: Builds a unified graph connecting pipeline orchestrator rules directly to the low-level functions executed within their scripts.
- 📦 **Container Dependency Mapping**: Natively parses `conda:` and `container:` directives, generating global Environment nodes to trace the exact blast radius of a package version upgrade.
- 🚦 **Interactive Git Tracking**: Integrates directly with Git. Uncommitted local modifications glow **Red** on the physical graph, and their downstream blast radius cascades in **Orange**.
- 🛠️ **Universal Language Parsing**: Natively extracts execution ASTs from **Snakemake**, **Nextflow**, **R**, **Python**, **Bash**, **Rust**, **Go**, **C++**, and **JavaScript**.
- 🤖 **CI/CD "Blast Radius" Bot**: Drops automated PR comments warning code reviewers of downstream risks before code ever merges.
- ⚡ **Zero-Dependency Export**: Generates a self-contained, interactive HTML force-directed graph (with a premium dark-mode WASM physics engine) that you can open anywhere.

---

## 🚀 Quickstart

Install BiGI globally to use the CLI from anywhere:

```bash
git clone https://github.com/BDB-Genomics/BiGI.git
cd BiGI
pip install -e .
```

---

## 📖 Usage Guide

BiGI is designed to be frictionless. Analyze local projects or remote repositories with zero configuration.

### 1. Analyze a Local Pipeline
```bash
bigi analyze path/to/pipeline --html output.html
```

### 2. Analyze a Remote GitHub Repository
BiGI instantly clones, analyzes, generates the graph, and cleans up temporary workspaces.
```bash
bigi analyze https://github.com/your-org/data-pipeline.git --html output.html
```

### 3. Query Downstream Impact (CLI)
Ask BiGI exactly what breaks if a specific function is modified:
```bash
bigi impact log_transform --pipeline-dir my_pipeline
```

### 4. CI/CD Automated Blast Radius
Integrate BiGI into your GitHub Actions to automate code reviews:
```bash
bigi pr-report --pipeline-dir .
```
*(See `.github/workflows/pr_blast_radius.yml` for an example workflow).*

---

## 🧠 Architecture & Under the Hood

BiGI avoids fragile runtime tracing in favor of blazing-fast static analysis:
1. **DAG Extraction**: Parses the Directed Acyclic Graph of inputs, outputs, and environments from `Snakefiles` or `.nf` files.
2. **AST Scanning**: Uses native parsers alongside high-speed regex engines to extract function definitions and invocations from the underlying source code.
3. **Graph Synthesis**: Resolves execution paths across files, linking them to orchestrator rules and environment definitions. Every edge is tagged with execution context.

---

## 🔭 Future Vision & Roadmap

We are actively expanding BiGI into a complete pipeline governance platform:

1. **Data Schema Nodes**: Statically infer expected CSV/Parquet schemas from script logic to flag column mismatches before compute is wasted.
2. **Telemetry Overlay**: Ingest orchestrator benchmarks to dynamically size graph nodes by RAM usage and color them by execution time, instantly highlighting bottlenecks.
3. **Interactive Cypher Queries**: Embed a Neo4j-style query engine directly into the visualization to programmatically audit massive enterprise architectures.
