# BiGI: Universal Pipeline Intelligence Platform

> **"What breaks if I change this?"**  
> BiGI (BDB-Genomics Impact Graph) is a static analysis and visualization tool that traces code dependencies across your entire bioinformatics pipeline—connecting orchestration layers (Snakemake, Nextflow) directly to the underlying scripts (R, Python, Rust, Bash, etc.).

---

## ⚡ Core Capabilities

- **Cross-Layer Traceability**: Builds a single, unified graph connecting high-level pipeline rules to the low-level functions executed within their scripts.
- **Universal Language Parsing**: Natively parses **Snakemake** and **Nextflow**. Automatically extracts ASTs for **R, Python, Bash, Rust, Go, C++, JavaScript**, and more.
- **CI/CD "Blast Radius" Bot**: Automatically comments on GitHub Pull Requests, warning reviewers of the downstream impact of modified code before it merges.
- **Offline HTML Visualization**: Generates a self-contained, interactive force-directed graph with a premium dark-mode aesthetic. Zero external dependencies.
- **GraphML Export**: Export your dependency index to `.graphml` for advanced network analysis in Cytoscape or Gephi.

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

BiGI is designed to be completely frictionless. You can analyze local directories or remote GitHub URLs directly.

### 1. Analyze a Local Pipeline
Generate an interactive dependency graph for a local project:
```bash
bigi analyze path/to/pipeline --html output.html
```

### 2. Analyze a Remote GitHub Repository
Pass a GitHub URL, and BiGI will clone it into a temporary workspace, analyze it, generate the graph, and instantly clean up the cloned code.
```bash
bigi analyze https://github.com/your-org/genomics-pipeline.git --html output.html
```

### 3. Query Downstream Impact (CLI)
Ask BiGI exactly what breaks if a specific function or rule is modified:
```bash
bigi impact log_transform --pipeline-dir my_pipeline
```

### 4. CI/CD Automated Blast Radius
Integrate BiGI into your GitHub Actions to automate code reviews. BiGI will calculate the downstream impact of any code changed in a PR and post a formatted report directly to the conversation.
```bash
bigi pr-report --pipeline-dir .
```
*(See `.github/workflows/pr_blast_radius.yml` for an example workflow).*

### 5. Export for Cytoscape
```bash
bigi export my_graph.graphml --pipeline-dir my_pipeline
```

---

## 🧠 How it Works

BiGI avoids dynamic runtime tracing in favor of blazing-fast static analysis:
1. **Orchestrator Parsing**: Extracts the Directed Acyclic Graph (DAG) of inputs, outputs, and shell commands from Snakemake `Snakefiles` or Nextflow `.nf` files.
2. **AST Extraction**: Uses native parsers (like Python's `ast` and R's `getParseData`) alongside regex-based generic parsers to extract function definitions and invocations from the underlying scripts.
3. **Graph Synthesis**: Resolves function calls to their definitions across files, linking them to the pipeline rules that execute those files. Every edge is tagged with execution context (e.g., `"Invoked at L42"`).

---

## 🔭 Future Vision & Roadmap

We are actively expanding BiGI into a complete pipeline governance platform:

1. **Data Schema Nodes**: Statically infer expected CSV/Parquet schemas from script logic to flag column mismatches before compute is wasted.
2. **Telemetry Overlay**: Ingest orchestrator benchmarks to dynamically size graph nodes by RAM usage and color them by execution time, instantly highlighting bottlenecks.
3. **Environment Graphing**: Parse `conda` and `Docker` environments to trace the exact blast radius of a package version upgrade (e.g., "What breaks if Pandas is bumped to v2.0?").
4. **Interactive Cypher Queries**: Embed a Neo4j-style query engine directly into the visualization to programmatically audit massive enterprise architectures.
