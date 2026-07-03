"""
Code Index Service
==================
Scans project files recursively and extracts code symbols (classes, interfaces,
methods, enums, imports) using Python AST and regular expression lexers.
"""

from __future__ import annotations
import ast
import re
import logging
from pathlib import Path

from project.workspace import ProjectWorkspace

log = logging.getLogger(__name__)

class CodeIndexService:
    """
    Scans a source tree and populates symbol indexes inside a workspace.
    """

    def __init__(self, workspace: ProjectWorkspace) -> None:
        self.workspace = workspace
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the code symbols indexing table in the workspace database."""
        self.workspace.db.execute(
            """
            CREATE TABLE IF NOT EXISTS code_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                symbol_name TEXT NOT NULL,
                symbol_type TEXT NOT NULL, -- Class, Interface, Enum, Method, Import
                line_number INTEGER NOT NULL,
                parent_class TEXT,
                content TEXT
            );
            """
        )

    def index_project(self, source_dir: str | Path) -> dict:
        """
        Recursively scan the source directory and index all code symbols.
        """
        source_path = Path(source_dir).resolve()
        if not source_path.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

        log.info(f"CodeIndexService: starting scan of directory {source_path}")
        
        # Clear previous index
        self.workspace.db.execute("DELETE FROM code_symbols")
        
        total_files = 0
        total_symbols = 0
        
        for file_path in source_path.rglob("*"):
            if not file_path.is_file():
                continue
                
            # Skip hidden folders / virtual envs
            parts = file_path.parts
            if any(p.startswith(".") or p in ("node_modules", "venv", ".venv", "__pycache__") for p in parts):
                continue
                
            ext = file_path.suffix.lower()
            if ext not in (".py", ".cs", ".js", ".ts"):
                continue
                
            total_files += 1
            rel_path = str(file_path.relative_to(source_path)).replace("\\", "/")
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                symbols = self._parse_file(ext, rel_path, content)
                
                if symbols:
                    self._save_symbols(symbols)
                    total_symbols += len(symbols)
            except Exception as e:
                log.error(f"CodeIndexService: failed to index {rel_path}: {e}")
                
        log.info(f"CodeIndexService: scan complete. Indexed {total_symbols} symbols across {total_files} files.")
        return {
            "total_files": total_files,
            "total_symbols": total_symbols
        }

    def _parse_file(self, ext: str, rel_path: str, content: str) -> list[dict]:
        """Route parsing based on file extension."""
        if ext == ".py":
            return self._parse_python(rel_path, content)
        elif ext == ".cs":
            return self._parse_csharp(rel_path, content)
        elif ext in (".js", ".ts"):
            return self._parse_javascript(rel_path, content)
        return []

    def _parse_python(self, rel_path: str, content: str) -> list[dict]:
        """Parse Python files using native AST module."""
        symbols = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
            
        class ASTVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_class = None
                
            def visit_ClassDef(self, node: ast.ClassDef):
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": node.name,
                    "symbol_type": "Class",
                    "line_number": node.lineno,
                    "parent_class": None,
                    "content": f"class {node.name}"
                })
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
                
            def visit_FunctionDef(self, node: ast.FunctionDef):
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": node.name,
                    "symbol_type": "Method",
                    "line_number": node.lineno,
                    "parent_class": self.current_class,
                    "content": f"def {node.name}"
                })
                self.generic_visit(node)
                
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": node.name,
                    "symbol_type": "Method",
                    "line_number": node.lineno,
                    "parent_class": self.current_class,
                    "content": f"async def {node.name}"
                })
                self.generic_visit(node)
                
            def visit_Import(self, node: ast.Import):
                for name in node.names:
                    symbols.append({
                        "file_path": rel_path,
                        "symbol_name": name.name,
                        "symbol_type": "Import",
                        "line_number": node.lineno,
                        "parent_class": None,
                        "content": f"import {name.name}"
                    })
                    
            def visit_ImportFrom(self, node: ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    symbols.append({
                        "file_path": rel_path,
                        "symbol_name": f"{module}.{name.name}",
                        "symbol_type": "Import",
                        "line_number": node.lineno,
                        "parent_class": None,
                        "content": f"from {module} import {name.name}"
                    })
                    
        visitor = ASTVisitor()
        visitor.visit(tree)
        return symbols

    def _parse_csharp(self, rel_path: str, content: str) -> list[dict]:
        """Parse C# files using regular expressions."""
        symbols = []
        lines = content.splitlines()
        
        current_class = None
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("//"):
                continue
                
            # Class, Interface, Enum matches
            class_match = re.search(r'\b(class|interface|enum)\s+(\w+)', line_stripped)
            if class_match:
                s_type = class_match.group(1).capitalize()
                s_name = class_match.group(2)
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": s_name,
                    "symbol_type": s_type,
                    "line_number": i,
                    "parent_class": None,
                    "content": line_stripped
                })
                if s_type == "Class":
                    current_class = s_name
                continue
                
            # Method matches: e.g. public void Start() or public async Task Update()
            method_match = re.search(
                r'\b(public|private|protected|internal)?\s*(static|virtual|override|async)?\s+([\w\<\>\[\]]+)\s+(\w+)\s*\(', 
                line_stripped
            )
            if method_match:
                m_name = method_match.group(4)
                # Filter out standard keywords that might match
                if m_name not in ("if", "for", "while", "switch", "using", "catch", "lock"):
                    symbols.append({
                        "file_path": rel_path,
                        "symbol_name": m_name,
                        "symbol_type": "Method",
                        "line_number": i,
                        "parent_class": current_class,
                        "content": line_stripped
                    })
                    
            # Using directive (Imports)
            using_match = re.search(r'^using\s+([\w\.]+);', line_stripped)
            if using_match:
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": using_match.group(1),
                    "symbol_type": "Import",
                    "line_number": i,
                    "parent_class": None,
                    "content": line_stripped
                })
                
        return symbols

    def _parse_javascript(self, rel_path: str, content: str) -> list[dict]:
        """Parse JavaScript and TypeScript files using regular expressions."""
        symbols = []
        lines = content.splitlines()
        
        current_class = None
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("//") or line_stripped.startswith("/*"):
                continue
                
            # Class, Interface matches
            class_match = re.search(r'\b(class|interface)\s+(\w+)', line_stripped)
            if class_match:
                s_type = class_match.group(1).capitalize()
                s_name = class_match.group(2)
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": s_name,
                    "symbol_type": s_type,
                    "line_number": i,
                    "parent_class": None,
                    "content": line_stripped
                })
                if s_type == "Class":
                    current_class = s_name
                continue
                
            # Function matches: function hello()
            func_match = re.search(r'\bfunction\s+(\w+)\s*\(', line_stripped)
            if func_match:
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": func_match.group(1),
                    "symbol_type": "Method",
                    "line_number": i,
                    "parent_class": None,
                    "content": line_stripped
                })
                continue
                
            # Class Method matches: constructor() or update()
            # E.g. start() { or async update() {
            method_match = re.search(r'^(async\s+)?(\w+)\s*\(.*\)\s*\{', line_stripped)
            if method_match:
                m_name = method_match.group(2)
                if m_name not in ("if", "for", "while", "switch", "catch", "function"):
                    symbols.append({
                        "file_path": rel_path,
                        "symbol_name": m_name,
                        "symbol_type": "Method",
                        "line_number": i,
                        "parent_class": current_class,
                        "content": line_stripped
                    })
                    
            # ES6 Import statement
            import_match = re.search(r'^import\s+.*from\s+[\'"](.*)[\'"]', line_stripped)
            if import_match:
                symbols.append({
                    "file_path": rel_path,
                    "symbol_name": import_match.group(1),
                    "symbol_type": "Import",
                    "line_number": i,
                    "parent_class": None,
                    "content": line_stripped
                })
                
        return symbols

    def _save_symbols(self, symbols: list[dict]) -> None:
        """Batch save extracted symbols into the workspace database."""
        sql = """
            INSERT INTO code_symbols (file_path, symbol_name, symbol_type, line_number, parent_class, content)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        seq = [
            (s["file_path"], s["symbol_name"], s["symbol_type"], s["line_number"], s["parent_class"], s["content"])
            for s in symbols
        ]
        self.workspace.db.execute_many(sql, seq)

    def search_symbols(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search indexed code symbols by name or signature content.
        """
        query_cleaned = query.strip().replace("'", "").replace('"', "")
        if not query_cleaned:
            return []
            
        sql = """
            SELECT file_path, symbol_name, symbol_type, line_number, parent_class, content
            FROM code_symbols
            WHERE symbol_name LIKE ? OR content LIKE ?
            LIMIT ?
        """
        pattern = f"%{query_cleaned}%"
        cursor = self.workspace.db.execute(sql, (pattern, pattern, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        return results
