"""Extract file structure (declarations with line ranges) using tree-sitter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sc": "scala",
    ".toml": "toml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".lua": "lua",
    ".bash": "bash",
    ".sh": "bash",
    ".zsh": "bash",
    ".dart": "dart",
    ".zig": "zig",
    ".r": "r",
    ".R": "r",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".ex": "elixir",
    ".exs": "elixir",
    ".heex": "heex",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".nim": "nim",
    ".nimble": "nim",
    ".v": "v",
    ".d": "d",
    ".elm": "elm",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".fs": "fsharp",
    ".fsi": "fsharp",
    ".fsx": "fsharp",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".sol": "solidity",
    ".proto": "proto",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "scss",
    ".less": "css",
    ".vue": "vue",
    ".svelte": "svelte",
    ".astro": "astro",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".prisma": "prisma",
    ".hcl": "hcl",
    ".tf": "hcl",
    ".tfvars": "hcl",
    ".nix": "nix",
    ".rst": "rst",
    ".md": "markdown",
    ".make": "make",
    ".mk": "make",
    ".cmake": "cmake",
    ".dockerfile": "dockerfile",
    ".rkt": "racket",
    ".jl": "julia",
    ".jsonnet": "jsonnet",
    ".libsonnet": "jsonnet",
    ".groovy": "groovy",
    ".gy": "groovy",
    ".gd": "gdscript",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".vim": "vim",
    ".xml": "xml",
}

_DECL_NODE_TYPES: dict[str, list[str]] = {
    "python": ["class_definition", "function_definition"],
    "javascript": ["class_declaration", "function_declaration"],
    "typescript": ["class_declaration", "function_declaration"],
    "tsx": ["class_declaration", "function_declaration"],
    "go": ["type_declaration", "func_declaration"],
    "rust": ["struct_item", "enum_item", "impl_item", "function_item"],
    "java": ["class_declaration", "interface_declaration", "method_declaration"],
    "ruby": ["class", "module", "method"],
    "c": ["struct_specifier", "function_definition"],
    "cpp": ["class_specifier", "function_definition"],
    "csharp": ["class_declaration", "struct_declaration", "method_declaration"],
    "php": ["class_declaration", "function_definition"],
    "swift": ["class_declaration", "struct_declaration", "function_declaration"],
    "kotlin": ["class_declaration", "function_declaration"],
    "scala": ["class_definition", "object_definition", "function_definition"],
    "toml": ["table", "table_array_element", "pair"],
    "json": ["pair"],
    "yaml": ["block_mapping_pair", "block_sequence_item"],
    "lua": ["function_definition", "local_function_definition"],
    "bash": ["function_definition"],
    "dart": ["class_declaration", "function_declaration"],
    "zig": ["FnProto", "VarDecl", "ContainerDecl"],
    "r": ["function_definition"],
    "haskell": ["function_declaration", "type_declaration"],
    "julia": ["function_definition", "struct_definition", "module_definition"],
    "elixir": ["module_definition", "function_definition"],
    "erlang": ["function_declaration", "attribute"],
    "nim": ["proc_def", "func_def", "type_def", "const_def"],
    "v": ["fn_declaration", "struct_declaration"],
    "d": ["function_declaration", "class_declaration", "struct_declaration"],
    "elm": ["function_declaration", "type_alias_declaration", "type_declaration"],
    "clojure": ["deflibrary", "defn", "defmacro", "defprotocol"],
    "fsharp": ["module_declaration", "type_declaration", "let_binding"],
    "ocaml": ["value_definition", "type_definition", "module_definition"],
    "solidity": ["contract_declaration", "function_definition"],
    "proto": ["message_definition", "service_definition"],
    "sql": ["create_table_stmt", "create_view_stmt"],
    "html": ["element"],
    "css": ["rule_set"],
    "scss": ["rule_set", "mixin_declaration"],
    "vue": ["component_definition"],
    "svelte": ["script_element"],
    "astro": ["element"],
    "graphql": ["operation_definition", "type_definition"],
    "prisma": ["model_block", "enum_block"],
    "hcl": ["block"],
    "nix": ["binding", "inherit"],
    "rst": ["section"],
    "markdown": ["atx_heading", "setext_heading"],
    "make": ["rule"],
    "cmake": ["function_definition", "macro_definition"],
    "dockerfile": ["instruction"],
    "racket": ["function_definition", "definition"],
    "groovy": ["class_declaration", "function_declaration"],
    "gdscript": ["class_declaration", "function_definition"],
    "powershell": ["function_definition"],
    "xml": ["element"],
}

_MAX_DEPTH: dict[str, int] = {
    "json": 3,
    "yaml": 5,
}


@dataclass
class Declaration:
    """A named declaration with 1-based line range."""

    kind: str
    name: str
    start_line: int
    end_line: int


_NAME_NODE_TYPES = frozenset(
    (
        "identifier",
        "name",
        "property_identifier",
        "bare_key",
        "quoted_key",
        "dotted_key",
        "string",
        "plain_scalar",
        "string_scalar",
    )
)


def _get_node_name(node: Any, source_bytes: bytes) -> str:
    """Extract identifier name from a tree-sitter node."""
    try:
        for child in node.children:
            if hasattr(child, "type") and child.type in _NAME_NODE_TYPES:
                raw = source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
                if child.type == "string" and len(raw) >= 2 and raw[0] == raw[-1] == '"':
                    return raw[1:-1]
                return raw
            name = _get_node_name(child, source_bytes)
            if name:
                return name
    except (AttributeError, IndexError):
        pass
    return ""


def _walk_declarations(
    node: Any,
    source_bytes: bytes,
    lang: str,
    decls: list[Declaration],
    *,
    depth: int = 0,
    max_depth: int | None = None,
) -> None:
    """Collect top-level declarations (limited depth to avoid nested methods)."""
    limit = max_depth if max_depth is not None else _MAX_DEPTH.get(lang, 1)
    if depth > limit:
        return
    try:
        node_type = getattr(node, "type", None)
        if not node_type:
            return
        decl_types = _DECL_NODE_TYPES.get(lang, [])
        if node_type in decl_types:
            name = _get_node_name(node, source_bytes) or f"<{node_type}>"
            start_row, _ = node.start_point
            end_row, _ = node.end_point
            decls.append(
                Declaration(
                    kind=node_type,
                    name=name,
                    start_line=start_row + 1,
                    end_line=end_row + 1,
                )
            )
        for child in node.children:
            _walk_declarations(
                child, source_bytes, lang, decls, depth=depth + 1, max_depth=limit
            )
    except (AttributeError, IndexError) as exc:
        logger.debug("tree-sitter walk error: %s", exc)


_TINY_FILE_THRESHOLD = 500


def get_file_structure(content: str, path: str) -> str:
    """
    Parse file with tree-sitter and return structure (declarations with line ranges).

    Args:
        content: File content.
        path: File path for extension detection.

    Returns:
        Formatted structure string with 1-based line indices and a hint to use
        read_file with start/end for specific spans.
    """
    lines = content.splitlines()
    total = len(lines)
    if len(content) < _TINY_FILE_THRESHOLD:
        return (
            f"File: {path} ({total} lines)\n"
            "File too small for structure. Call read_file with start and end (e.g. start=1, end="
            f"{total}) to read the file.\n"
        )

    try:
        from tree_sitter_language_pack import get_parser
    except ImportError as e:
        logger.warning("tree-sitter-language-pack not available: %s", e)
        return (
            f"File: {path} ({total} lines)\n"
            f"No tree-sitter support. Call read_file with start and end (1-based line numbers) to read specific sections.\n"
        )

    ext = "" if "." not in path else "." + path.rsplit(".", 1)[-1].lower()
    lang = _EXT_TO_LANG.get(ext)
    if not lang:
        return (
            f"File: {path} ({total} lines)\n"
            "Unsupported extension for structure. Call read_file with start and end to read specific sections.\n"
        )

    try:
        parser = get_parser(cast(Any, lang))
    except Exception as exc:
        logger.debug("tree-sitter parser for %s: %s", lang, exc)
        return (
            f"File: {path} ({total} lines)\n"
            f"No parser for {lang}. Call read_file with start and end to read specific sections.\n"
        )

    source_bytes = content.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    decls: list[Declaration] = []
    _walk_declarations(root, source_bytes, lang, decls)

    if not decls:
        return (
            f"File: {path} ({total} lines)\n"
            f"No top-level declarations found. Call read_file with start and end (e.g. start=1, end={total}) to read the file.\n"
        )

    parts = [f"File: {path} ({total} lines)"]
    for d in decls:
        parts.append(f"  {d.kind} {d.name} (lines {d.start_line}-{d.end_line})")
    parts.append(
        "\nTo read specific content, call read_file with start and end (1-based line numbers)."
    )
    return "\n".join(parts)
