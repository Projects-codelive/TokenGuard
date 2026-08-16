# TokenGuard — Feature 1: Codebase Dependency Graph + Embedding System

TokenGuard is an intelligent middleware system designed to sit between developers and LLM coding agents. Its primary goal is to eliminate token waste by scanning a codebase, understanding file dependencies, creating local vector embeddings, and serving only the minimal required context for any developer task.

---

## Tech Stack

- **AST Parsing**: `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript` + Regex Fallback
- **Graph Engine**: `NetworkX` (directed graph & shortest path routing)
- **Vector Database**: `ChromaDB` (local vector storage on disk)
- **Embeddings**: OpenAI `text-embedding-3-small` (via `LangChain` wrapper)
- **UI & Logging**: `Rich` (colored console logs & tables)
- **API Framework**: `FastAPI` + `Uvicorn`

---

## Directory Structure

```
tokenguard/
├── config/
│   ├── __init__.py
│   └── settings.py          # Environment variables & constants
├── core/
│   ├── __init__.py
│   ├── scanner.py           # Step 1 — File walking & filtering
│   ├── parser.py            # Step 2 — Tree-sitter + Regex parser
│   ├── graph_builder.py     # Step 3 — NetworkX graph construction & JSON persistence
│   └── embedder.py          # Step 4 — ChromaDB vector persistence
├── graph/
│   ├── __init__.py
│   └── query_engine.py      # Step 5 — Natural language query interface & FastAPI app
├── utils/
│   ├── __init__.py
│   └── logger.py            # Rich-based logger & timer
├── tests/
│   ├── test_scanner.py
│   ├── test_parser.py
│   ├── test_graph.py
│   └── test_query.py
├── main.py                  # CLI Entry point
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quickstart Setup

### 1. Create Virtual Environment (`.venv`)
*All packages MUST be installed exclusively within `.venv` as per project policy.*

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./chroma_db
LOG_LEVEL=INFO
```

---

## Usage

### 1. Scan and Index a Codebase

To index any codebase directory:
```bash
python main.py --project /path/to/target/project
```

To force a fresh re-scan (ignoring cached graph and vector database):
```bash
python main.py --project /path/to/target/project --force
```

### 2. Query Codebase for Task Context

```bash
python main.py --project /path/to/target/project --query "change the user login validation logic"
```

### 3. Output Format Example

```json
{
  "task": "change the user login validation logic",
  "relevant_files": [
    {
      "file": "src/auth/login.py",
      "reason": "Module to validate user login details; functions: validate_login; imports: database",
      "similarity_score": 0.91
    }
  ],
  "dependency_path": [
    "src/routes/user.py",
    "src/auth/login.py",
    "src/db/connection.py"
  ],
  "files_to_read": ["src/auth/login.py", "src/db/connection.py"],
  "files_skipped": 47,
  "estimated_tokens_saved": 18400
}
```

---

## Running Automated Tests

Run the test suite using pytest inside `.venv`:

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -v
```
