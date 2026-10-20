"""Integrity and discovery for optional, development-only GUI skills."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


def inside(here: Path, relative: str) -> Path:
    source = (here / relative).resolve()
    if not relative or Path(relative).is_absolute() or not source.is_relative_to(here.resolve()):
        raise ValueError('A GUI tool path must stay inside its checked-in directory')
    return source


def verify_extensions(here: Path) -> dict:
    manifest = json.loads((here / 'EXTENSIONS.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported GUI extension manifest')
    for source in manifest['sources']:
        target = inside(here, source['copied_to'])
        if hashlib.sha256(target.read_bytes()).hexdigest() != source['sha256']:
            raise RuntimeError('GUI upstream integrity check failed: ' + source['copied_to'])
    for entry in manifest['entries']:
        if not re.fullmatch(r'template-ai-[a-z-]+', entry['name']):
            raise ValueError('Invalid project GUI skill name')
        source = inside(here, entry['source'])
        skill = source / 'SKILL.md'
        if not skill.is_file() or ('name: ' + entry['name']) not in skill.read_text(encoding='utf-8'):
            raise ValueError('Missing or mismatched project skill: ' + entry['name'])
    for path in manifest['agent_roles'].values():
        if not inside(here, path).is_file():
            raise ValueError('Missing project GUI agent role')
    return manifest


def discover_skills(repository: Path, here: Path, manifest: dict) -> list[str]:
    """Use the standard project-local discovery directory without overwriting files."""
    entries = [{'name': 'template-ai-gui', 'source': '.'}, *manifest['entries']]
    discovered = []
    for entry in entries:
        source = inside(here, entry['source'])
        destination = repository / '.agents/skills' / entry['name']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            if destination.resolve() != source:
                raise RuntimeError('A different project skill exists: ' + entry['name'])
        elif destination.exists():
            raise RuntimeError('An existing skill was not overwritten: ' + entry['name'])
        else:
            destination.symlink_to(os.path.relpath(source, destination.parent), target_is_directory=True)
        discovered.append(str(destination.relative_to(repository)))
    return discovered
