"""Comprehensive test suite for BiGI.

Covers:
- Snakemake parser (find, parse single, parse pipeline)
- Python parser (sync/async functions, dotted calls, schema reads)
- Generic parser (JavaScript, Rust, bash)
- Graph builder (build_graph, save/load index, trace_impact, stitch_graphs)
- CLI export (export_html)
"""

import json
import os
import textwrap
from unittest import mock

import pytest

from bigi.parsers.snakemake import (
    find_snakemake_files,
    parse_pipeline,
    parse_snakemake_file,
)
from bigi.parsers.python import parse_python_directory, parse_python_file
from bigi.parsers.generic import parse_generic_file
from bigi.graph import (
    build_graph,
    load_index,
    save_index,
    stitch_graphs,
    trace_impact,
)
from bigi.cli import export_html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_PIPELINE_DIR = os.path.join(os.path.dirname(__file__), "test_pipeline")


# ===========================================================================
# 1. Snakemake Parser Tests
# ===========================================================================


class TestSnakemakeParser:
    """Tests for ``bigi.parsers.snakemake``."""

    def test_find_snakemake_files_discovers_snakefile(self, tmp_path):
        """find_snakemake_files should discover Snakefile and *.smk files."""
        (tmp_path / "Snakefile").write_text("rule a:\n    shell: 'echo hi'\n")
        sub = tmp_path / "rules"
        sub.mkdir()
        (sub / "extra.smk").write_text("rule b:\n    shell: 'echo bye'\n")
        # Non-snakemake file should be ignored
        (tmp_path / "readme.md").write_text("# readme")

        found = find_snakemake_files(str(tmp_path))

        basenames = sorted(os.path.basename(f) for f in found)
        assert basenames == ["Snakefile", "extra.smk"]

    def test_parse_snakemake_file_extracts_rules(self, tmp_path):
        """parse_snakemake_file should extract rule metadata correctly."""
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(textwrap.dedent("""\
            rule step_one:
                input:
                    "data/raw.csv"
                output:
                    "data/processed.csv"
                shell:
                    "python scripts/process.py {input} {output}"

            rule step_two:
                input:
                    "data/processed.csv"
                output:
                    "results/final.csv"
                script:
                    "scripts/analyze.R"
        """))

        rules = parse_snakemake_file(str(snakefile), str(tmp_path))

        assert "step_one" in rules
        assert "step_two" in rules

        r1 = rules["step_one"]
        assert r1["input"] == ["data/raw.csv"]
        assert r1["output"] == ["data/processed.csv"]
        assert r1["file"] == "Snakefile"

        r2 = rules["step_two"]
        assert r2["input"] == ["data/processed.csv"]
        assert r2["output"] == ["results/final.csv"]
        # script section should resolve relative to snakefile directory
        assert r2["script"] is not None
        assert r2["r_script"] is not None  # .R extension → r_script set

    def test_parse_pipeline_combines_rules(self, tmp_path):
        """parse_pipeline should merge rules from multiple Snakemake files."""
        (tmp_path / "Snakefile").write_text(
            "rule alpha:\n    output: 'a.txt'\n    shell: 'touch a.txt'\n"
        )
        sub = tmp_path / "rules"
        sub.mkdir()
        (sub / "extra.smk").write_text(
            "rule beta:\n    input: 'a.txt'\n    output: 'b.txt'\n    shell: 'cp a.txt b.txt'\n"
        )

        rules = parse_pipeline(str(tmp_path))

        assert "alpha" in rules
        assert "beta" in rules

    def test_parse_real_test_pipeline(self):
        """parse_pipeline should successfully parse the existing test_pipeline Snakefile."""
        rules = parse_pipeline(TEST_PIPELINE_DIR)

        expected_names = {"raw_data", "preprocess", "normalise", "plot_data"}
        assert set(rules.keys()) == expected_names

        # Verify the pipeline chain
        assert rules["preprocess"]["input"] == ["data/raw.csv"]
        assert rules["normalise"]["input"] == ["data/filtered.csv"]
        assert rules["plot_data"]["input"] == ["data/normalized.csv"]


# ===========================================================================
# 2. Python Parser Tests
# ===========================================================================


class TestPythonParser:
    """Tests for ``bigi.parsers.python``."""

    def test_parse_python_file_functions_and_calls(self, tmp_path):
        """parse_python_file should extract function defs, calls, and their callers."""
        pyfile = tmp_path / "sample.py"
        pyfile.write_text(textwrap.dedent("""\
            import os

            def greet(name):
                print(f"Hello, {name}")

            def main():
                greet("world")
                os.path.join("a", "b")
        """))

        result = parse_python_file(str(pyfile), str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "greet" in def_names
        assert "main" in def_names

        call_names = [c["name"] for c in result["calls"]]
        assert "greet" in call_names
        assert "os.path.join" in call_names  # dotted call resolution

        # Verify caller tracking
        greet_call = next(c for c in result["calls"] if c["name"] == "greet")
        assert greet_call["caller"] == "main"

    def test_parse_async_function(self, tmp_path):
        """parse_python_file should handle async function definitions via visit_AsyncFunctionDef."""
        pyfile = tmp_path / "async_mod.py"
        pyfile.write_text(textwrap.dedent("""\
            import asyncio

            async def fetch_data(url):
                await asyncio.sleep(1)
                return url

            async def process():
                result = await fetch_data("http://example.com")
        """))

        result = parse_python_file(str(pyfile), str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "fetch_data" in def_names
        assert "process" in def_names

        # fetch_data should be called from within process
        fd_call = next(c for c in result["calls"] if c["name"] == "fetch_data")
        assert fd_call["caller"] == "process"

    def test_parse_schema_reads(self, tmp_path):
        """parse_python_file should detect dataframe column subscript reads."""
        pyfile = tmp_path / "transform.py"
        pyfile.write_text(textwrap.dedent("""\
            def transform(df):
                col_a = df['gene_id']
                col_b = df['expression']
                return col_a + col_b
        """))

        result = parse_python_file(str(pyfile), str(tmp_path))

        schema_cols = [s["column"] for s in result["schemas"]]
        assert "gene_id" in schema_cols
        assert "expression" in schema_cols
        assert all(s["caller"] == "transform" for s in result["schemas"])

    def test_parse_python_directory(self, tmp_path):
        """parse_python_directory should recursively discover .py files, skipping excluded dirs."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("def helper(): pass\n")
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "should_skip.py").write_text("def skip_me(): pass\n")

        result = parse_python_directory(str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "helper" in def_names
        assert "skip_me" not in def_names  # venv excluded


# ===========================================================================
# 3. Generic Parser Tests
# ===========================================================================


class TestGenericParser:
    """Tests for ``bigi.parsers.generic``."""

    def test_javascript_function(self, tmp_path):
        """parse_generic_file should extract JS function definitions and calls."""
        jsfile = tmp_path / "util.js"
        jsfile.write_text(textwrap.dedent("""\
            function calculateSum(a, b) {
                return a + b;
            }

            calculateSum(1, 2);
        """))

        result = parse_generic_file(str(jsfile), str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "calculateSum" in def_names

        call_names = [c["name"] for c in result["calls"]]
        assert "calculateSum" in call_names

    def test_rust_fn_declaration(self, tmp_path):
        """parse_generic_file should detect Rust fn declarations."""
        rsfile = tmp_path / "lib.rs"
        rsfile.write_text(textwrap.dedent("""\
            fn compute_score(x: i32) -> i32 {
                x * 2
            }
        """))

        result = parse_generic_file(str(rsfile), str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "compute_score" in def_names

    def test_bash_function(self, tmp_path):
        """parse_generic_file should extract bash function declarations."""
        shfile = tmp_path / "deploy.sh"
        shfile.write_text(textwrap.dedent("""\
            function run_pipeline() {
                echo "running"
            }

            cleanup() {
                rm -rf tmp/
            }
        """))

        result = parse_generic_file(str(shfile), str(tmp_path))

        def_names = [d["name"] for d in result["definitions"]]
        assert "run_pipeline" in def_names
        assert "cleanup" in def_names

    def test_unsupported_extension_returns_empty(self, tmp_path):
        """parse_generic_file should return empty results for unsupported extensions."""
        txt = tmp_path / "notes.txt"
        txt.write_text("This is just a text file.\n")

        result = parse_generic_file(str(txt), str(tmp_path))

        assert result["definitions"] == []
        assert result["calls"] == []


# ===========================================================================
# 4. Graph Builder Tests
# ===========================================================================


class TestGraphBuilder:
    """Tests for ``bigi.graph`` — build, serialize, trace, and stitch."""

    @pytest.fixture()
    def graph(self):
        """Build a graph from the test_pipeline directory, mocking the R parser subprocess."""
        with mock.patch("subprocess.run") as mock_run:
            # Mock the Rscript call to return empty results (no R runtime needed)
            mock_result = mock.MagicMock()
            mock_result.stdout = json.dumps({"definitions": [], "calls": []})
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            g = build_graph(TEST_PIPELINE_DIR)
        return g

    def test_build_graph_nodes(self, graph):
        """build_graph should create rule nodes for all four test pipeline rules."""
        node_ids = set(graph["nodes"].keys())

        for rule_name in ("raw_data", "preprocess", "normalise", "plot_data"):
            assert f"rule:{rule_name}" in node_ids

    def test_build_graph_edges(self, graph):
        """build_graph should create pipeline_dep edges for the input-output chain."""
        edge_pairs = [(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "pipeline_dep"]

        # raw_data → preprocess (raw.csv)
        assert ("rule:raw_data", "rule:preprocess") in edge_pairs
        # preprocess → normalise (filtered.csv)
        assert ("rule:preprocess", "rule:normalise") in edge_pairs
        # normalise → plot_data (normalized.csv)
        assert ("rule:normalise", "rule:plot_data") in edge_pairs

    def test_save_and_load_index(self, graph, tmp_path):
        """save_index + load_index should round-trip the graph faithfully."""
        save_index(graph, str(tmp_path))
        loaded = load_index(str(tmp_path))

        assert loaded is not None
        assert set(loaded["nodes"].keys()) == set(graph["nodes"].keys())
        assert len(loaded["edges"]) == len(graph["edges"])

    def test_load_index_returns_none_when_missing(self, tmp_path):
        """load_index should return None when no index file exists."""
        assert load_index(str(tmp_path)) is None

    def test_trace_impact_finds_downstream(self, graph):
        """trace_impact should report downstream rules affected by raw_data."""
        result = trace_impact(graph, "raw_data")

        assert result is not None
        text = "\n".join(result)
        # raw_data's output feeds preprocess
        assert "preprocess" in text

    def test_trace_impact_returns_none_for_missing_symbol(self, graph):
        """trace_impact should return None for a symbol not in the graph."""
        result = trace_impact(graph, "nonexistent_symbol_xyz")
        assert result is None

    def test_stitch_graphs_namespaces_nodes(self, graph):
        """stitch_graphs should namespace node IDs by repo and merge edges."""
        # Create two copies pretending to be different repos
        g1 = {
            "nodes": {"rule:A": {"id": "rule:A", "type": "rule", "name": "A", "file": "Snakefile"}},
            "edges": [],
            "pipeline_dir": "/fake/repo_alpha",
        }
        g2 = {
            "nodes": {"rule:A": {"id": "rule:A", "type": "rule", "name": "A", "file": "Snakefile"}},
            "edges": [],
            "pipeline_dir": "/fake/repo_beta",
        }

        meta = stitch_graphs([g1, g2])

        # Both should exist under namespaced IDs without collision
        assert "repo_alpha::rule:A" in meta["nodes"]
        assert "repo_beta::rule:A" in meta["nodes"]
        assert meta["pipeline_dir"] == "meta_graph"


# ===========================================================================
# 5. CLI Export Tests
# ===========================================================================


class TestCliExport:
    """Tests for ``bigi.cli.export_html``."""

    def test_export_html_produces_valid_file(self, tmp_path):
        """export_html should write an HTML file containing the serialized graph data."""
        graph_data = {
            "nodes": {
                "rule:test": {"id": "rule:test", "type": "rule", "name": "test", "file": "Snakefile"}
            },
            "edges": [],
            "pipeline_dir": "/tmp/test",
        }
        output = tmp_path / "viz.html"

        export_html(graph_data, str(output))

        assert output.exists()
        content = output.read_text()
        assert "<html" in content.lower() or "<!doctype" in content.lower()
        # The graph data JSON should be embedded in the HTML
        assert "rule:test" in content
        assert "Snakefile" in content
