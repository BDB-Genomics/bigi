# BiGI (BDB-Genomics Impact Graph)

BiGI is a command-line interface (CLI) tool designed for bioinformatics developers to answer: **"What breaks if I change this?"** across both the pipeline orchestration layer (Snakemake) and the code layer (R/Bioconductor scripts).

Unlike generic code-intelligence tools that only analyze general-purpose code or only view pipelines as static command blocks, BiGI builds a single, unified dependency graph connecting Snakemake rule inputs/outputs to the underlying R functions executed by those rules.

---

## Features

- **Pipeline DAG Parsing**: Extracts Snakemake rule configurations (inputs, outputs, scripts, and shell commands).
- **R Code Analysis**: Extracts function definitions and function calls (with local scope/caller resolution) directly from R scripts.
- **Cross-Layer Graph Connection**: Links rules to the R functions called by their scripts (both direct and transitive dependencies).
- **Impact Querying**: Traces downstream impact hierarchically across both layers starting from a rule or R function.
- **Honest Confidence Labeling**: Tags every dependency/impact relationship with `HIGH`, `AMBIGUOUS`, or `UNRESOLVED`.
- **Self-Contained HTML Export**: Generates an interactive force-directed graph visualization of the index with **zero external CDN dependencies** (works 100% offline). Now featuring a premium, sleek tech aesthetic with a cyberpunk-inspired dark theme and monospace typography.
- **GraphML Export**: Export the dependency index to a `.graphml` file for ingestion into advanced network analysis platforms like Cytoscape or Gephi.

---

## Architectural Decisions & R AST Choice

### R Parsing: `parse()` + `getParseData()`
To analyze R code, BiGI invokes R's built-in `parse(keep.source = TRUE)` combined with `getParseData()`.
- **Why this was chosen**: Unlike Python which has a standard, official `ast` module, R has multiple third-party packages for AST parsing (like `lintr` or `codetools`) which can be brittle or require external compilation. `getParseData()` is a native R API available in every standard R installation. It provides a detailed, token-by-token dataframe representing the parse tree (with exact line/column boundaries and parent-child relationships).
- **How caller resolution works**: BiGI extracts function definitions and their exact bounding ranges. For every `SYMBOL_FUNCTION_CALL` token, BiGI finds the narrowest enclosing function definition range. If no function encloses the call, it is classified as a global-scope call executing when the script runs.

---

## Limitations (What is NOT Handled)

BiGI aims to be honest about its static analysis limits:
1. **Dynamic R Dispatch & S4/R6 Classes**: BiGI uses static syntactic analysis. Dynamic method dispatch (e.g., S3/S4 generics, R6 class methods, or `UseMethod`) is not traced. These connections are reported as `UNRESOLVED`.
2. **Non-Standard Evaluation (NSE)**: R's NSE (frequent in packages like `dplyr` and `ggplot2` where arguments are interpreted as column names rather than variables/functions) is ignored.
3. **Dynamic Script Sourcing**: Function definitions loaded dynamically at runtime via `source("path/to/file.R")` are not statically followed if the path is dynamically constructed or if the source occurs inside control flow.
4. **Snakemake Wildcard Limits**: While BiGI parses and matches wildcards (e.g., matching `data/{sample}.csv` output to `data/{id}.csv` input), it cannot statically expand computed wildcards that rely on python code execution inside the Snakefile (e.g., `expand()` calls that query filesystem state).
5. **Nextflow Support**: Nextflow parsing is currently out of scope. Only Snakemake is supported as the pipeline orchestration layer.
6. **Cross-Package Resolution**: BiGI does not parse external R libraries (like `DESeq2` or `ggplot2`) that reside outside the indexed project directory. These external calls are labeled `UNRESOLVED`.

---

## Synthetic Test Pipeline Structure

We built a synthetic test pipeline to validate the tool:
- **`raw_data`**: Dummy shell command outputting `data/raw.csv`.
- **`preprocess`**: Runs `scripts/preprocess.R` on `data/raw.csv`, outputting `data/filtered.csv`. Defines `clean_names` and `log_transform`.
- **`normalise`**: Runs `scripts/normalize.R` on `data/filtered.csv`, outputting `data/normalized.csv`. Defines `normalize_counts` and a conflicting definition of `log_transform` (creating a deliberate name collision).
- **`plot_data`**: Runs `scripts/plot.R` on `data/normalized.csv`, outputting `plots/expression_plot.png`. Defines `generate_heatmap`, which calls `clean_names` (defined in `preprocess.R`) to verify cross-file call resolution.

---

## Installation

To install BiGI globally so you can run it from anywhere without needing the `python3 bigi-cli` prefix:

```bash
git clone https://github.com/BDB-Genomics/BiGI.git
cd BiGI
pip install -e .
```
Now you can use the `bigi` command globally!

---

## CLI Usage & Verification Results

### 1. Indexing the Codebase (`analyze`)
You can analyze a local directory or **directly analyze a remote GitHub repository URL**. 

When passing a remote GitHub URL, BiGI will automatically clone the repository into an isolated temporary folder, generate the requested output graph, and instantly delete the cloned code when finished.

**Analyze a local folder:**
```bash
bigi analyze test_pipeline --html test_pipeline/visualization.html
```

**Analyze a remote GitHub repository directly:**
```bash
bigi analyze https://github.com/BDB-Genomics/BiGI.git --html output.html
```
*Output:*
```
Analyzing genomics pipeline at 'test_pipeline'...
Analysis complete. Index saved to 'test_pipeline/.bigi_index.json'.
Indexed 18 nodes and 26 edges.
### 2. Exporting to GraphML (`export`)
If you want to perform custom network analysis (e.g., PageRank, Centrality) in tools like Gephi or Cytoscape, you can export the graph:
```bash
bigi export my_graph.graphml --pipeline-dir test_pipeline
```
*Output:*
```
GraphML exported to 'my_graph.graphml'.
```

### 3. Querying Downstream Impact (`impact`)

#### Test Case A: Happy Path (`clean_names`)
Querying `clean_names` (which is defined in `preprocess.R` and called inside `plot.R`):
```bash
bigi impact clean_names --pipeline-dir test_pipeline
```
*Output:*
```
Symbol: function: clean_names (in scripts/preprocess.R, lines 2-5)
Downstream Impact (what breaks if changed):
  [Depth 1] function: generate_heatmap (in scripts/plot.R) (Confidence: HIGH)
    [Depth 2] rule: plot_data (Confidence: HIGH)
  [Depth 1] rule: preprocess (Confidence: HIGH)
    [Depth 2] rule: normalise (Confidence: HIGH - Input 'data/filtered.csv' matched output)
      [Depth 3] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)
```

#### Test Case B: Ambiguous Resolution (`log_transform`)
Querying the conflicting function `log_transform` (defined in both `preprocess.R` and `normalize.R`):
```bash
bigi impact log_transform --pipeline-dir test_pipeline
```
*Output:*
```
Symbol: function: log_transform (in scripts/normalize.R, lines 7-10)
Downstream Impact (what breaks if changed):
  [Depth 1] rule: normalise (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)
  [Depth 1] rule: preprocess (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] rule: normalise (Confidence: HIGH - Input 'data/filtered.csv' matched output)
      [Depth 3] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)

Symbol: function: log_transform (in scripts/preprocess.R, lines 7-10)
Downstream Impact (what breaks if changed):
  [Depth 1] rule: normalise (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)
  [Depth 1] rule: preprocess (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] rule: normalise (Confidence: HIGH - Input 'data/filtered.csv' matched output)
      [Depth 3] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)
```

#### Test Case C: Rule Downstream + Touched Functions (`preprocess`)
Querying the rule `preprocess`:
```bash
bigi impact preprocess --pipeline-dir test_pipeline
```
*Output:*
```
Symbol: rule: preprocess (in Snakefile)
Downstream Impact (what breaks if changed):
  [Depth 1] rule: normalise (Confidence: HIGH - Input 'data/filtered.csv' matched output)
    [Depth 2] rule: plot_data (Confidence: HIGH - Input 'data/normalized.csv' matched output)
R Functions Touched by Script (direct and transitive calls):
  [Depth 1] function: clean_names (in scripts/preprocess.R) (Confidence: HIGH)
    [Depth 2] function: return (UNRESOLVED definition) (Confidence: UNRESOLVED)
  [Depth 1] function: log_transform (in scripts/normalize.R) (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] function: mean (UNRESOLVED definition) (Confidence: UNRESOLVED)
    [Depth 2] function: return (UNRESOLVED definition) (Confidence: UNRESOLVED)
  [Depth 1] function: log_transform (in scripts/preprocess.R) (Confidence: AMBIGUOUS - Multiple definitions of 'log_transform' exist)
    [Depth 2] function: log (UNRESOLVED definition) (Confidence: UNRESOLVED)
    [Depth 2] function: return (UNRESOLVED definition) (Confidence: UNRESOLVED)
  [Depth 1] function: read.csv (UNRESOLVED definition) (Confidence: UNRESOLVED)
  [Depth 1] function: write.csv (UNRESOLVED definition) (Confidence: UNRESOLVED)
```

#### Test Case D: Failure on Nonexistent Symbol
```bash
bigi impact nonexistent_symbol --pipeline-dir test_pipeline
```
*Output (exits with status 1):*
```
Error: Symbol or rule 'nonexistent_symbol' not found in the index.
```

### 4. CI/CD Automated Blast Radius Reporting (`pr-report`)
BiGI features a `pr-report` command designed specifically for GitHub Actions. It automatically detects which rules and functions were modified in a Pull Request, calculates their downstream impact, and generates a formatted Markdown string. 

When integrated into a CI/CD pipeline (see `.github/workflows/pr_blast_radius.yml`), BiGI will automatically post this report as a comment directly on the PR, warning reviewers of the exact blast radius of the code changes before merging!

---

## Recent Updates

- **Remote GitHub URL Support**: You can now pass GitHub URLs directly into `--pipeline-dir`. BiGI will securely clone it into an isolated temporary folder, analyze it, and instantly delete the clone upon completion to keep your workspace pristine.
- **CI/CD Blast Radius Bot**: Added the `pr-report` command and a GitHub Actions workflow to automatically comment on PRs with the downstream impact of code changes.
- **Nextflow Support (`.nf`)**: Native parsing support for Nextflow pipelines is fully integrated alongside Snakemake.
- **GraphML Export Capability**: Added `bigi export <file>.graphml` to generate standardized XML graph files for external network analysis.
- **Premium Visualization Redesign**: Stripped away generic gradients and glassmorphism from the HTML export, replacing it with a sleek, minimalist hacker aesthetic (solid `#0a0a0a` backgrounds, sharp `#00e5ff`/`#ff00aa` neon accents, JetBrains Mono font).
- **Physics Simulation Control Fix**: Corrected the WASM physics engine so the pause/resume simulation button now accurately halts the layout calculations.

---

## Future Roadmap & Vision

We are actively expanding BiGI from a simple dependency mapper into a full-scale **Universal Pipeline Intelligence Platform**. Here are the major architectural features planned for the future, applicable across all supported languages (Python, R, Rust, Go, C++, JS, Bash) and orchestrators (Snakemake, Nextflow):

### 1. Data Schema & Content Type Validation Nodes
Right now, the graph connects pipeline rules to their internal functions. In the future, we will model the **data structures themselves** as nodes. By statically analyzing the data manipulation logic across the codebase, BiGI will infer the expected schemas (e.g., column names in a CSV/Parquet). If a `preprocess` step outputs a dataset with a `sample_id` column, but a downstream downstream model expects `id`, the graph will flag a **Schema Mismatch Warning** before you ever waste compute running the pipeline.

### 2. Computational Bottleneck Overlay (Telemetry Integration)
By ingesting execution logs and benchmarks from orchestrators, BiGI will project performance telemetry directly onto the visual graph. Developers will be able to toggle a "Performance View" where nodes are sized dynamically by RAM consumption and colored by execution time. This will instantly highlight algorithmic bottlenecks and inefficient scripts within massively parallel workflows.

### 3. Container & Environment Dependency Graphing
Modern pipelines rely on tightly coupled environments (Docker containers, Conda `.yaml` files). BiGI will parse these environment definitions and inject them as global nodes into the graph. If you want to know, *"What breaks if I upgrade Pandas from 1.5 to 2.0?"*, the graph will instantly trace from the environment node down to every specific script and rule that imports or relies on that dependency, proactively preventing version-bump breakages.

### 4. Interactive "Cypher" Graph Query Engine
Instead of just a visual search bar or static CLI queries, we plan to embed a fully-fledged graph query language interface (similar to Neo4j's Cypher) directly into the UI. Pipeline engineers will be able to programmatically audit massive enterprise architectures with queries like:
`MATCH (r:Rule)-[*]->(f:Function) WHERE f.language='rust' RETURN r`
This will unlock unparalleled compliance auditing, refactoring analysis, and architectural governance.
- **Exponential DFS Traversal Fix**: Resolved a performance issue where the impact traversal explored all paths redundantly, which would cause the tool to hang on complex pipelines.
- **Python `async def` Support**: The Python AST parser now correctly captures asynchronous functions.
- **WASM Memory Safety**: Added array bounds checking for JS-provided link indices inside the Rust physics engine to prevent memory out-of-bounds crashes, and implemented `wrapping_abs` in the hash grid to avoid integer overflow.
- **WASM Initialization Optimization**: Replaced an O(N×E) index loop during WASM graph renderer initialization with an O(1) Map lookup.
- **Graceful CLI Default**: Running `bigi` with no arguments now prints the help text instead of running a default analysis.
