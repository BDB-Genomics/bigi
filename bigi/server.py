import os
import json
import time
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Global state for execution status
execution_state = {
    "nodes": {}, # node_id -> status (running, done, failed)
    "last_updated": time.time()
}

def parse_snakemake_log(log_path: str):
    """Tail a snakemake log and update execution state."""
    if not os.path.exists(log_path):
        return
        
    with open(log_path, 'r', encoding='utf-8') as f:
        # Go to the end of file for tailing if it's already large, 
        # or just read from beginning to replay state.
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
                
            # Basic parsing of Snakemake logs
            if "rule " in line and ":" in line and "Error" not in line:
                match = re.search(r"rule\s+([a-zA-Z0-9_-]+):", line)
                if match:
                    rule_name = match.group(1)
                    execution_state["nodes"][f"rule:{rule_name}"] = "running"
                    execution_state["last_updated"] = time.time()
                    
            if "Finished job" in line or "1 of 1 steps" in line:
                for n, s in list(execution_state["nodes"].items()):
                    if s == "running":
                        execution_state["nodes"][n] = "done"
                        execution_state["last_updated"] = time.time()
                        
            if "Error in rule" in line:
                match = re.search(r"Error in rule\s+([a-zA-Z0-9_-]+):", line)
                if match:
                    rule_name = match.group(1)
                    execution_state["nodes"][f"rule:{rule_name}"] = "failed"
                    execution_state["last_updated"] = time.time()

def parse_nextflow_log(log_path: str):
    """Tail a nextflow log and update execution state."""
    if not os.path.exists(log_path):
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
                
            if "Submitted process >" in line:
                match = re.search(r"Submitted process >\s+([a-zA-Z0-9_-]+)", line)
                if match:
                    proc_name = match.group(1)
                    execution_state["nodes"][f"rule:nf:{proc_name}"] = "running"
                    execution_state["last_updated"] = time.time()
                    
            if "Completed process >" in line or ("INFO" in line and "succeeded" in line):
                match = re.search(r"Completed process >\s+([a-zA-Z0-9_-]+)", line)
                if match:
                    proc_name = match.group(1)
                    execution_state["nodes"][f"rule:nf:{proc_name}"] = "done"
                    execution_state["last_updated"] = time.time()


class BiGIHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, html_path, *args, **kwargs):
        self.html_path = html_path
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(self.html_path, "rb") as f:
                self.wfile.write(f.read())
        elif parsed.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(execution_state).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress logging

def run_server(html_path: str, log_path: str, port: int = 8080):
    """Start the Live Execution Overlay server."""
    
    if log_path:
        if "nextflow" in log_path.lower():
            t = threading.Thread(target=parse_nextflow_log, args=(log_path,), daemon=True)
        else:
            t = threading.Thread(target=parse_snakemake_log, args=(log_path,), daemon=True)
        t.start()
        print(f"Monitoring log file: {log_path}")
    
    def handler(*args, **kwargs):
        return BiGIHTTPRequestHandler(html_path, *args, **kwargs)
    server = HTTPServer(("localhost", port), handler)
    print(f"🚀 Live Execution Overlay server running at http://localhost:{port}/")
    print(f"Serving graph from: {html_path}")
    print("Press Ctrl+C to stop.")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()
