"""Code execution skill for Jarvis."""
import asyncio
import subprocess
import tempfile
import os
from typing import Any, Dict

from src.skills.registry import Skill


class CodeSkill(Skill):
    """Code execution skill for multiple languages."""

    name = "code"
    description = "Execute code in Python, JavaScript, Bash, and other languages"
    triggers = ["run", "execute", "code", "python", "javascript", "bash", "script", "calc", "calculate"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute code."""
        text = context.get("text", "") if context else ""
        code = params.get("code", self._extract_code(text))
        language = params.get("language", self._detect_language(text, code))

        if not code:
            return "What code would you like me to run?"

        return await self._run_code(code, language)

    def _extract_code(self, text: str) -> str:
        """Extract code from text."""
        import re
        # Look for code blocks
        code_block = re.search(r'```(?:\w+)?\n(.*?)\n```', text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # Look for inline code
        inline = re.search(r'`([^`]+)`', text)
        if inline:
            return inline.group(1)

        # Try to extract after trigger words
        for trigger in ["run", "execute", "code", "python", "javascript", "bash"]:
            idx = text.lower().find(trigger)
            if idx >= 0:
                return text[idx + len(trigger):].strip()

        return ""

    def _detect_language(self, text: str, code: str) -> str:
        """Detect programming language."""
        text_lower = text.lower()
        if "python" in text_lower or "py " in text_lower:
            return "python"
        if "javascript" in text_lower or "js " in text_lower or "node" in text_lower:
            return "javascript"
        if "bash" in text_lower or "shell" in text_lower or "sh " in text_lower:
            return "bash"

        # Heuristic based on code content
        if "import " in code or "def " in code or "print(" in code:
            return "python"
        if "console.log" in code or "const " in code or "let " in code or "=>" in code:
            return "javascript"
        if code.startswith("#!/bin") or any(c in code for c in ["ls ", "cd ", "echo ", "grep "]):
            return "bash"

        return "python"  # Default

    async def _run_code(self, code: str, language: str) -> str:
        """Run code in specified language."""
        try:
            if language == "python":
                return await self._run_python(code)
            elif language == "javascript":
                return await self._run_javascript(code)
            elif language == "bash":
                return await self._run_bash(code)
            else:
                return f"Unsupported language: {language}"
        except Exception as e:
            return f"Execution error: {e}"

    async def _run_python(self, code: str) -> str:
        """Run Python code."""
        # Create a safe execution environment
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                'python', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            if error:
                output += f"\n[stderr]\n{error}"
            return output.strip() or "[No output]"
        finally:
            os.unlink(temp_file)

    async def _run_javascript(self, code: str) -> str:
        """Run JavaScript code with Node.js."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                'node', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            if error:
                output += f"\n[stderr]\n{error}"
            return output.strip() or "[No output]"
        finally:
            os.unlink(temp_file)

    async def _run_bash(self, code: str) -> str:
        """Run Bash script."""
        # Safety check - don't run dangerous commands
        dangerous = ['rm -rf', 'dd ', 'mkfs', 'format ', 'fdisk', '> /dev/sd', 'chmod 777']
        code_lower = code.lower()
        for d in dangerous:
            if d in code_lower:
                return f"Blocked dangerous command: {d}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n" + code)
            temp_file = f.name

        try:
            os.chmod(temp_file, 0o755)
            proc = await asyncio.create_subprocess_exec(
                'bash', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            if error:
                output += f"\n[stderr]\n{error}"
            return output.strip() or "[No output]"
        finally:
            os.unlink(temp_file)