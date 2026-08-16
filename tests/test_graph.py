import tempfile
import os
import networkx as nx
import pytest
from core.graph_builder import save_graph, load_graph

def test_graph_shortest_path_and_persistence():
    # Build 3-node graph manually
    graph = nx.DiGraph()
    
    graph.add_node("src/routes/user.py", summary="User routes")
    graph.add_node("src/auth/login.py", summary="Login logic")
    graph.add_node("src/db/connection.py", summary="DB Connection")

    graph.add_edge("src/routes/user.py", "src/auth/login.py")
    graph.add_edge("src/auth/login.py", "src/db/connection.py")

    # Verify shortest path
    path = nx.shortest_path(graph, "src/routes/user.py", "src/db/connection.py")
    assert path == ["src/routes/user.py", "src/auth/login.py", "src/db/connection.py"]

    # Test Save and Load
    with tempfile.TemporaryDirectory() as temp_dir:
        json_path = os.path.join(temp_dir, "test_dependency_graph.json")
        saved = save_graph(graph, json_path)
        assert saved is True

        reloaded_graph = load_graph(json_path)
        assert reloaded_graph is not None
        assert reloaded_graph.number_of_nodes() == 3
        assert reloaded_graph.number_of_edges() == 2
        
        reloaded_path = nx.shortest_path(reloaded_graph, "src/routes/user.py", "src/db/connection.py")
        assert reloaded_path == ["src/routes/user.py", "src/auth/login.py", "src/db/connection.py"]
