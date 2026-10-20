"""Local-only scans, immutable baselines and a labelled end-to-end demonstration."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from bootstrap import HERE, ROOT, executable, home, verify_sources, versions

SCHEMA = 1
EXCLUDED = {"__pycache__", ".venv", ".private", "node_modules", "vendor", "build", "dist", ".git", ".cache", "local-data"}
CONFIGS = ("ruff.toml.txt", "pyrightconfig.json", "jscpd.json", "TOOLCHAIN.json", "requirements-tools.txt", "node/package.json", "node/package-lock.json")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value: dict, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def inventory(root: Path, scope: str) -> list[Path]:
    roots = {"application": [root / "template_ai"], "tools": [root / "tools", root / "docs/dev/debug_tooling"], "tests": [root / "tests"]}[scope]
    if not roots[0].is_dir():
        raise ValueError("Expected scope directory missing: " + scope)
    result = []
    for base in roots:
        for path in base.rglob("*.py"):
            relative = path.relative_to(root)
            if not path.is_symlink() and not (set(relative.parts) & EXCLUDED):
                result.append(path)
    if scope == "application" and (root / "app.py").is_file():
        result.append(root / "app.py")
    if scope == "tools":
        result = [p for p in result if "debug_tooling/tests" not in p.as_posix()]
    if scope == "tests" and root == ROOT:
        result.extend((HERE / "tests").glob("test_*.py"))
    result = sorted(set(result))
    if not result:
        raise ValueError("Empty scope is not a pass: " + scope)
    for path in result:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Source escapes repository")
    return result


def manifest(files: list[Path], root: Path) -> dict:
    return {p.relative_to(root).as_posix(): {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size} for p in files}


def profile(scope: str) -> dict:
    items = {name: sha((HERE / name).read_bytes()) for name in CONFIGS}
    # Fingerprinting/coverage code is part of the comparison contract as well.
    items["quality.py"] = sha(Path(__file__).read_bytes())
    items["bootstrap.py"] = sha((HERE / "bootstrap.py").read_bytes())
    return {"schema": SCHEMA, "scope": scope, "files": items, "sha256": sha(json.dumps(items, sort_keys=True).encode())}


def locate(name: str, files: list[Path], root: Path) -> str:
    candidate = Path(name)
    if candidate.is_absolute():
        relative = candidate.relative_to(root).as_posix()
        if root / relative not in files:
            raise ValueError("Tool reported an unlisted source")
        return relative
    name = name.replace("\\", "/").removeprefix("./")
    candidates = [p.relative_to(root).as_posix() for p in files if p.relative_to(root).as_posix() == name or p.relative_to(root).as_posix().endswith("/" + name)]
    if len(candidates) != 1:
        raise ValueError("Ambiguous or unlisted tool path: " + name)
    return candidates[0]


def diagnostic(tool: str, rule: str, path: str, line: int, message: str, root: Path) -> dict:
    lines = (root / path).read_text(encoding="utf-8-sig").splitlines()
    context = lines[line - 1].strip() if 0 < line <= len(lines) else ""
    key = [tool, rule, path, message, context]
    return {"tool": tool, "rule": rule, "path": path, "line": line, "message": message, "context": context, "fingerprint": sha(json.dumps(key, ensure_ascii=False).encode())}


def compare(report: dict, baseline: dict) -> dict:
    if report["profile"] != baseline["profile"] or report["versions"] != baseline["versions"]:
        raise ValueError("Baseline profile/version mismatch; do not silently refresh")
    old = Counter(x["fingerprint"] for x in baseline["findings"])
    current = Counter(x["fingerprint"] for x in report["findings"])
    new, existing = [], []
    remaining = old.copy()
    for finding in report["findings"]:
        if remaining[finding["fingerprint"]]:
            remaining[finding["fingerprint"]] -= 1
            existing.append(finding)
        else:
            new.append(finding)
    return {"status": "NEW_FINDINGS" if new else "NO_NEW_FINDINGS", "new_count": len(new), "existing_count": len(existing), "resolved_count": sum((old - current).values()), "new": new, "baseline_source": baseline["source"], "note": "Existing findings remain a backlog; this is not a clean-product certificate."}


def scan(root: Path, scope: str, output: Path, application_python: Path | None = None) -> dict:
    root = root.resolve()
    if output.exists():
        raise FileExistsError("Unique report directory required; never overwrite evidence")
    verify_sources()
    installed = versions(home())
    files = inventory(root, scope)
    before = manifest(files, root)
    effective_profile = profile(scope)
    interpreter = application_python or executable(ROOT / ".venv", "python")
    if not interpreter.is_file():
        raise ValueError("Application Python missing; prepare existing application dependencies first")
    output.mkdir(parents=True)
    commands = []
    started = time.monotonic()

    def run(tool: str, args: list[str], accepted: tuple[int, ...] = (0, 1)) -> str:
        tick = time.monotonic()
        result = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        (output / (tool + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
        (output / (tool + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
        replacements = ((str(interpreter), "$APP_PYTHON"), (str(home().resolve()), "$TOOLS"), (str(output), "$REPORT"), (str(ROOT), "$REPO"), (str(root), "$SCAN_ROOT"))
        safe_args = []
        for arg in args:
            for old, new in replacements:
                arg = arg.replace(old, new)
            safe_args.append(arg)
        commands.append({"tool": tool, "argv": safe_args, "exit_code": result.returncode, "seconds": round(time.monotonic() - tick, 3), "stdout_sha256": sha(result.stdout.encode()), "stderr_sha256": sha(result.stderr.encode())})
        dump(output / "commands.json", {"commands": commands})
        if result.returncode not in accepted:
            raise RuntimeError("Tool execution/configuration failed: " + tool + " (see local log)")
        return result.stdout

    ruff_config = output / "ruff.toml"
    ruff_config.write_bytes((HERE / "ruff.toml.txt").read_bytes())
    ruff = str(executable(home() / "python", "ruff"))
    arguments = [str(p) for p in files]
    listed = run("ruff-files", [ruff, "check", "--config", str(ruff_config), "--show-files", *arguments], (0,))
    if {Path(x.strip()).resolve() for x in listed.splitlines() if x.strip()} != set(files):
        raise ValueError("Ruff did not cover the exact inventory")
    ruff_items = json.loads(run("ruff", [ruff, "check", "--config", str(ruff_config), "--output-format", "json", *arguments]))
    findings = [diagnostic("ruff", x["code"], locate(x["filename"], files, root), x["location"]["row"], x["message"], root) for x in ruff_items]

    config = json.loads((HERE / "pyrightconfig.json").read_text())
    config.update(include=[os.path.relpath(p, output) for p in files], executionEnvironments=[{"root": str(root), "extraPaths": [str(root)]}])
    dump(output / "pyrightconfig.json", config)
    node = shutil.which("node")
    pyright = json.loads(run("pyright", [node, str(home() / "node/node_modules/pyright/index.js"), "--project", str(output / "pyrightconfig.json"), "--pythonpath", str(interpreter), "--outputjson"]))
    pyright_count = pyright["summary"]["filesAnalyzed"]
    if pyright_count < len(files):
        raise ValueError("Pyright analyzed fewer sources than requested")
    for item in pyright["generalDiagnostics"]:
        findings.append(diagnostic("pyright", item.get("rule", "syntax"), locate(item["file"], files, root), item["range"]["start"]["line"] + 1, item["message"], root))

    clone_dir = output / "clones"
    run("jscpd", [node, str(home() / "node/node_modules/jscpd/run-jscpd.js"), "--config", str(HERE / "jscpd.json"), "--no-gitignore", "--output", str(clone_dir), "--silent", *arguments], (0,))
    clones = json.loads((clone_dir / "jscpd-report.json").read_text())
    clone_count = clones["statistics"]["total"]["sources"]
    minimum_lines = json.loads((HERE / "jscpd.json").read_text())["minLines"]
    short_sources = [p.relative_to(root).as_posix() for p in files if len(p.read_text(encoding="utf-8-sig").splitlines()) < minimum_lines]
    # jscpd 5.4.1 excludes short/token-insufficient files from `sources`.
    # All inventory paths are explicit CLI inputs; do not mislabel that statistic
    # as all supplied files, or lower thresholds just to inflate coverage.
    if not 0 < clone_count <= len(files) - len(short_sources):
        raise ValueError("jscpd has no eligible sources or inconsistent coverage")
    for item in clones["duplicates"]:
        first, second = item["firstFile"], item["secondFile"]
        paths = [locate(x["name"], files, root) for x in (first, second)]
        fragment_hash = sha(" ".join(re.findall(r"\w+|[^\s\w]", item["fragment"])).encode())
        kind = item.get("kind", "exact")
        key = ["jscpd", kind, sorted(paths), fragment_hash]
        findings.append({"tool": "jscpd", "rule": kind, "paths": paths, "ranges": [[x["start"], x["end"]] for x in (first, second)], "lines": item["lines"], "fragment_sha256": fragment_hash, "fingerprint": sha(json.dumps(key).encode()), "review": "UNREVIEWED_CANDIDATE_NOT_CONFIRMED_DEFECT"})

    if manifest(inventory(root, scope), root) != before or profile(scope) != effective_profile:
        raise ValueError("Source/configuration changed while scanning; result not accepted")
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    report = {"schema": SCHEMA, "status": "SCAN_COMPLETE_WITH_FINDINGS" if findings else "SCAN_COMPLETE_CLEAN", "scope": scope, "profile": effective_profile, "versions": installed,
              "source": {"head": git.stdout.strip() if git.returncode == 0 else "ISOLATED_DEMONSTRATION", "manifest_sha256": sha(json.dumps(before, sort_keys=True).encode()), "files": before},
              "coverage": {"expected": len(files), "ruff": len(files), "pyright_files_analyzed": pyright_count, "pyright_include": len(arguments), "jscpd_explicit_inputs": len(files), "jscpd_eligible_sources": clone_count, "jscpd_below_min_lines": short_sources, "jscpd_additional_below_min_tokens": len(files) - len(short_sources) - clone_count},
              "effective_configuration": {"ruff_sha256": sha(ruff_config.read_bytes()), "pyright_sha256": sha((output / "pyrightconfig.json").read_bytes()), "jscpd_sha256": sha((HERE / "jscpd.json").read_bytes()), "application_python_version": subprocess.run([str(interpreter), "--version"], capture_output=True, text=True, check=True).stdout.strip()},
              "commands": commands, "seconds": round(time.monotonic() - started, 3), "findings": findings, "counts": dict(Counter(x["tool"] for x in findings)),
              "exclusion_policy": {"directory_names": sorted(EXCLUDED), "reason": "Third-party/generated/build/private/cache data are not product source; tools and tests are separate scopes."},
              "qualification": "LOCAL_STATIC_ANALYSIS_ONLY_NOT_PRODUCT_OR_WINDOWS_ACCEPTANCE"}
    dump(output / "report.json", report)
    return report


DEMO_CODE = '''def accumulate(values: list[float]) -> tuple[float, int, float, float, float]:
    total = 0.0
    accepted: list[float] = []
    for value in values:
        if value > 0:
            total += value
            accepted.append(value)
        else:
            total -= value
    count = len(accepted)
    average = total / max(count, 1)
    maximum = max(accepted, default=0.0)
    minimum = min(accepted, default=0.0)
    return total, count, average, maximum, minimum
'''


def selftest(output: Path) -> dict:
    if output.exists():
        raise FileExistsError("Unique demo output required")
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="template-ai-quality-demo-") as temporary:
        root = Path(temporary)
        directory = root / "template_ai"
        directory.mkdir()
        (directory / "__init__.py").write_text("")
        unchanged = directory / "existing.py"
        unchanged.write_text(DEMO_CODE)
        (directory / "known_problem.py").write_text("def known() -> float:\n    return missing_old_rate\n")
        old_hash = sha(unchanged.read_bytes())
        baseline = scan(root, "application", output / "before")
        copied = directory / "new_copy.py"
        copied.write_text(DEMO_CODE + '\ndef wrong() -> int:\n    return "wrong type"\n\ndef missing() -> float:\n    return missing_new_rate\n')
        broken = scan(root, "application", output / "broken")
        comparison = compare(broken, baseline)
        assert broken["counts"].get("ruff", 0) > baseline["counts"].get("ruff", 0)
        assert any(x["rule"] == "reportReturnType" for x in broken["findings"] if x["tool"] == "pyright")
        assert any(x["tool"] == "jscpd" and set(x["paths"]) == {"template_ai/existing.py", "template_ai/new_copy.py"} for x in comparison["new"])
        assert comparison["existing_count"] > 0 and comparison["new_count"] > 0
        assert sha(unchanged.read_bytes()) == old_hash
        copied.write_text("def wrong() -> int:\n    return 1\n\ndef missing() -> float:\n    return 1.0\n")
        repaired = scan(root, "application", output / "repaired")
        clean_comparison = compare(repaired, baseline)
        assert clean_comparison["new_count"] == 0
        assert repaired["counts"].get("ruff") == baseline["counts"].get("ruff")
        result = {"status": "PASS", "label": "ISOLATED_DEMONSTRATION_NOT_REAL_PRODUCT_FIX", "checks": {"ruff_undefined_name": True, "pyright_incompatible_return": True, "exact_clone_detected": True, "new_to_unchanged_comparison": True, "existing_source_unchanged": True, "baseline_keeps_existing_problem": True, "new_findings_not_swallowed": True, "repair_removes_only_demo_new_findings": True}, "before": baseline["counts"], "broken": broken["counts"], "repaired": repaired["counts"], "versions": repaired["versions"], "profile": repaired["profile"]}
    dump(output / "selftest.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scan", "check", "baseline", "selftest"))
    parser.add_argument("--scope", choices=("application", "tools", "tests"), default="application")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--reason", help="Required explanation for initial baseline creation")
    parser.add_argument("--python", type=Path, help="Existing application interpreter; no automatic installation")
    args = parser.parse_args()
    if args.action == "baseline":
        if not args.report or not args.output or not args.reason:
            parser.error("baseline requires --report, --output and --reason; cannot overwrite")
        report = json.loads(args.report.read_text())
        report["baseline_reason"] = args.reason
        dump(args.output, report, exclusive=True)
        print(json.dumps({"status": "BASELINE_CREATED_WITH_EXISTING_FINDINGS", "counts": report["counts"]}))
        return 0
    output = (args.output or home() / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + args.action + "-" + args.scope)).resolve()
    if args.action == "selftest":
        result = selftest(output)
        print(json.dumps({"status": result["status"], "checks": len(result["checks"]), "label": result["label"]}))
        return 0
    report = scan(args.root, args.scope, output, args.python)
    result = {"status": report["status"], "scope": args.scope, "counts": report["counts"], "coverage": report["coverage"]}
    if args.action == "check":
        baseline_path = args.baseline or HERE / "baselines" / (args.scope + ".json")
        comparison = compare(report, json.loads(baseline_path.read_text()))
        dump(output / "comparison.json", comparison)
        result.update({k: comparison[k] for k in ("status", "new_count", "existing_count", "resolved_count")})
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "NEW_FINDINGS" else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "TOOLING_ERROR_NOT_PASS", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
