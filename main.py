import argparse
import json
import os
import sys
import webbrowser
import threading
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.json import JSON

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from core.scanner import scan_codebase
from core.parser import parse_file
from core.graph_builder import build_dependency_graph, save_graph, load_graph, print_graph_summary
from core.embedder import embed_codebase
from graph.query_engine import QueryEngine
from utils.logger import get_logger

logger = get_logger()
console = Console()



def run_pipeline(project_path: str, force: bool = False):
    """
    Run full TokenGuard pipeline on project_path: scan, parse, build graph, embed.
    Idempotent: skips re-scan if dependency_graph.json exists unless force=True.
    """
    project_root = Path(project_path).resolve()
    graph_file = project_root / settings.GRAPH_FILENAME

    console.print(Panel(f"[bold cyan]TokenGuard Pipeline[/bold cyan]\nProject: [green]{project_root}[/green]", expand=False))

    # Check idempotency
    if not force and graph_file.exists():
        console.print(f"[yellow]Found existing dependency graph at {graph_file}. Skipping full scan (use --force to re-scan).[/yellow]")
        graph = load_graph(str(graph_file))
        return graph

    # Step 1 — Scan Codebase
    relative_files = scan_codebase(str(project_root))
    if not relative_files:
        console.print("[bold red]No supported source files found to parse.[/bold red]")
        return None

    # Step 2 — Parse Each File
    console.print(f"[bold cyan]Parsing {len(relative_files)} files...[/bold cyan]")
    parsed_metadata_list = []
    success_count = 0

    for rel_path in relative_files:
        meta = parse_file(str(project_root), rel_path)
        parsed_metadata_list.append(meta)
        if meta.summary and not meta.summary.startswith("Failed to read"):
            success_count += 1

    console.print(f"Parsed [bold green]{success_count}/{len(relative_files)}[/bold green] files successfully.")

    # Step 3 — Build Dependency Graph
    graph = build_dependency_graph(parsed_metadata_list, str(project_root))
    save_graph(graph, str(graph_file))

    # Step 4 — Generate Embeddings & Store in ChromaDB
    embed_codebase(parsed_metadata_list, force_reset=force)

    console.print(Panel("[bold green]TokenGuard ready. You can now query this codebase.[/bold green]", expand=False))
    return graph


def run_query_demo(query_text: str, project_path: str):
    """Run natural language task query and display structured results."""
    project_root = Path(project_path).resolve()
    graph_file = project_root / settings.GRAPH_FILENAME

    console.print(f"\n[bold yellow]Executing Query:[/bold yellow] [bold white]\"{query_text}\"[/bold white]\n")

    engine = QueryEngine(graph=load_graph(str(graph_file)) if graph_file.exists() else None)
    result = engine.query(task=query_text, graph_path=str(graph_file) if graph_file.exists() else None)

    # Format output tables and metrics
    table = Table(title="Top Relevant Files", show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Similarity", style="green", justify="right")
    table.add_column("Reason / Extracted Context", style="white")

    for item in result.get("relevant_files", []):
        table.add_row(
            item.get("file", ""),
            f"{item.get('similarity_score', 0.0):.2f}",
            item.get("reason", "")
        )

    console.print(table)

    if result.get("file_relationships"):
        console.print("\n[bold cyan]File Relationships (Import Links):[/bold cyan]")
        for rel in result.get("file_relationships", []):
            console.print(f"  [yellow]*[/yellow] [white]{rel}[/white]")

    console.print(f"\n[bold cyan]Dependency Path:[/bold cyan] {result.get('dependency_path', [])}")
    console.print(f"[bold green]Files to Read ({len(result.get('files_to_read', []))}):[/bold green] {result.get('files_to_read', [])}")
    console.print(f"[bold yellow]Files Skipped:[/bold yellow] {result.get('files_skipped', 0)}")
    console.print(f"[bold magenta]Estimated Tokens Saved:[/bold magenta] ~{result.get('estimated_tokens_saved', 0)} tokens\n")

    console.print("[bold dim]Structured JSON Output:[/bold dim]")
    console.print(JSON(json.dumps(result, indent=2)))


def launch_visualizer(graph_file: Path, host: str = "127.0.0.1", port: int = 8000, hide_isolated: bool = False) -> None:
    """
    Start the FastAPI visualizer server and open the browser.
    Blocks until the user presses Ctrl+C.
    """
    if not graph_file.exists():
        console.print(
            "[bold red]dependency_graph.json not found.[/bold red]\n"
            "Run [cyan]python main.py --project <path>[/cyan] first to build the graph."
        )
        sys.exit(1)

    try:
        import uvicorn
        from api.server import app
    except ImportError as exc:
        console.print(f"[bold red]Import error:[/bold red] {exc}\nInstall with: pip install fastapi uvicorn")
        sys.exit(1)

    url = f"http://{host}:{port}"
    console.print(Panel(
        f"[bold cyan]TokenGuard Visual[/bold cyan] ready\n"
        f"Open -> [link={url}]{url}[/link]\n"
        f"Press [bold]Ctrl+C[/bold] to stop.",
        expand=False,
    ))

    # Auto-open browser after a short delay
    def _open():
        time.sleep(1.2)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    parser = argparse.ArgumentParser(description="TokenGuard - Codebase Dependency Graph & Embedding System")
    parser.add_argument("--project", type=str, default=".", help="Path to project directory to analyze")
    parser.add_argument("--query", type=str, default=None, help="Task description query string")
    parser.add_argument("--force", action="store_true", help="Force full re-scan and re-embedding")
    parser.add_argument("--tree",  action="store_true", help="Print visual dependency graph tree")
    parser.add_argument("--visualize",     action="store_true", help="Launch interactive D3 visual graph in browser")
    parser.add_argument("--hide-isolated", action="store_true", help="Hide isolated nodes (no imports, not imported) in visual")
    parser.add_argument("--port", type=int, default=8000, help="Port for the visualizer server (default: 8000)")

    args = parser.parse_args()

    # ── Visualize mode (does not re-scan) ──────────────────────────────────
    if args.visualize:
        project_root = Path(args.project).resolve()
        graph_file   = project_root / settings.GRAPH_FILENAME
        launch_visualizer(graph_file, port=args.port, hide_isolated=args.hide_isolated)
        return  # server is blocking; nothing below runs

    # ── Step 1–4 Pipeline ──────────────────────────────────────────────────
    graph = run_pipeline(args.project, force=args.force)

    if args.tree and graph:
        print_graph_summary(graph)

    # ── Step 5 Query Demo ──────────────────────────────────────────────────
    if args.query:
        run_query_demo(args.query, args.project)


if __name__ == "__main__":
    main()
