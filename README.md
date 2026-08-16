# TokenGuard — Codebase Dependency Graph + Visual Explorer

TokenGuard is an intelligent middleware system that sits between developers and LLM coding agents.
It scans a codebase, builds a dependency graph, stores vector embeddings, and serves only the minimal
required context for any developer task — saving thousands of tokens per query.

It also ships with a **live interactive dependency graph** you can explore in the browser.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AST Parsing | `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript` + Regex fallback |
| Graph Engine | `NetworkX` — directed graph & shortest path |
| Vector Store | `ChromaDB` — local on-disk embeddings |
| Embeddings | OpenAI `text-embedding-3-small` via `LangChain` |
| Visualizer | `FastAPI` + `D3.js` force-directed graph |
| Logging / CLI | `Rich` — colored terminal output |

---

## Project Structure

```
TokenGuard/
├── api/
│   └── server.py            # FastAPI server — serves graph data + frontend
├── config/
│   └── settings.py          # All env vars and constants in one place
├── core/
│   ├── scanner.py           # Step 1 — walks folder, filters files
│   ├── parser.py            # Step 2 — tree-sitter + regex extraction
│   ├── graph_builder.py     # Step 3 — builds and saves NetworkX graph
│   └── embedder.py          # Step 4 — generates and stores embeddings in ChromaDB
├── graph/
│   └── query_engine.py      # Step 5 — takes a task, returns relevant file paths
├── visualizer/
│   ├── graph_processor.py   # Transforms graph JSON into D3 format
│   └── static/
│       └── index.html       # The entire frontend in one self-contained file
├── utils/
│   └── logger.py            # Rich-based colored logger
├── tests/                   # Pytest test suite
├── main.py                  # CLI entry point
├── requirements.txt
└── README.md
```

---

## Prerequisites

- **Python 3.10+** — [download here](https://www.python.org/downloads/)
- **Git** — [download here](https://git-scm.com/)
- **OpenAI API key** — [get one here](https://platform.openai.com/api-keys)

---

## Setup (from scratch)

### Step 1 — Clone the repo

```bash
git clone https://github.com/Projects-codelive/TokenGuard.git
cd TokenGuard
```

### Step 2 — Create a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

> You should see `(.venv)` at the start of your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create your `.env` file

Create a file named `.env` in the project root (same folder as `main.py`):

```bash
# Windows
copy NUL .env

# macOS / Linux
touch .env
```

Open `.env` and add your keys:

```env
OPENAI_API_KEY=sk-proj-your_real_key_here
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./chroma_db
LOG_LEVEL=INFO
```

> `.env` is in `.gitignore` — it will never be committed. Keep your key secret.

---

## Running TokenGuard

### Option A — Scan + Index a codebase

Point TokenGuard at any project folder on your machine:

```bash
python main.py --project /path/to/any/project
```

This will:
1. Scan all `.py`, `.js`, `.ts`, `.jsx`, `.tsx` files
2. Parse functions, classes, imports from each file
3. Build a dependency graph → saved as `dependency_graph.json`
4. Generate embeddings for every file → stored in `chroma_db/`
5. Print `TokenGuard ready. You can now query this codebase.`

To scan TokenGuard itself (great for testing):

```bash
python main.py --project .
```

To force a full re-scan (ignore cached graph):

```bash
python main.py --project . --force
```

---

### Option B — Query the codebase

After scanning, run a natural language query:

```bash
python main.py --project . --query "change the user login validation logic"
```

Output:

```json
{
  "task": "change the user login validation logic",
  "relevant_files": [
    {
      "file": "src/auth/login.py",
      "reason": "contains login(), validate_token() — imports from db.py",
      "similarity_score": 0.91
    }
  ],
  "dependency_path": ["src/routes/user.py", "src/auth/login.py", "src/db/connection.py"],
  "files_to_read": ["src/auth/login.py", "src/db/connection.py"],
  "files_skipped": 47,
  "estimated_tokens_saved": 18400
}
```

---

### Option C — Launch the Visual Graph Explorer

```bash
python main.py --visualize
```

> **Requires** that a scan has been run first (`dependency_graph.json` must exist).

Opens **http://127.0.0.1:8000** in your browser automatically.

#### Visual features:
| Feature | How to use |
|---|---|
| **Hover a node** | Highlights connections in gold, dims everything else |
| **Click a node** | Opens detail panel — functions, classes, imports, source preview |
| **Search bar** | Type a filename or function name — graph filters live |
| **Folder filter pills** | Click `core`, `utils`, etc. to isolate a folder |
| **Find Path** | Click a node → "Set as Start", click another → "Set as End" → Find Path |
| **Zoom / Pan** | Scroll to zoom, drag background to pan, double-click to reset |

Other flags:
```bash
# Use a different port
python main.py --visualize --port 8080

# Hide files with no connections
python main.py --visualize --hide-isolated
```

---

## Running Tests

```bash
# Windows
.venv\Scripts\python.exe -m pytest tests/ -v

# macOS / Linux
python -m pytest tests/ -v
```

---

## What the `.gitignore` blocks

These files are **never committed** — safe by design:

| Blocked | Reason |
|---|---|
| `.env` | Contains your API key |
| `.env.example` | Excluded to avoid accidental key leaks |
| `chroma_db/` | Local vector store — large and machine-specific |
| `dependency_graph.json` | Generated output — recreated on each scan |
| `.venv/` | Python virtual environment |
| `__pycache__/` | Compiled Python bytecode |

---

## Quick Reference

```bash
# Full pipeline: scan → parse → graph → embed
python main.py --project .

# Query
python main.py --project . --query "your task here"

# Visual graph in browser
python main.py --visualize

# Force re-scan
python main.py --project . --force

# Run tests
python -m pytest tests/ -v
```
