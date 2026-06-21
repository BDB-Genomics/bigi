"""Command-line interface for BiGI.

Entry point: ``bigi`` (installed via ``console_scripts`` in pyproject.toml).

Sub-commands:
- ``analyze <pipeline_dir>`` — index a pipeline directory.
- ``impact <symbol>``        — trace downstream impact of a rule or R function.
"""

import copy
import json
import os
import sys
import argparse
import tempfile
import subprocess
import urllib.request
import zipfile
from typing import Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .graph import build_graph, save_index, load_index, trace_impact, stitch_graphs
from .render.html_template import HTML_TEMPLATE


def export_html(graph_data: dict, output_path: str, selected_node_id: Optional[str] = None) -> None:
    """Write an interactive HTML visualization of *graph_data* to *output_path*.

    If *selected_node_id* is given, that node is pre-highlighted in the UI.
    """
    data = copy.deepcopy(graph_data)
    data["selected_node_id"] = selected_node_id

    html_content = HTML_TEMPLATE.replace(
        "const graphData = // __DATA__;",
        f"const graphData = {json.dumps(data, indent=2)};",
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def export_graphml(graph_data: dict, output_path: str) -> None:
    """Export the graph to GraphML format."""
    root = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
    
    # Define keys for node attributes
    for key_id, key_type in [("type", "string"), ("name", "string"), ("file", "string")]:
        ET.SubElement(root, "key", id=key_id, **{"for": "node", "attr.name": key_id, "attr.type": key_type})
        
    # Define keys for edge attributes
    for key_id, key_type in [("type", "string"), ("confidence", "string"), ("label", "string")]:
        ET.SubElement(root, "key", id=f"e_{key_id}", **{"for": "edge", "attr.name": key_id, "attr.type": key_type})
        
    graph_elem = ET.SubElement(root, "graph", id="G", edgedefault="directed")
    
    for node_id, node in graph_data.get("nodes", {}).items():
        n = ET.SubElement(graph_elem, "node", id=node_id)
        ET.SubElement(n, "data", key="type").text = node.get("type", "")
        ET.SubElement(n, "data", key="name").text = node.get("name", "")
        if "file" in node:
            ET.SubElement(n, "data", key="file").text = node.get("file", "")
            
    for i, edge in enumerate(graph_data.get("edges", [])):
        e = ET.SubElement(graph_elem, "edge", id=f"e{i}", source=edge["source"], target=edge["target"])
        ET.SubElement(e, "data", key="e_type").text = edge.get("type", "")
        ET.SubElement(e, "data", key="e_confidence").text = edge.get("confidence", "")
        if "label" in edge:
            ET.SubElement(e, "data", key="e_label").text = edge.get("label", "")
            
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xmlstr)


def _fetch_pipeline_dir(pdir: str, temp_dirs: list) -> str:
    """Clones a URL into a temporary directory if needed."""
    is_url = pdir.startswith(("http://", "https://", "git@", "git://"))
    if not is_url:
        if not os.path.exists(pdir):
            raise FileNotFoundError(f"Pipeline directory '{pdir}' does not exist.")
        return pdir

    print(f"Detected remote URL: {pdir}")
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dirs.append(temp_dir_obj)
    target_dir = temp_dir_obj.name

    if pdir.endswith(".zip"):
        print(f"Downloading zip archive from {pdir}...")
        zip_path = os.path.join(target_dir, "archive.zip")
        urllib.request.urlretrieve(pdir, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        contents = os.listdir(target_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(target_dir, contents[0])):
            return os.path.join(target_dir, contents[0])
        return target_dir
    else:
        clone_url = pdir
        if "github.com" in clone_url and "/tree/" in clone_url:
            parts = clone_url.split("/tree/")
            clone_url = parts[0] + ".git"

        print(f"Cloning git repository {clone_url}...")
        result = subprocess.run(["git", "clone", "--depth", "1", clone_url, target_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error cloning repository: {result.stderr}")
        return target_dir


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Execute the ``analyze`` sub-command. Returns an exit code."""
    pipeline_dirs: list = args.pipeline_dir
    temp_dirs = []
    local_dirs = []

    try:
        for pdir in pipeline_dirs:
            local_dirs.append(_fetch_pipeline_dir(pdir, temp_dirs))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        for t in temp_dirs:
            t.cleanup()
        return 1

    graphs = []
    for d in local_dirs:
        print(f"Analyzing genomics pipeline at '{d}'...")
        graphs.append(build_graph(d))

    if len(graphs) == 1:
        combined_graph = graphs[0]
    else:
        print(f"Stitching {len(graphs)} repositories into an Org-Wide Meta-Graph...")
        combined_graph = stitch_graphs(graphs)

    # Save index in current directory if multiple repos or remote URL was indexed
    is_url = pipeline_dirs[0].startswith(("http://", "https://", "git@", "git://"))
    index_dir = os.getcwd() if (len(local_dirs) > 1 or is_url) else local_dirs[0]
    index_path = save_index(combined_graph, index_dir)
    print(f"Analysis complete. Index saved to '{index_path}'.")
    print(f"Indexed {len(combined_graph['nodes'])} nodes and {len(combined_graph['edges'])} edges.")

    if args.html:
        export_html(combined_graph, args.html)
        print(f"Interactive Meta-Graph visualization exported to '{args.html}'.")

    for t in temp_dirs:
        t.cleanup()

    return 0


def _cmd_impact(args: argparse.Namespace) -> int:
    """Execute the ``impact`` sub-command. Returns an exit code."""
    pipeline_dir: str = args.pipeline_dir
    symbol: str = args.symbol_or_rule_name

    graph = load_index(pipeline_dir)
    if graph is None:
        index_path = os.path.join(pipeline_dir, ".bigi_index.json")
        print(f"Error: Index not found at '{index_path}'.", file=sys.stderr)
        print("Please run 'bigi analyze <pipeline_dir>' first to build the index.", file=sys.stderr)
        return 1

    results = trace_impact(graph, symbol)
    if results is None:
        print(f"Error: Symbol or rule '{symbol}' not found in the index.", file=sys.stderr)
        return 1

    print("\n".join(results))

    if args.html:
        selected_node_id: Optional[str] = None
        rule_id = f"rule:{symbol}"
        if rule_id in graph["nodes"]:
            selected_node_id = rule_id
        else:
            func_prefix = f"function:{symbol}@"
            for node_id in graph["nodes"]:
                if node_id.startswith(func_prefix):
                    selected_node_id = node_id
                    break

        export_html(graph, args.html, selected_node_id=selected_node_id)
        print(f"Interactive graph visualization with '{symbol}' highlighted exported to '{args.html}'.")

    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Execute the ``export`` sub-command. Returns an exit code."""
    pipeline_dir: str = args.pipeline_dir
    output_path: str = args.output

    graph = load_index(pipeline_dir)
    if graph is None:
        index_path = os.path.join(pipeline_dir, ".bigi_index.json")
        print(f"Error: Index not found at '{index_path}'.", file=sys.stderr)
        print("Please run 'bigi analyze <pipeline_dir>' first to build the index.", file=sys.stderr)
        return 1

    if output_path.endswith(".graphml"):
        export_graphml(graph, output_path)
        print(f"GraphML exported to '{output_path}'.")
    else:
        print("Error: Unsupported export format. Please use a file with .graphml extension.", file=sys.stderr)
        return 1

    return 0

def _cmd_pr_report(args: argparse.Namespace) -> int:
    """Execute the ``pr-report`` sub-command."""
    pipeline_dir: str = args.pipeline_dir
    output_path: str = args.output

    graph = load_index(pipeline_dir)
    if graph is None:
        index_path = os.path.join(pipeline_dir, ".bigi_index.json")
        print(f"Error: Index not found at '{index_path}'.", file=sys.stderr)
        return 1

    modified_nodes = [node for node in graph.get("nodes", {}).values() if node.get("git_modified")]
    
    if not modified_nodes:
        report = "✅ **BiGI Blast Radius Report**: No modified rules or functions detected in the pipeline."
    else:
        report = "💥 **BiGI Blast Radius Report** 💥\n\n"
        report += "The following rules/functions were modified in this PR. Here is the downstream impact:\n\n"
        
        # Deduplicate by name
        seen_names = set()
        for node in modified_nodes:
            name = node["name"]
            if name in seen_names:
                continue
            seen_names.add(name)
            
            results = trace_impact(graph, name)
            if results:
                # Format as markdown block
                report += f"**Impact of `{name}`**:\n```text\n"
                report += "\n".join(results) + "\n```\n\n"

        report += "*Please ensure all impacted downstream rules have been re-tested before merging.*"

    print(report)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to '{output_path}'.", file=sys.stderr)

    return 0

def _cmd_remediate(args: argparse.Namespace) -> int:
    """Execute the ``remediate`` sub-command."""
    pipeline_dir: str = args.pipeline_dir
    symbol: str = args.symbol_or_rule_name
    prompt: str = args.prompt

    graph = load_index(pipeline_dir)
    if graph is None:
        index_path = os.path.join(pipeline_dir, ".bigi_index.json")
        print(f"Error: Index not found at '{index_path}'.", file=sys.stderr)
        return 1

    results = trace_impact(graph, symbol)
    if results is None:
        print(f"Error: Symbol '{symbol}' not found in the index.", file=sys.stderr)
        return 1

    # Find the code for the symbol
    code_content = None
    file_path = None
    rule_id = f"rule:{symbol}"
    target_node = None
    if rule_id in graph["nodes"]:
        target_node = graph["nodes"][rule_id]
    else:
        func_prefix = f"function:{symbol}@"
        for node_id, node in graph["nodes"].items():
            if node_id.startswith(func_prefix):
                target_node = node
                break
                
    if target_node:
        code_content = target_node.get("code") or target_node.get("script")
        file_path = target_node.get("file")
        
    if not code_content and file_path:
        full_path = os.path.join(pipeline_dir, file_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                code_content = f.read()
        except:
            pass

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        print("Please set your Gemini API key to use the AI Auto-Remediation feature.", file=sys.stderr)
        return 1

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro")
        
        full_prompt = (
            f"You are an AI code remediation assistant. You are tasked with fixing a pipeline issue.\n\n"
            f"Target Symbol/Rule: {symbol}\n"
            f"File: {file_path}\n\n"
            f"User Prompt: {prompt}\n\n"
            f"Downstream Impact (Context):\n" + "\n".join(results) + "\n\n"
        )
        if code_content:
            full_prompt += f"Current Code:\n```\n{code_content}\n```\n\n"
        
        full_prompt += "Please provide the patched code or a detailed suggested fix. Only output the corrected code and a brief explanation."
        
        print(f"🤖 Analyzing impact for '{symbol}' and generating remediation strategy with Gemini...")
        response = model.generate_content(full_prompt)
        print("\n✨ AI Remediation Suggestion:\n")
        print(response.text)
        
    except ImportError:
        print("Error: 'google-generativeai' package not installed.", file=sys.stderr)
        print("Please install it via 'pip install google-generativeai' to use this feature.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during AI generation: {e}", file=sys.stderr)
        return 1
        
    return 0

def _cmd_monitor(args: argparse.Namespace) -> int:
    """Execute the ``monitor`` sub-command."""
    html_path = args.html
    log_path = args.log
    port = args.port
    
    if not os.path.exists(html_path):
        print(f"Error: HTML file '{html_path}' not found.", file=sys.stderr)
        return 1
        
    from .server import run_server
    run_server(html_path, log_path, port)
    return 0

def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate sub-command."""
    parser = argparse.ArgumentParser(
        description=(
            "BiGI: BDB-Genomics Impact Graph — trace downstream impact across "
            "Snakemake pipelines and R code."
        )
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")

    export_parser = subparsers.add_parser(
        "export",
        help="Export the analyzed index to other graph formats (e.g. GraphML).",
    )
    export_parser.add_argument(
        "output",
        help="Path to export the graph (must end in .graphml).",
    )
    export_parser.add_argument(
        "--pipeline-dir",
        default=".",
        help="Path to the pipeline directory containing the built index (default: current directory).",
    )

    pr_report_parser = subparsers.add_parser(
        "pr-report",
        help="Generate a markdown report of downstream impacts for all git-modified files (useful for CI/CD).",
    )
    pr_report_parser.add_argument(
        "--pipeline-dir",
        default=".",
        help="Path to the pipeline directory containing the built index (default: current directory).",
    )
    pr_report_parser.add_argument(
        "--output",
        help="Path to save the generated markdown report.",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Index the pipeline directory and build the combined graph.",
    )
    analyze_parser.add_argument(
        "pipeline_dir",
        nargs='+',
        help="Path(s) to the pipeline directories or git URLs to analyze. Pass multiple inputs to generate an Org-Wide Meta-Graph.",
    )
    analyze_parser.add_argument(
        "--html",
        help="Path to export the interactive HTML visualization.",
    )

    impact_parser = subparsers.add_parser(
        "impact",
        help="Trace the downstream impact of changing a rule or R function.",
    )
    impact_parser.add_argument(
        "symbol_or_rule_name",
        help="Name of the Snakemake rule or R function to query.",
    )
    impact_parser.add_argument(
        "--pipeline-dir",
        default=".",
        help="Path to the pipeline directory containing the built index (default: current directory).",
    )
    impact_parser.add_argument(
        "--html",
        help="Path to export the interactive HTML visualization of the impact.",
    )

    remediate_parser = subparsers.add_parser(
        "remediate",
        help="AI Auto-Remediation: suggest code patches using LLM considering pipeline impact.",
    )
    remediate_parser.add_argument(
        "symbol_or_rule_name",
        help="Name of the Snakemake rule or R function to remediate.",
    )
    remediate_parser.add_argument(
        "--prompt",
        required=True,
        help="The prompt describing the issue or required change.",
    )
    remediate_parser.add_argument(
        "--pipeline-dir",
        default=".",
        help="Path to the pipeline directory containing the built index (default: current directory).",
    )

    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Live Execution Overlay: serve graph HTML and stream live execution status.",
    )
    monitor_parser.add_argument(
        "--html",
        required=True,
        help="Path to the BiGI interactive HTML file.",
    )
    monitor_parser.add_argument(
        "--log",
        help="Path to the Snakemake or Nextflow log file to tail.",
    )
    monitor_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTP server port.",
    )

    args_list = sys.argv[1:]
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # The manual cloning interceptor block has been moved inside _fetch_pipeline_dir

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "analyze": _cmd_analyze,
        "impact": _cmd_impact,
        "export": _cmd_export,
        "pr-report": _cmd_pr_report,
        "remediate": _cmd_remediate,
        "monitor": _cmd_monitor,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
