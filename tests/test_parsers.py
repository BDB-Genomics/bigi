import os
import pytest
import subprocess
import shutil
import tempfile
import json
from bigi.parsers.generic import parse_generic_file
from bigi.parsers.snakemake import parse_snakemake_file

# Check if Rscript is available
has_rscript = shutil.which("Rscript") is not None

def test_generic_parser():
    """Test the regex-based generic AST parser using a dummy JavaScript script."""
    dummy_code = '''
function my_function(a, b) {
    console.log("hello");
}

my_function(1, 2);
other_function();
    '''
    test_file = "/tmp/test_dummy.js"
    with open(test_file, "w") as f:
        f.write(dummy_code)
        
    try:
        res = parse_generic_file(test_file, "/tmp")
        defs, calls = res["definitions"], res["calls"]
        
        # Verify function definition
        assert len(defs) == 1
        assert defs[0]["name"] == "my_function"
        
        # Verify function calls
        call_names = [c["name"] for c in calls]
        assert "my_function" in call_names
        assert "other_function" in call_names
        assert "log" in call_names
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


@pytest.mark.skipif(not has_rscript, reason="Rscript not installed")
def test_r_parser():
    """Test the R AST parser with standard and complex/anonymous R code structure."""
    dummy_code = """
    # Standard assignment
    my_fun <- function(a) {
      print(a)
    }

    # Call it
    my_fun(10)

    # Anonymous / nested function that has no assignment operator as parent
    lapply(1:10, function(x) { x * 2 })
    
    # Nested function definition with assignment in complex structure
    # to ensure LHS detection doesn't crash with NA node IDs
    nested_list <- list(
      sub_fun = function(y) {
        return(y)
      }
    )
    """
    
    with tempfile.NamedTemporaryFile(suffix=".R", mode="w", delete=False) as tf:
        tf.write(dummy_code)
        temp_r_file = tf.name
        
    try:
        # Resolve r_parser.R path relative to tests directory
        parser_r_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bigi", "parsers", "r_parser.R")
        
        # We pass the temporary R file inside a JSON array, as r_parser.R expects
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as json_tf:
            json.dump([temp_r_file], json_tf)
            temp_json_file = json_tf.name
            
        try:
            res = subprocess.run(
                ["Rscript", parser_r_path, temp_json_file, tempfile.gettempdir()],
                capture_output=True, text=True, check=True
            )
            parsed_data = json.loads(res.stdout)
            
            defs = parsed_data.get("definitions", [])
            calls = parsed_data.get("calls", [])
            
            def_names = [d["name"] for d in defs]
            assert "my_fun" in def_names
            
            call_names = [c["name"] for c in calls]
            assert "my_fun" in call_names
            assert "lapply" in call_names
            assert "print" in call_names
            
        finally:
            if os.path.exists(temp_json_file):
                os.remove(temp_json_file)
    finally:
        if os.path.exists(temp_r_file):
            os.remove(temp_r_file)


def test_gitignore_matching():
    """Test that GitIgnore helper parses and matches paths correctly."""
    from bigi.gitignore import GitIgnore
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a .gitignore file
        gitignore_path = os.path.join(tmpdir, ".gitignore")
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "*.log",
                "node_modules/",
                "build/",
                "temp-dir",
                "!important.log",
                "/relative-only",
                "nested/**/docs",
            ]))
            
        gitignore = GitIgnore(tmpdir)
        
        # Test basic wildcards
        assert gitignore.is_ignored(os.path.join(tmpdir, "test.log")) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "important.log")) is False
        assert gitignore.is_ignored(os.path.join(tmpdir, "subdir", "test.log")) is True
        
        # Test directory only rules
        assert gitignore.is_ignored(os.path.join(tmpdir, "node_modules"), is_dir=True) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "node_modules"), is_dir=False) is False
        assert gitignore.is_ignored(os.path.join(tmpdir, "node_modules", "foo.js"), is_dir=False) is True
        
        # Test basic relative checks
        assert gitignore.is_ignored(os.path.join(tmpdir, "relative-only"), is_dir=False) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "subdir", "relative-only"), is_dir=False) is False
        
        # Test double star matching
        assert gitignore.is_ignored(os.path.join(tmpdir, "nested", "docs"), is_dir=True) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "nested", "foo", "docs"), is_dir=True) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "nested", "foo", "bar", "docs"), is_dir=True) is True
        assert gitignore.is_ignored(os.path.join(tmpdir, "docs"), is_dir=True) is False


def test_parser_respects_gitignore():
    """Test that build_graph and parsers respect .gitignore rules during analysis."""
    from bigi.graph import build_graph
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files
        os.makedirs(os.path.join(tmpdir, "ignored_dir"))
        os.makedirs(os.path.join(tmpdir, "active_dir"))
        
        # 1. Ignored directory file
        with open(os.path.join(tmpdir, "ignored_dir", "func1.py"), "w", encoding="utf-8") as f:
            f.write("def ignored_function():\n    pass\n")
            
        # 2. Ignored file extension
        with open(os.path.join(tmpdir, "active_dir", "temp.log"), "w", encoding="utf-8") as f:
            f.write("Some log entries\n")
            
        # 3. Active file
        with open(os.path.join(tmpdir, "active_dir", "main.py"), "w", encoding="utf-8") as f:
            f.write("def active_function():\n    pass\n")
            
        # 4. Create .gitignore
        with open(os.path.join(tmpdir, ".gitignore"), "w", encoding="utf-8") as f:
            f.write("ignored_dir/\n*.log\n")
            
        # Build the graph
        graph = build_graph(tmpdir)
        
        # Nodes should only contain active_function and NOT ignored_function
        node_names = []
        for node_id, node in graph.get("nodes", {}).items():
            if node.get("type") == "function":
                node_names.append(node.get("name"))
                
        assert "active_function" in node_names
        assert "ignored_function" not in node_names


def test_generic_parser_supports_any_text_file():
    """Test that generic parser falls back to default spec for unrecognized text file extensions."""
    from bigi.parsers.generic import parse_generic_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with a completely random/unrecognized extension containing PHP or Ruby style func definition
        random_file = os.path.join(tmpdir, "script.xyz")
        with open(random_file, "w", encoding="utf-8") as f:
            f.write("def custom_xyz_func(x, y) {\n  some_xyz_call(x);\n}\n")
            
        res = parse_generic_file(random_file, tmpdir)
        defs = res["definitions"]
        calls = res["calls"]
        
        # Verify function definition
        assert len(defs) == 1
        assert defs[0]["name"] == "custom_xyz_func"
        
        # Verify function calls
        call_names = [c["name"] for c in calls]
        assert "some_xyz_call" in call_names
