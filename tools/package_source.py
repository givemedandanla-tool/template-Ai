"""產生原始碼包；只納入軟體、文件與合成驗證檔，不納入本機使用者資料。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from template_ai import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = args.output or root / "artifacts" / f"TemplateAI-v{__version__}-Source.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError("來源包已存在，請指定新檔名")
    names = ["README.md", ".gitignore", "app.py", "START_WINDOWS.bat", "requirements.txt",
             "requirements-lock.txt", "requirements-build.txt"]
    files = [(root / name, name) for name in names]
    for directory in (".github", "docs", "examples", "template_ai", "tests", "tools"):
        for source in sorted((root / directory).rglob("*")):
            if source.is_file() and not source.is_symlink() and "__pycache__" not in source.parts:
                files.append((source, source.relative_to(root).as_posix()))
    # 只含驗證工具生成的合成成品；SQLite、assets 及使用者原檔全部排除。
    evidence = ["TEST_RESULTS.txt", "VALIDATION.json", "output-workspace.png", "training-workspace.png",
                "template-workspace.png", "decorated-output-workspace.png", "multiple-artworks-workspace.png"]
    evidence += [f"{prefix}-FINAL.{suffix}" for prefix in ("synthetic", "decorated") for suffix in ("pdf", "png", "jpg")]
    files += [(root / "artifacts" / name, "validation/" + name) for name in evidence if (root / "artifacts" / name).is_file()]
    folder = f"TemplateAI-v{__version__}-Source"
    manifest = {name: {"bytes": source.stat().st_size, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                for source, name in files}
    created = False
    try:
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            created = True
            for source, name in files:
                archive.write(source, folder + "/" + name)
            archive.writestr(folder + "/SOURCE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(target) as archive:
            if archive.testzip():
                raise ValueError("來源 ZIP 完整性檢查失敗")
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".sha256").write_text(digest + "  " + target.name + "\n", encoding="utf-8")
    print(json.dumps({"path": str(target), "version": __version__, "files": len(files) + 1,
                      "bytes": target.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    main()
