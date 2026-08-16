import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Set
import networkx as nx
from config.settings import settings
from core.parser import ParsedFileMetadata
from utils.logger import get_logger, log_step

logger = get_logger()


def resolve_import_path(
    current_file: str,
    import_str: str,
    all_files: Set[str]
) -> Optional[str]:
    """
    Resolve an import statement string to an actual file path in the project.
    
    Args:
        current_file: Relative path of the file containing the import.
        import_str: Raw import string (e.g. "./auth", "src.db.connection", "../utils/logger").
        all_files: Set of all valid relative file paths in the project.
        
    Returns:
        Resolved relative file path if matched in project, else None.
    """
    if not import_str:
        return None

    current_dir = Path(current_file).parent
    possible_paths: List[Path] = []

    # 1. Relative import starting with . or ..
    if import_str.startswith("."):
        # Convert module dots in relative imports if any (e.g., ..utils.logger -> ../utils/logger)
        clean_imp = import_str
        if not ("/" in clean_imp or "\\" in clean_imp):
            # E.g. .auth -> ./auth or ..utils -> ../utils
            if clean_imp.startswith(".."):
                clean_imp = "../" + clean_imp[2:].lstrip(".").replace(".", "/")
            elif clean_imp.startswith("."):
                clean_imp = "./" + clean_imp[1:].lstrip(".").replace(".", "/")
        
        target = current_dir / clean_imp
        possible_paths.append(target)
    else:
        # 2. Package / module style import (e.g., src.auth.login or auth/login)
        path_from_str = import_str.replace(".", "/")
        possible_paths.append(current_dir / path_from_str)
        possible_paths.append(Path(path_from_str))

    # Candidate extensions to attempt
    extensions = ["", ".py", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts", "/index.py"]

    for base_target in possible_paths:
        for ext in extensions:
            candidate = str(base_target) + ext
            # Standardize path separators
            candidate_std = os.path.normpath(candidate).replace("\\", "/")
            if candidate_std in all_files:
                return candidate_std

    return None


def build_dependency_graph(
    parsed_files: List[ParsedFileMetadata],
    project_root: str
) -> nx.DiGraph:
    """
    Build a directed NetworkX graph of codebase dependencies.
    
    Nodes represent files; edges represent "file A imports file B".
    
    Args:
        parsed_files: List of ParsedFileMetadata objects.
        project_root: Absolute project root directory.
        
    Returns:
        NetworkX DiGraph object.
    """
    graph = nx.DiGraph()
    all_files_set: Set[str] = {f.file_path for f in parsed_files}

    with log_step("Dependency Graph Construction (Step 3)"):
        try:
            # Step 1: Add all nodes with metadata
            for meta in parsed_files:
                graph.add_node(
                    meta.file_path,
                    file_path=meta.file_path,
                    language=meta.language,
                    functions=meta.functions,
                    classes=meta.classes,
                    imports=meta.imports,
                    summary=meta.summary
                )

            # Step 2: Add directed edges for imports
            edges_added = 0
            for meta in parsed_files:
                for raw_import in meta.imports:
                    target_file = resolve_import_path(meta.file_path, raw_import, all_files_set)
                    if target_file and target_file != meta.file_path:
                        graph.add_edge(meta.file_path, target_file, raw_import=raw_import)
                        edges_added += 1

            logger.info(
                f"Graph built with [bold green]{graph.number_of_nodes()}[/bold green] nodes "
                f"and [bold green]{edges_added}[/bold green] dependency edges."
            )
        except Exception as e:
            logger.error(f"Failed to build dependency graph: {e}")

    return graph


def save_graph(graph: nx.DiGraph, output_path: str) -> bool:
    """Save NetworkX graph to a JSON file."""
    try:
        data = nx.node_link_data(graph)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Dependency graph saved to [bold green]{output_path}[/bold green]")
        return True
    except Exception as e:
        logger.error(f"Failed to save dependency graph to '{output_path}': {e}")
        return False


def load_graph(input_path: str) -> Optional[nx.DiGraph]:
    """Load NetworkX graph from a JSON file."""
    if not os.path.exists(input_path):
        return None
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = nx.node_link_graph(data)
        logger.info(f"Loaded existing dependency graph from [bold green]{input_path}[/bold green]")
        return graph
    except Exception as e:
        logger.warning(f"Could not load graph from '{input_path}': {e}")
        return None


def print_graph_summary(graph: nx.DiGraph):
    """Print an ASCII / Rich visual representation of the dependency graph."""
    from rich.tree import Tree
    from rich.console import Console

    # Force utf-8 output encoding for legacy Windows terminals
    console = Console(force_terminal=True, legacy_windows=False)
    tree = Tree("[bold cyan]Project Dependency Graph[/bold cyan]", guide_style="cyan")

    for node in graph.nodes():
        node_tree = tree.add(f"[bold yellow]{node}[/bold yellow] [dim]({graph.nodes[node].get('language', '')})[/dim]")
        neighbors = list(graph.successors(node))
        if neighbors:
            for target in neighbors:
                imp = graph.edges[node, target].get("raw_import", "imports")
                node_tree.add(f"[dim]-> imports[/dim] [green]{target}[/green] [dim]({imp})[/dim]")

    console.print(tree)
