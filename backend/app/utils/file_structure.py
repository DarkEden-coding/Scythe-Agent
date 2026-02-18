"""Extract file structure (declarations with line ranges) using tree-sitter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
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
    ".scala": "scala",
}

_DECL_NODE_TYPES: dict[str, list[str]] = {
    "python": ["class_definition", "function_definition"],
    "javascript": ["class_declaration", "function_declaration"],
    "typescript": ["class_declaration", "function_declaration"],
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
}


@dataclass
class Declaration:
    """A named declaration with 1-based line range."""

    kind: str
    name: str
    start_line: int
    end_line: int


def _get_node_name(node: Any, source_bytes: bytes) -> str:
    """Extract identifier name from a tree-sitter node."""
    try:
        for child in node.children:
            if hasattr(child, "type") and child.type in ("identifier", "name", "property_identifier"):
                return source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
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
    max_depth: int = 1,
) -> None:
    """Collect top-level declarations (limited depth to avoid nested methods)."""
    if depth > max_depth:
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
                child, source_bytes, lang, decls, depth=depth + 1, max_depth=max_depth
            )
    except (AttributeError, IndexError) as exc:
        logger.debug("tree-sitter walk error: %s", exc)


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
    try:
        from tree_sitter_language_pack import get_parser  # type: ignore[import-untyped]
    except ImportError as e:
        logger.warning("tree-sitter-language-pack not available: %s", e)
        lines = content.splitlines()
        return (
            f"File: {path} ({len(lines)} lines)\n"
            f"No tree-sitter support. Call read_file with start and end (1-based line numbers) to read specific sections.\n"
        )

    ext = "" if "." not in path else "." + path.rsplit(".", 1)[-1].lower()
    lang = _EXT_TO_LANG.get(ext)
    if not lang:
        lines = content.splitlines()
        return (
            f"File: {path} ({len(lines)} lines)\n"
            "Unsupported extension for structure. Call read_file with start and end to read specific sections.\n"
        )

    try:
        parser = get_parser(lang)
    except Exception as exc:
        logger.debug("tree-sitter parser for %s: %s", lang, exc)
        lines = content.splitlines()
        return (
            f"File: {path} ({len(lines)} lines)\n"
            f"No parser for {lang}. Call read_file with start and end to read specific sections.\n"
        )

    source_bytes = content.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    decls: list[Declaration] = []
    _walk_declarations(root, source_bytes, lang, decls)

    lines = content.splitlines()
    total = len(lines)

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
