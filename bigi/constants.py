"""Constants used across the BiGI package."""

# Names of built-in R functions and base-package symbols that should not be
# treated as user-defined function calls when building the call graph.
R_BUILTINS: frozenset[str] = frozenset({
    # Core language syntax and basic creators
    "c", "list", "vector", "matrix", "array", "data.frame", "factor",
    "names", "colnames", "rownames", "dimnames", "dim", "length", "nrow", "ncol",
    "class", "typeof", "mode", "storage.mode", "attributes", "attr", "structure",
    "unname", "levels", "table", "xtabs",
    # Basic math and statistics
    "sum", "mean", "median", "sd", "var", "min", "max", "range", "abs", "round",
    # Type coercion
    "as.character", "as.numeric", "as.integer", "as.logical", "as.factor",
    "as.vector", "as.matrix", "as.data.frame", "as.list",
    # Type predicates
    "is.character", "is.numeric", "is.integer", "is.logical", "is.factor",
    "is.vector", "is.matrix", "is.data.frame", "is.list", "is.null", "is.na",
    # Core type constructors
    "character", "numeric", "integer", "logical", "double",
    # Flow, system, and core input/output
    "library", "require", "source", "return", "stop", "warning", "message",
    "suppressPackageStartupMessages", "suppressWarnings", "suppressMessages",
    "print", "cat", "paste", "paste0", "sprintf", "ifelse", "rep", "seq", "seq_len", "seq_along"
})
