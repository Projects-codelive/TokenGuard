import os
import tempfile
import pytest
from core.scanner import scan_codebase

def test_scan_codebase_filters():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create valid files
        src_dir = os.path.join(temp_dir, "src")
        os.makedirs(src_dir)
        
        file1 = os.path.join(src_dir, "main.py")
        file2 = os.path.join(src_dir, "auth.js")
        file3 = os.path.join(src_dir, "utils.ts")
        
        with open(file1, "w") as f:
            f.write("print('hello')")
        with open(file2, "w") as f:
            f.write("console.log('auth')")
        with open(file3, "w") as f:
            f.write("export const x = 1;")
            
        # Create ignored folder and files
        nm_dir = os.path.join(temp_dir, "node_modules")
        os.makedirs(nm_dir)
        ignored_file1 = os.path.join(nm_dir, "library.js")
        with open(ignored_file1, "w") as f:
            f.write("module.exports = {}")
            
        lock_file = os.path.join(temp_dir, "package-lock.json")
        with open(lock_file, "w") as f:
            f.write("{}")

        # Perform scan
        scanned_files = scan_codebase(temp_dir)
        
        # Verify exactly the 3 valid files were found
        assert len(scanned_files) == 3
        normalized = [f.replace("\\", "/") for f in scanned_files]
        assert "src/main.py" in normalized
        assert "src/auth.js" in normalized
        assert "src/utils.ts" in normalized
        assert not any("node_modules" in f for f in normalized)
        assert not any("package-lock" in f for f in normalized)
