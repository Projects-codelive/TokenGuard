import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from config.settings import settings
from utils.logger import get_logger

logger = get_logger()

# Tree-sitter import handling
TREE_SITTER_AVAILABLE = False
try:
    from tree_sitter import Language, Parser
    import tree_sitter_python
    import tree_sitter_javascript
    TREE_SITTER_AVAILABLE = True
except Exception as e:
    logger.warning(f"Tree-sitter initialization note: {e}. Will rely on regex fallback.")


@dataclass
class ParsedFileMetadata:
    """Metadata extracted from a single source file."""
    file_path: str  # Relative path to project root
    language: str
    imports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    summary: str = ""
    code_preview: str = ""  # First 100 lines of code


def _detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return "python"
    elif ext in [".js", ".jsx"]:
        return "javascript"
    elif ext in [".ts", ".tsx"]:
        return "typescript"
    return "unknown"


def _extract_summary_regex(content: str, language: str) -> str:
    """Extract first docstring or comment as a one-line summary."""
    lines = content.strip().splitlines()
    if not lines:
        return "No summary available."

    if language == "python":
        # Check for triple quoted module docstring at top
        doc_match = re.search(r'^\s*("""|\'\'\')(.*?)\1', content, re.DOTALL)
        if doc_match:
            clean_doc = doc_match.group(2).strip().splitlines()[0]
            return clean_doc[:120]
        # Check for first top comment
        for line in lines[:10]:
            line_str = line.strip()
            if line_str.startswith("#"):
                return line_str.lstrip("#").strip()[:120]
    else:
        # JS / TS multi-line comment or single-line comment
        js_doc_match = re.search(r'/\*\*(.*?)\*/', content, re.DOTALL)
        if js_doc_match:
            clean_doc = js_doc_match.group(1).replace("*", "").strip().splitlines()[0]
            return clean_doc[:120]
        for line in lines[:10]:
            line_str = line.strip()
            if line_str.startswith("//"):
                return line_str.lstrip("/").strip()[:120]

    return f"{language.capitalize()} source file {Path(content).name if len(content) < 50 else ''}".strip()


def _parse_python_regex(content: str) -> tuple[List[str], List[str], List[str]]:
    """Regex fallback for Python imports, functions, classes."""
    imports = []
    functions = []
    classes = []

    for line in content.splitlines():
        line_clean = line.strip()
        # Imports
        if line_clean.startswith("import "):
            parts = line_clean.replace("import ", "").split(",")
            for p in parts:
                mod = p.strip().split()[0]
                if mod:
                    imports.append(mod)
        elif line_clean.startswith("from "):
            match = re.match(r'from\s+([\w\.]+)\s+import', line_clean)
            if match:
                imports.append(match.group(1))

        # Functions
        func_match = re.match(r'^\s*def\s+([a-zA-Z_]\w*)\s*\(', line)
        if func_match:
            functions.append(func_match.group(1))

        # Classes
        cls_match = re.match(r'^\s*class\s+([a-zA-Z_]\w*)\b', line)
        if cls_match:
            classes.append(cls_match.group(1))

    return list(dict.fromkeys(imports)), list(dict.fromkeys(functions)), list(dict.fromkeys(classes))


def _parse_js_regex(content: str) -> tuple[List[str], List[str], List[str]]:
    """Regex fallback for JS/TS imports, functions, classes."""
    imports = []
    functions = []
    classes = []

    # Imports: import ... from 'path', import 'path', require('path'), import('path')
    import_patterns = [
        r'import\s+(?:.*?\s+from\s+)?[\'"]([^\'"]+)[\'"]',
        r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
    ]
    for pattern in import_patterns:
        for match in re.finditer(pattern, content, re.DOTALL):
            imp = match.group(1)
            if imp:
                imports.append(imp)

    # Functions: function foo() or const foo = () => or const foo = function()
    func_matches = re.findall(
        r'(?:function\s+([a-zA-Z_]\w*)|(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>|(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?function)',
        content
    )
    for m in func_matches:
        fn = m[0] or m[1] or m[2]
        if fn:
            functions.append(fn)

    # Classes: class Foo
    class_matches = re.findall(r'\bclass\s+([a-zA-Z_]\w*)\b', content)
    for c in class_matches:
        classes.append(c)

    return list(dict.fromkeys(imports)), list(dict.fromkeys(functions)), list(dict.fromkeys(classes))


def _parse_with_treesitter(content_bytes: bytes, language: str) -> Optional[tuple[List[str], List[str], List[str]]]:
    """Parse source code using Tree-Sitter AST parser."""
    if not TREE_SITTER_AVAILABLE:
        return None

    try:
        if language == "python":
            lang = Language(tree_sitter_python.language())
        elif language in ["javascript", "typescript"]:
            lang = Language(tree_sitter_javascript.language())
        else:
            return None

        try:
            parser = Parser(lang)
        except TypeError:
            parser = Parser()
            parser.set_language(lang)

        tree = parser.parse(content_bytes)
        root = tree.root_node

        imports, functions, classes = [], [], []

        def traverse(node):
            node_type = node.type

            # Python & JS AST Node checks
            if node_type in ["import_statement", "import_from_statement"]:
                text = node.text.decode("utf-8", errors="ignore")
                match = re.search(r'from\s+([\w\.]+)|import\s+([\w\.]+)', text)
                if match:
                    imports.append(match.group(1) or match.group(2))
            elif node_type in ["import_declaration", "call_expression"]:
                text = node.text.decode("utf-8", errors="ignore")
                # Match ES6 import or CommonJS require/dynamic import
                m1 = re.search(r'from\s+[\'"]([^\'"]+)[\'"]|import\s+[\'"]([^\'"]+)[\'"]', text)
                if m1:
                    imports.append(m1.group(1) or m1.group(2))
                m2 = re.search(r'(?:require|import)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', text)
                if m2:
                    imports.append(m2.group(1))

            elif node_type in ["function_definition", "function_declaration"]:
                for child in node.children:
                    if child.type == "identifier":
                        functions.append(child.text.decode("utf-8", errors="ignore"))
                        break

            elif node_type == "lexical_declaration":
                text = node.text.decode("utf-8", errors="ignore")
                match = re.search(r'(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>', text)
                if match:
                    functions.append(match.group(1))

            elif node_type in ["class_definition", "class_declaration"]:
                for child in node.children:
                    if child.type == "identifier":
                        classes.append(child.text.decode("utf-8", errors="ignore"))
                        break

            for child in node.children:
                traverse(child)

        traverse(root)
        return list(dict.fromkeys(imports)), list(dict.fromkeys(functions)), list(dict.fromkeys(classes))
    except Exception as e:
        logger.debug(f"Tree-sitter parse error ({language}): {e}. Falling back to regex.")
        return None


def parse_file(project_root: str, relative_path: str) -> ParsedFileMetadata:
    """
    Parse a single file using Tree-Sitter with Regex fallback.
    
    Args:
        project_root: Absolute root path of the project.
        relative_path: Relative path of the file to parse.
        
    Returns:
        ParsedFileMetadata object.
    """
    abs_path = Path(project_root) / relative_path
    language = _detect_language(relative_path)
    
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Could not read file '{relative_path}': {e}")
        return ParsedFileMetadata(
            file_path=relative_path,
            language=language,
            summary=f"Failed to read file: {e}"
        )

    lines = content.splitlines()
    code_preview = "\n".join(lines[:100])
    summary = _extract_summary_regex(content, language)

    # Try Tree-Sitter AST Parsing
    ts_result = _parse_with_treesitter(content.encode("utf-8"), language)
    
    if ts_result is not None:
        imports, functions, classes = ts_result
    else:
        # Regex Fallback
        if language == "python":
            imports, functions, classes = _parse_python_regex(content)
        else:
            imports, functions, classes = _parse_js_regex(content)

    return ParsedFileMetadata(
        file_path=relative_path,
        language=language,
        imports=imports,
        functions=functions,
        classes=classes,
        summary=summary,
        code_preview=code_preview
    )
