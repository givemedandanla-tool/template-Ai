"""Explicit setup only: hash-pinned isolated tools and project skill entries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def home() -> Path:
    return Path(os.environ.get("TEMPLATE_AI_QUALITY_HOME", ROOT / ".cache/debug-tooling"))


def executable(base: Path, name: str) -> Path:
    return base / ("Scripts" if os.name == "nt" else "bin") / (name + (".exe" if os.name == "nt" else ""))


def load_lock() -> dict:
    return json.loads((HERE / "TOOLCHAIN.json").read_text(encoding="utf-8"))


def verify_sources() -> int:
    lock = load_lock()
    for name, info in lock["skills"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != info["sha256"]:
            raise RuntimeError("Pinned skill integrity mismatch: " + name)
    return len(lock["skills"])


def versions(base: Path) -> dict:
    ruff = executable(base / "python", "ruff")
    node = shutil.which("node")
    if not node or not ruff.is_file():
        raise RuntimeError("Run the explicit bootstrap first; ordinary checks never install tools")
    commands = {
        "ruff": [str(ruff), "--version"],
        "pyright": [node, str(base / "node/node_modules/pyright/index.js"), "--version"],
        "jscpd": [node, str(base / "node/node_modules/jscpd/run-jscpd.js"), "--version"],
    }
    found = {}
    for name, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
        version = load_lock()["tools"][name]
        if version not in result.stdout.split():
            raise RuntimeError("Unexpected " + name + " version")
        found[name] = version
    return found


def discover_skills() -> list[dict]:
    directory = ROOT / ".agents/skills"
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for name in ("diagnosing-bugs", "dry-refactoring"):
        source = HERE / "skills" / name
        destination = directory / ("template-ai-" + name)
        if destination.is_symlink():
            if destination.resolve() != source.resolve():
                raise RuntimeError("Refusing to replace another skill: " + name)
        elif destination.exists():
            if not destination.is_dir() or (destination / "SKILL.md").read_bytes() != (source / "SKILL.md").read_bytes():
                raise RuntimeError("Existing skill differs; preserve user changes: " + name)
        else:
            try:
                destination.symlink_to(source, target_is_directory=True)
            except OSError:
                shutil.copytree(source, destination)
        result.append({"name": "template-ai-" + name, "entry": str(destination.relative_to(ROOT) / "SKILL.md"), "files": "VERIFIED", "platform_auto_discovery": "UNVERIFIED_RELOAD_MAY_BE_REQUIRED"})
    return result


def setup(base: Path, offline: bool = False) -> dict:
    verify_sources()
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise RuntimeError("Node >=18 and npm are setup prerequisites; no automatic system installation")
    major = int(subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip().lstrip("v").split(".")[0])
    if major < load_lock()["node_minimum_major"]:
        raise RuntimeError("Node >=18 required")
    python = executable(base / "python", "python")
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(base / "python")
    ruff = executable(base / "python", "ruff")
    ready = ruff.is_file() and subprocess.run([str(ruff), "--version"], capture_output=True, text=True, check=True).stdout.strip() == "ruff " + load_lock()["tools"]["ruff"]
    wheels = base / "wheels"
    wheels.mkdir(exist_ok=True)
    if not list(wheels.glob("ruff-" + load_lock()["tools"]["ruff"] + "-*.whl")):
        if offline:
            raise RuntimeError("Offline setup needs the matching hash-pinned wheelhouse copied into the tool home")
        subprocess.run([str(python), "-m", "pip", "download", "--disable-pip-version-check", "--require-hashes", "--no-deps", "--only-binary=:all:", "--cache-dir", str(base / "pip-cache"), "--dest", str(wheels), "-r", str(HERE / "requirements-tools.txt")], check=True, timeout=180)
    if not ready:
        command = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--no-deps", "--only-binary=:all:", "--no-index", "--find-links", str(wheels), "-r", str(HERE / "requirements-tools.txt")]
        subprocess.run(command, check=True, timeout=180)
    target = base / "node"
    target.mkdir(parents=True, exist_ok=True)
    refresh = not all((target / name).is_file() for name in ("node_modules/pyright/index.js", "node_modules/jscpd/run-jscpd.js"))
    for name in ("package.json", "package-lock.json"):
        original = (HERE / "node" / name).read_bytes()
        if not (target / name).is_file() or (target / name).read_bytes() != original:
            refresh = True
            (target / name).write_bytes(original)
    if refresh:
        command = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--update-notifier=false", "--cache", str(base / "npm-cache")]
        if offline:
            command.append("--offline")
        subprocess.run(command, cwd=target, check=True, timeout=180)
    result = {"versions": versions(base), "upstream_files_verified": verify_sources(), "skills": discover_skills(), "network": "EXPLICIT_SETUP_ONLY", "product_dependencies_changed": False}
    (base / "bootstrap-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--check", action="store_true", help="No installation or downloads")
    args = parser.parse_args()
    result = {"versions": versions(home()), "upstream_files_verified": verify_sources()} if args.check else setup(home(), args.offline)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
