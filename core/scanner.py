import os
from pathlib import Path
from typing import List
from config.settings import settings
from utils.logger import get_logger, log_step

logger = get_logger()

def scan_codebase(project_path: str) -> List[str]:
    """
    Walk through project_path and collect all supported source files.
    
    Args:
        project_path: Absolute or relative path to project root.
        
    Returns:
        List of relative file paths (relative to project_path).
    """
    project_root = Path(project_path).resolve()
    if not project_root.exists() or not project_root.is_dir():
        logger.error(f"Project directory '{project_path}' does not exist or is not a directory.")
        return []

    collected_files: List[str] = []

    with log_step("Codebase Scanning (Step 1)"):
        try:
            for root, dirs, files in os.walk(project_root):
                # Filter out ignored directories in-place
                dirs[:] = [
                    d for d in dirs
                    if d not in settings.IGNORE_FOLDERS and not d.startswith(".")
                ]
                
                for file_name in files:
                    try:
                        file_path = Path(root) / file_name
                        ext = file_path.suffix.lower()
                        
                        # Skip binary / lock files and unsupported extensions
                        if ext in settings.IGNORE_FILE_EXTENSIONS:
                            continue
                            
                        if ext in settings.SUPPORTED_EXTENSIONS:
                            relative_path = os.path.relpath(file_path, project_root)
                            # Standardize path separators to forward slash for cross-platform consistency
                            standardized_rel_path = relative_path.replace("\\", "/")
                            collected_files.append(standardized_rel_path)
                    except Exception as exc:
                        logger.warning(f"Failed to process file path '{file_name}': {exc}")
                        continue

            logger.info(f"Scan complete: Found [bold green]{len(collected_files)}[/bold green] source files in project.")
        except Exception as e:
            logger.error(f"Error during codebase scan: {e}")

    return collected_files
