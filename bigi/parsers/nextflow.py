"""Nextflow workflow parser for BiGI.

Parses Nextflow .nf files to extract processes, inputs/outputs, and script bindings.
"""

import os
import re

def parse_nextflow_file(file_path: str, base_dir: str) -> dict:
    """Parse a single Nextflow workflow file (.nf)."""
    rel_path = os.path.relpath(file_path, base_dir)
    processes = {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}")
        return {}
        
    pos = 0
    while True:
        match = re.search(r"\bprocess\s+([a-zA-Z0-9_]+)\s*\{", content[pos:])
        if not match:
            break
            
        proc_name = match.group(1)
        start_idx = pos + match.end()
        
        brace_count = 1
        end_idx = start_idx
        while end_idx < len(content) and brace_count > 0:
            char = content[end_idx]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
            end_idx += 1
            
        block_content = content[start_idx:end_idx-1]
        pos = end_idx
        
        inputs = []
        outputs = []
        script_cmd = ""
        
        input_match = re.search(r"input:\s*([\s\S]*?)(?:output:|script:|shell:|exec:|\Z)", block_content)
        if input_match:
            in_block = input_match.group(1)
            for line in in_block.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] in ("val", "path", "file", "set", "tuple"):
                    inputs.append(parts[-1])
                    
        output_match = re.search(r"output:\s*([\s\S]*?)(?:input:|script:|shell:|exec:|\Z)", block_content)
        if output_match:
            out_block = output_match.group(1)
            for line in out_block.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] in ("val", "path", "file", "set", "tuple", "stdout"):
                    outputs.append(parts[-1])
                    
        script_match = re.search(r"(?:script|shell):\s*(?:\"\"\"([\s\S]*?)\"\"\"|\"([\s\S]*?)\"|'([\s\S]*?)'|(\S+))", block_content)
        if script_match:
            script_cmd = next((g for g in script_match.groups() if g is not None), "").strip()
            
        script_file = ""
        # Look for explicit runner calls: Rscript, python, perl, julia, bash, sh, etc.
        runner_match = re.search(
            r"\b(?:Rscript|source|python3?|perl|julia|bash|sh)\s+([a-zA-Z0-9_\-\.\/]+\.[a-zA-Z0-9]+)",
            script_cmd,
            re.IGNORECASE
        )
        if runner_match:
            script_file = runner_match.group(1)
        else:
            # Fallback to finding any script with code/script extensions in the script block
            matches = re.findall(
                r"\b([a-zA-Z0-9_\-\./]+\.(?:r|py|sh|bash|pl|pm|jl|m|rb|js|ts|rs|go|c|cpp|cc|cxx|h|hpp))\b",
                script_cmd,
                re.IGNORECASE
            )
            if matches:
                script_file = matches[0]
            else:
                template_match = re.search(r"template\s+['\"]([^'\"]+)['\"]", block_content)
                if template_match:
                    script_file = os.path.join("templates", template_match.group(1))

        ext = os.path.splitext(script_file)[1].lower() if script_file else ""
        processes[proc_name] = {
            "file": rel_path,
            "input": inputs,
            "output": outputs,
            "r_script": script_file if ext in (".r", ".rscript") else None,
            "py_script": script_file if ext == ".py" else None,
            "script": script_file or None,
            "raw_script": script_cmd
        }
        
    return processes

def parse_nextflow_pipeline(directory_path: str) -> dict:
    """Scan directory recursively for Nextflow .nf files and parse processes."""
    directory_path = os.path.abspath(directory_path)
    rules = {}
    for root, _, files in os.walk(directory_path):
        for f in files:
            if f.endswith(".nf"):
                file_path = os.path.join(root, f)
                res = parse_nextflow_file(file_path, directory_path)
                rules.update(res)
    return rules
