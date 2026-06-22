"""Snakemake pipeline parser.

Walks a pipeline directory, finds all Snakefiles/smk files, and extracts
rule metadata (inputs, outputs, scripts, shell commands, and resolved R
script paths).
"""

import re
import os
from typing import Optional


def find_snakemake_files(pipeline_dir: str) -> list[str]:
    """Return paths of all Snakefile / *.smk / *.snakefile files under *pipeline_dir*."""
    files: list[str] = []
    for root, _, filenames in os.walk(pipeline_dir):
        for f in filenames:
            if f == "Snakefile" or f.endswith(".smk") or f.endswith(".snakefile"):
                files.append(os.path.join(root, f))
    return files


def _save_section(rule: dict, section: str, content_lines: list[str]) -> None:
    """Flush a collected section block into *rule*.

    Handles ``input``/``output`` path extraction (stripping config lookups and
    format-string quotes), and ``script``/``shell`` assignment.
    """
    content = " ".join(content_lines).strip()
    if section in ("input", "output"):
        # Strip config["a"]["b"] or config['a']['b'] dict lookups
        cleaned = re.sub(r'\b[a-zA-Z0-9_]+(?:\[["\'][^"\']+["\']\])+', "", content)
        # Strip .get("key") calls
        cleaned = re.sub(r'\b[a-zA-Z0-9_]+\.get\(["\'][^"\']+["\']\)', "", cleaned)
        # Strip quotes inside curly braces to keep format strings clean
        def _strip_quotes(match: re.Match) -> str:
            return "{" + match.group(1).replace("'", "").replace('"', "") + "}"
        cleaned = re.sub(r'\{([^}]+)\}', _strip_quotes, cleaned)

        paths = re.findall(r'["\']([^"\']+)["\']', cleaned)
        filtered = [p for p in paths if any(c in p for c in ("/", ".", "{", "}"))]
        rule[section].extend(filtered)

    elif section == "script":
        paths = re.findall(r'["\']([^"\']+)["\']', content)
        if paths:
            rule["script"] = paths[0]

    elif section == "shell":
        paths = re.findall(r'["\']([^"\']+)["\']', content)
        rule["shell"] = paths[0] if paths else content

    elif section in ("conda", "container"):
        paths = re.findall(r'["\']([^"\']+)["\']', content)
        rule[section] = paths[0] if paths else content


def parse_snakemake_file(file_path: str, base_dir: str) -> dict[str, dict]:
    """Parse a single Snakemake file and return a mapping of rule name → rule dict.

    Each rule dict contains:
    - ``name``: rule name
    - ``file``: path relative to *base_dir*
    - ``input``/``output``: lists of path strings
    - ``script``: script value if a ``script:`` section is present
    - ``shell``: shell command if a ``shell:`` section is present
    - ``r_script``: resolved R script path relative to *base_dir* (or ``None``)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    rules: dict[str, dict] = {}
    current_rule: Optional[dict] = None
    current_section: Optional[str] = None
    section_content: list[str] = []

    rule_re = re.compile(r"^rule\s+([a-zA-Z0-9_]+)\s*:")
    section_re = re.compile(
        r"^\s*(input|output|params|log|benchmark|threads|resources|conda|container"
        r"|singularity|envmodules|wildcard_constraints|message|wrapper|script"
        r"|notebook|shadow|run|shell|cwl|handover|cache|priority|retries|group)\s*:(.*)"
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        match = rule_re.match(line)
        if match:
            if current_rule and current_section:
                _save_section(current_rule, current_section, section_content)
            rule_name = match.group(1)
            current_rule = {
                "name": rule_name,
                "file": os.path.relpath(file_path, base_dir),
                "input": [],
                "output": [],
                "script": None,
                "shell": None,
                "conda": None,
                "container": None,
                "r_script": None,
            }
            rules[rule_name] = current_rule
            current_section = None
            section_content = []
            i += 1
            continue

        if current_rule is not None:
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                if current_section:
                    _save_section(current_rule, current_section, section_content)
                current_rule = None
                current_section = None
                continue

            section_match = section_re.match(line)
            if section_match:
                if current_section:
                    _save_section(current_rule, current_section, section_content)
                current_section = section_match.group(1)
                inline = section_match.group(2).strip()
                section_content = [inline] if inline else []
            else:
                if current_section:
                    section_content.append(stripped)

        i += 1

    if current_rule and current_section:
        _save_section(current_rule, current_section, section_content)

    # Resolve script paths relative to base_dir
    rule_dir = os.path.dirname(file_path)
    for rule in rules.values():
        script_val: Optional[str] = rule["script"] or None
        if not script_val and rule["shell"]:
            matches = re.findall(
                r"\b([a-zA-Z0-9_\-\./]+\.(?:r|py|sh|bash|pl|pm|jl|m|rb|js|ts|rs|go|c|cpp|cc|cxx|h|hpp))\b",
                rule["shell"],
                re.IGNORECASE
            )
            if matches:
                script_val = matches[0]
        if script_val:
            full_path = os.path.normpath(os.path.join(rule_dir, script_val))
            rel_path = os.path.relpath(full_path, base_dir)
            rule["script"] = rel_path
            
            ext = os.path.splitext(rel_path)[1].lower()
            if ext in (".r", ".rscript"):
                rule["r_script"] = rel_path
            elif ext == ".py":
                rule["py_script"] = rel_path

    return rules


def parse_pipeline(pipeline_dir: str) -> dict[str, dict]:
    """Parse all Snakemake files in *pipeline_dir* and return a combined rule mapping."""
    all_rules: dict[str, dict] = {}
    for f in find_snakemake_files(pipeline_dir):
        all_rules.update(parse_snakemake_file(f, pipeline_dir))
    return all_rules
