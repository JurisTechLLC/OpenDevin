"""
JurisTech OpenHands Extension - RAG Manager
Local RAG database for indexing and searching the codebase.
Uses ChromaDB for vector storage (runs locally, no external dependencies).
"""

import os
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

# File extensions to index
INDEXABLE_EXTENSIONS = {
    # Programming languages
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    # Web
    ".html", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
    # Config/Data
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".env.example",
    # Documentation
    ".md", ".rst", ".txt",
    # Shell
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    # Database
    ".sql",
}

# Directories to skip
SKIP_DIRECTORIES = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".tox", "eggs", "*.egg-info", ".eggs", "htmlcov",
    ".hypothesis", ".ruff_cache", "target", "vendor", "Pods",
}

# Maximum file size to index (in bytes)
MAX_FILE_SIZE = 1024 * 1024  # 1MB


@dataclass
class CodeChunk:
    """Represents a chunk of code for indexing."""
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    """Represents a search result from the RAG database."""
    chunk: CodeChunk
    score: float
    highlights: List[str]


class RAGManager:
    """
    Manages the local RAG database for codebase indexing.
    Uses ChromaDB for vector storage with sentence-transformers for embeddings.
    """
    
    def __init__(
        self,
        index_path: str = "~/.juristech-openhands/rag_index",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        collection_name: str = "codebase"
    ):
        self.index_path = Path(index_path).expanduser()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.collection_name = collection_name
        
        self._client = None
        self._collection = None
        self._embedding_function = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Track indexed files
        self._file_hashes: Dict[str, str] = {}
        self._hashes_file = self.index_path / "file_hashes.json"
    
    def _ensure_initialized(self) -> None:
        """Ensure ChromaDB is initialized."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
            except ImportError:
                raise ImportError(
                    "ChromaDB is required for RAG functionality. "
                    "Install it with: pip install chromadb"
                )
            
            # Create index directory
            self.index_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB with persistent storage
            self._client = chromadb.PersistentClient(
                path=str(self.index_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            # Load file hashes
            self._load_file_hashes()
    
    def _load_file_hashes(self) -> None:
        """Load file hashes from disk."""
        if self._hashes_file.exists():
            with open(self._hashes_file, "r") as f:
                self._file_hashes = json.load(f)
    
    def _save_file_hashes(self) -> None:
        """Save file hashes to disk."""
        with open(self._hashes_file, "w") as f:
            json.dump(self._file_hashes, f)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file content."""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _get_language(self, file_path: Path) -> str:
        """Determine programming language from file extension."""
        ext = file_path.suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".vue": "vue",
            ".svelte": "svelte",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".rst": "rst",
            ".txt": "text",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".sql": "sql",
        }
        return language_map.get(ext, "text")
    
    def _chunk_content(
        self,
        content: str,
        file_path: str,
        language: str
    ) -> List[CodeChunk]:
        """Split content into chunks for indexing."""
        chunks = []
        lines = content.split("\n")
        
        current_chunk = []
        current_size = 0
        start_line = 1
        
        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > self.chunk_size and current_chunk:
                # Create chunk
                chunk_content = "\n".join(current_chunk)
                chunk_id = hashlib.md5(
                    f"{file_path}:{start_line}:{i-1}".encode()
                ).hexdigest()
                
                chunks.append(CodeChunk(
                    id=chunk_id,
                    file_path=file_path,
                    content=chunk_content,
                    start_line=start_line,
                    end_line=i - 1,
                    language=language,
                    metadata={
                        "file_path": file_path,
                        "language": language,
                        "start_line": start_line,
                        "end_line": i - 1
                    }
                ))
                
                # Start new chunk with overlap
                overlap_lines = int(self.chunk_overlap / 50)  # Approximate lines
                current_chunk = current_chunk[-overlap_lines:] if overlap_lines > 0 else []
                current_size = sum(len(l) + 1 for l in current_chunk)
                start_line = max(1, i - overlap_lines)
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk_id = hashlib.md5(
                f"{file_path}:{start_line}:{len(lines)}".encode()
            ).hexdigest()
            
            chunks.append(CodeChunk(
                id=chunk_id,
                file_path=file_path,
                content=chunk_content,
                start_line=start_line,
                end_line=len(lines),
                language=language,
                metadata={
                    "file_path": file_path,
                    "language": language,
                    "start_line": start_line,
                    "end_line": len(lines)
                }
            ))
        
        return chunks
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Check if file should be indexed."""
        # Check extension
        if file_path.suffix.lower() not in INDEXABLE_EXTENSIONS:
            return False
        
        # Check file size
        try:
            if file_path.stat().st_size > MAX_FILE_SIZE:
                return False
        except OSError:
            return False
        
        # Check if in skip directory
        for part in file_path.parts:
            if part in SKIP_DIRECTORIES:
                return False
        
        return True
    
    def _collect_files(self, directory: Path) -> List[Path]:
        """Collect all indexable files from directory."""
        files = []
        
        for item in directory.rglob("*"):
            if item.is_file() and self._should_index_file(item):
                files.append(item)
        
        return files
    
    async def index_directory(
        self,
        directory: str,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index all code files in a directory.
        
        Args:
            directory: Path to directory to index
            force_reindex: If True, reindex all files even if unchanged
            
        Returns:
            Statistics about the indexing operation
        """
        self._ensure_initialized()
        
        dir_path = Path(directory).expanduser().resolve()
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        # Collect files
        files = self._collect_files(dir_path)
        
        stats = {
            "total_files": len(files),
            "indexed_files": 0,
            "skipped_files": 0,
            "total_chunks": 0,
            "errors": []
        }
        
        for file_path in files:
            try:
                rel_path = str(file_path.relative_to(dir_path))
                file_hash = self._get_file_hash(file_path)
                
                # Check if file needs reindexing
                if not force_reindex and rel_path in self._file_hashes:
                    if self._file_hashes[rel_path] == file_hash:
                        stats["skipped_files"] += 1
                        continue
                
                # Read file content
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Try with different encoding
                    with open(file_path, "r", encoding="latin-1") as f:
                        content = f.read()
                
                # Get language
                language = self._get_language(file_path)
                
                # Chunk content
                chunks = self._chunk_content(content, rel_path, language)
                
                if chunks:
                    # Remove old chunks for this file
                    self._collection.delete(
                        where={"file_path": rel_path}
                    )
                    
                    # Add new chunks
                    self._collection.add(
                        ids=[c.id for c in chunks],
                        documents=[c.content for c in chunks],
                        metadatas=[c.metadata for c in chunks]
                    )
                    
                    stats["total_chunks"] += len(chunks)
                
                # Update file hash
                self._file_hashes[rel_path] = file_hash
                stats["indexed_files"] += 1
                
            except Exception as e:
                stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # Save file hashes
        self._save_file_hashes()
        
        return stats
    
    async def search(
        self,
        query: str,
        n_results: int = 10,
        filter_language: Optional[str] = None,
        filter_path: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search the indexed codebase.
        
        Args:
            query: Search query
            n_results: Maximum number of results to return
            filter_language: Filter by programming language
            filter_path: Filter by file path prefix
            
        Returns:
            List of search results
        """
        self._ensure_initialized()
        
        # Build where clause
        where = {}
        if filter_language:
            where["language"] = filter_language
        if filter_path:
            where["file_path"] = {"$contains": filter_path}
        
        # Search
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert to SearchResult objects
        search_results = []
        
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 1.0
                
                chunk = CodeChunk(
                    id=chunk_id,
                    file_path=metadata.get("file_path", ""),
                    content=document,
                    start_line=metadata.get("start_line", 0),
                    end_line=metadata.get("end_line", 0),
                    language=metadata.get("language", ""),
                    metadata=metadata
                )
                
                # Convert distance to similarity score (cosine distance to similarity)
                score = 1 - distance
                
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    highlights=[]  # Could add highlighting logic here
                ))
        
        return search_results
    
    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 4000,
        n_results: int = 10
    ) -> str:
        """
        Get relevant code context for a query.
        
        Args:
            query: The query to find context for
            max_tokens: Maximum tokens in the context
            n_results: Maximum number of chunks to include
            
        Returns:
            Formatted context string
        """
        results = await self.search(query, n_results=n_results)
        
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Approximate chars per token
        
        for result in results:
            chunk = result.chunk
            chunk_text = f"""
### {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})
```{chunk.language}
{chunk.content}
```
"""
            if total_chars + len(chunk_text) > max_chars:
                break
            
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
        
        if not context_parts:
            return "No relevant code context found."
        
        return "\n".join([
            "## Relevant Code Context",
            "",
            *context_parts
        ])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed codebase."""
        self._ensure_initialized()
        
        return {
            "total_chunks": self._collection.count(),
            "indexed_files": len(self._file_hashes),
            "index_path": str(self.index_path)
        }
    
    def clear_index(self) -> None:
        """Clear the entire index."""
        self._ensure_initialized()
        
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self._file_hashes = {}
        self._save_file_hashes()


# Global RAG manager instance
_rag_manager: Optional[RAGManager] = None


def get_rag_manager(
    index_path: str = "~/.juristech-openhands/rag_index",
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> RAGManager:
    """Get or create the global RAG manager instance."""
    global _rag_manager
    
    if _rag_manager is None:
        _rag_manager = RAGManager(
            index_path=index_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    return _rag_manager
