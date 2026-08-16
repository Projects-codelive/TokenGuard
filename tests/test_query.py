import pytest
from unittest.mock import MagicMock, patch
import networkx as nx
from graph.query_engine import QueryEngine

def test_query_engine_response_structure():
    # Build 3-node graph
    graph = nx.DiGraph()
    graph.add_node("src/auth/login.py")
    graph.add_node("src/db/connection.py")
    graph.add_node("src/routes/user.py")
    
    graph.add_edge("src/routes/user.py", "src/auth/login.py")
    graph.add_edge("src/auth/login.py", "src/db/connection.py")

    # Mock ChromaDB Collection
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "metadatas": [[
            {
                "file_path": "src/auth/login.py",
                "summary": "User authentication",
                "functions": "login, logout",
                "imports": "db.py"
            },
            {
                "file_path": "src/db/connection.py",
                "summary": "Database connectivity",
                "functions": "get_connection",
                "imports": ""
            }
        ]],
        "distances": [[0.09, 0.25]]
    }

    mock_chroma_client = MagicMock()
    mock_chroma_client.get_collection.return_value = mock_collection

    with patch("chromadb.PersistentClient", return_value=mock_chroma_client):
        engine = QueryEngine(graph=graph, persist_dir="./test_chroma_db")
        result = engine.query(task="change the user login logic")

        # Verify exact required key structure
        assert "task" in result
        assert "relevant_files" in result
        assert "dependency_path" in result
        assert "files_to_read" in result
        assert "files_skipped" in result
        assert "estimated_tokens_saved" in result

        assert result["task"] == "change the user login logic"
        assert len(result["relevant_files"]) == 2
        assert result["relevant_files"][0]["file"] == "src/auth/login.py"
        assert isinstance(result["files_skipped"], int)
        assert isinstance(result["estimated_tokens_saved"], int)
