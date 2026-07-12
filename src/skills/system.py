"""System skill for Jarvis - system operations."""
import os
import platform
import psutil
import subprocess
from typing import Any, Dict

from src.skills.registry import Skill
from src.config import config


class SystemSkill(Skill):
    """System information and control skill."""

    name = "system"
    description = "System information, processes, and control"
    triggers = ["system", "cpu", "memory", "disk", "process", "uptime", "hostname", "ip", "network"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute system commands."""
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "info":
            return self._get_system_info()
        elif action == "cpu":
            return self._get_cpu_info()
        elif action == "memory":
            return self._get_memory_info()
        elif action == "disk":
            return self._get_disk_info()
        elif action == "processes":
            return self._get_processes(params.get("limit", 10))
        elif action == "uptime":
            return self._get_uptime()
        elif action == "network":
            return self._get_network_info()
        elif action == "shell":
            command = params.get("command", "")
            if not command:
                return "No command specified"
            return await self._run_shell(command)
        else:
            return self._get_system_info()

    def _detect_action(self, text: str) -> str:
        """Detect action from text."""
        if any(w in text for w in ["cpu", "processor"]):
            return "cpu"
        if any(w in text for w in ["memory", "ram", "mem"]):
            return "memory"
        if any(w in text for w in ["disk", "storage", "space"]):
            return "disk"
        if any(w in text for w in ["process", "task", "running"]):
            return "processes"
        if "uptime" in text:
            return "uptime"
        if any(w in text for w in ["network", "ip", "connection"]):
            return "network"
        if any(w in text for w in ["shell", "cmd", "command", "run "]):
            return "shell"
        return "info"

    def _get_system_info(self) -> str:
        """Get general system info."""
        uname = platform.uname()
        boot_time = psutil.boot_time()
        import datetime
        boot_str = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"🖥️ **System Information**\n"
            f"OS: {uname.system} {uname.release}\n"
            f"Hostname: {uname.node}\n"
            f"Architecture: {uname.machine}\n"
            f"Processor: {uname.processor}\n"
            f"Python: {platform.python_version()}\n"
            f"Boot time: {boot_str}\n"
            f"CPU cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical"
        )

    def _get_cpu_info(self) -> str:
        """Get CPU information."""
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        freq = psutil.cpu_freq()

        return (
            f"🔧 **CPU Information**\n"
            f"Usage per core: {', '.join(f'{p}%' for p in cpu_percent)}\n"
            f"Average: {sum(cpu_percent)/len(cpu_percent):.1f}%\n"
            f"Current freq: {freq.current:.0f} MHz\n"
            f"Min/Max: {freq.min:.0f} / {freq.max:.0f} MHz\n"
            f"Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count()} logical"
        )

    def _get_memory_info(self) -> str:
        """Get memory information."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return (
            f"💾 **Memory Information**\n"
            f"Total: {self._format_bytes(mem.total)}\n"
            f"Available: {self._format_bytes(mem.available)}\n"
            f"Used: {self._format_bytes(mem.used)} ({mem.percent}%)\n"
            f"Free: {self._format_bytes(mem.free)}\n"
            f"Swap: {self._format_bytes(swap.used)}/{self._format_bytes(swap.total)} ({swap.percent}%)"
        )

    def _get_disk_info(self) -> str:
        """Get disk information."""
        partitions = psutil.disk_partitions()
        lines = ["💿 **Disk Information**"]

        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                lines.append(
                    f"{part.device} ({part.mountpoint}) [{part.fstype}]\n"
                    f"  Total: {self._format_bytes(usage.total)} | "
                    f"Used: {self._format_bytes(usage.used)} ({usage.percent}%) | "
                    f"Free: {self._format_bytes(usage.free)}"
                )
            except PermissionError:
                lines.append(f"{part.device} - Permission denied")

        return "\n".join(lines)

    def _get_processes(self, limit: int = 10) -> str:
        """Get top processes by CPU."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] > 0:
                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        top = processes[:limit]

        lines = [f"⚙️ **Top {limit} Processes by CPU**"]
        for p in top:
            lines.append(f"PID {p['pid']:>6} | {p['cpu_percent']:>5.1f}% CPU | {p['memory_percent']:>5.1f}% MEM | {p['name']}")

        return "\n".join(lines)

    def _get_uptime(self) -> str:
        """Get system uptime."""
        import time
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        return f"⏱️ **Uptime**: {days}d {hours}h {minutes}m"

    def _get_network_info(self) -> str:
        """Get network information."""
        interfaces = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        lines = ["🌐 **Network Interfaces**"]
        for name, addrs in interfaces.items():
            if name in stats and stats[name].isup:
                lines.append(f"\n{name} (UP):")
                for addr in addrs:
                    if addr.family == 2:  # IPv4
                        lines.append(f"  IPv4: {addr.address}")
                    elif addr.family == 10:  # IPv6
                        lines.append(f"  IPv6: {addr.address}")
                    elif addr.family == 17:  # MAC
                        lines.append(f"  MAC: {addr.address}")

        # Add connection count
        conns = psutil.net_connections()
        lines.append(f"\nActive connections: {len([c for c in conns if c.status == 'ESTABLISHED'])}")

        return "\n".join(lines)

    async def _run_shell(self, command: str) -> str:
        """Run shell command safely."""
        # Safety check
        dangerous = ['rm -rf', 'dd ', 'mkfs', 'fdisk', 'format', 'shutdown', 'reboot']
        for d in dangerous:
            if d in command.lower():
                return f"Blocked dangerous command: {d}"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            output = ""
            if stdout:
                output += stdout.decode()
            if stderr:
                output += f"\n[stderr]\n{stderr.decode()}"

            return output.strip() or "[No output]"
        except asyncio.TimeoutError:
            return "Command timed out (30s)"
        except Exception as e:
            return f"Error: {e}"

    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f}PB"