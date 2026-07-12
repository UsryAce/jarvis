"""Files skill for Jarvis."""
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from src.skills.registry import Skill


class FilesSkill(Skill):
    """File operations skill."""

    name = "files"
    description = "File system operations: read, write, list, search, copy, move, delete"
    triggers = ["file", "folder", "directory", "read", "write", "list", "find", "search", "copy", "move", "delete"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute file operations."""
        text = context.get("text", "").lower() if context else ""
        path = params.get("path", ".")

        if "read" in text or "cat" in text:
            return await self._read_file(path)
        elif "write" in text or "create" in text:
            content = params.get("content", "")
            return await self._write_file(path, content)
        elif "list" in text or "ls" in text or "dir" in text:
            return await self._list_files(path)
        elif "find" in text or "search" in text:
            pattern = params.get("pattern", "*")
            return await self._find_files(path, pattern)
        elif "copy" in text or "cp" in text:
            dest = params.get("dest", "")
            return await self._copy_file(path, dest)
        elif "move" in text or "mv" in text or "rename" in text:
            dest = params.get("dest", "")
            return await self._move_file(path, dest)
        elif "delete" in text or "remove" in text or "rm" in text:
            return await self._delete_file(path)
        elif "mkdir" in text or "make directory" in text:
            return await self._make_directory(path)
        else:
            return await self._list_files(path)

    async def _read_file(self, path: str) -> str:
        """Read file contents."""
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return f"File not found: {path}"
            if p.is_dir():
                return f"Is a directory: {path}"

            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > 5000:
                return content[:5000] + f"\n... (truncated, {len(content)} total chars)"
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    async def _write_file(self, path: str, content: str) -> str:
        """Write content to file."""
        try:
            p = Path(path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written to {path} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing file: {e}"

    async def _list_files(self, path: str) -> str:
        """List files in directory."""
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return f"Path not found: {path}"
            if not p.is_dir():
                return f"Not a directory: {path}"

            items = []
            for item in sorted(p.iterdir()):
                if item.is_dir():
                    items.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    items.append(f"📄 {item.name} ({self._format_size(size)})")

            if not items:
                return "Directory is empty"
            return f"Contents of {path}:\n" + "\n".join(items)
        except Exception as e:
            return f"Error listing files: {e}"

    async def _find_files(self, path: str, pattern: str) -> str:
        """Find files matching pattern."""
        try:
            p = Path(path).expanduser().resolve()
            matches = list(p.rglob(pattern))
            if not matches:
                return f"No files matching '{pattern}' in {path}"

            results = []
            for m in matches[:50]:
                rel = m.relative_to(p)
                if m.is_dir():
                    results.append(f"📁 {rel}/")
                else:
                    results.append(f"📄 {rel}")

            if len(matches) > 50:
                results.append(f"... and {len(matches) - 50} more")
            return f"Found {len(matches)} matches:\n" + "\n".join(results)
        except Exception as e:
            return f"Error finding files: {e}"

    async def _copy_file(self, src: str, dest: str) -> str:
        """Copy file or directory."""
        try:
            src_p = Path(src).expanduser().resolve()
            dest_p = Path(dest).expanduser().resolve()

            if src_p.is_dir():
                shutil.copytree(src_p, dest_p)
            else:
                dest_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dest_p)
            return f"Copied {src} to {dest}"
        except Exception as e:
            return f"Error copying: {e}"

    async def _move_file(self, src: str, dest: str) -> str:
        """Move/rename file or directory."""
        try:
            src_p = Path(src).expanduser().resolve()
            dest_p = Path(dest).expanduser().resolve()
            dest_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_p), str(dest_p))
            return f"Moved {src} to {dest}"
        except Exception as e:
            return f"Error moving: {e}"

    async def _delete_file(self, path: str) -> str:
        """Delete file or directory."""
        try:
            p = Path(path).expanduser().resolve()
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return f"Deleted {path}"
        except Exception as e:
            return f"Error deleting: {e}"

    async def _make_directory(self, path: str) -> str:
        """Create directory."""
        try:
            p = Path(path).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            return f"Created directory: {path}"
        except Exception as e:
            return f"Error creating directory: {e}"

    def _format_size(self, size: int) -> str:
        """Format file size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"