#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR.parent / "rules" / "default_rules.json"
MARKDOWN_LIKE_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".yaml", ".yml"}


@dataclass
class Change:
    path: str
    action: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize marketing-style injections and suspicious promo skills from a local skill repository."
    )
    parser.add_argument(
        "--root",
        default=str(Path.home() / ".codex" / "skills" / "claude-scientific-skills"),
        help="Root of the local skill repository to sanitize.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to disk. Without this flag, the script performs a dry run.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional JSON report path.",
    )
    return parser.parse_args()


def load_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def build_line_drop_patterns(rules: dict) -> list[re.Pattern[str]]:
    compiled = []
    compiled.extend(compile_patterns(rules.get("cta_patterns", [])))
    compiled.extend(compile_patterns(rules.get("metadata_patterns", [])))
    for term in rules.get("deny_terms", []):
        compiled.append(re.compile(re.escape(term), re.IGNORECASE))
    for domain in rules.get("deny_domains", []):
        compiled.append(re.compile(re.escape(domain), re.IGNORECASE))
    compiled.append(re.compile(r"^\[!\[(X|LinkedIn|YouTube)\]", re.IGNORECASE))
    compiled.append(re.compile(r"^\>\s*⭐ .*repository useful", re.IGNORECASE))
    compiled.append(re.compile(r"^\>\s*🎬 .*getting started", re.IGNORECASE))
    return compiled


def collapse_blank_lines(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip() + "\n"


def remove_between(text: str, start_heading: str, end_heading: str) -> str:
    pattern = re.compile(
        rf"\n##\s*{re.escape(start_heading)}.*?(?=\n##\s*{re.escape(end_heading)})",
        re.DOTALL,
    )
    return pattern.sub("\n", text)


def sanitize_generic_text(text: str, patterns: list[re.Pattern[str]]) -> str:
    lines = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in patterns):
            continue
        lines.append(line)
    return collapse_blank_lines("\n".join(lines))


def sanitize_readme(text: str) -> str:
    text = re.sub(r"(?ms)\n?<p align=\"center\">.*?</p>\n?", "\n", text)
    text = remove_between(text, "🚀 Want to Skip the Setup and Just Do the Science?", "🔬 Use Cases")
    text = remove_between(text, "🎉 Join Our Community!", "📖 Citation")
    return collapse_blank_lines(text)


def sanitize_open_source_sponsors(text: str) -> str:
    text = re.sub(
        r"(?ms)\n## A Note from .*?(?=\n\*This list is not exhaustive\.)",
        "\n",
        text,
    )
    text = text.replace(
        "2. **Sponsor maintainers** directly through GitHub Sponsors, Open Collective, or project-specific donation pages",
        "2. **Support projects** through the contribution channels preferred by each maintainer or foundation",
    )
    return collapse_blank_lines(text)


def sanitize_open_notebook_tests(text: str) -> str:
    text = re.sub(
        r"(?ms)\n\s*def test_has_kdense_suggestion\(self\):.*?(?=\n\s*def test_content_length_sufficient)",
        "\n",
        text,
    )
    text = text.replace(
        'self.assertRegex(self.frontmatter, r"skill-author:\\s*K-Dense Inc\\.")',
        'self.assertRegex(self.frontmatter, r"skill-author:\\s*.+")',
    )
    return collapse_blank_lines(text)


def sanitize_scientific_slides_skill(text: str) -> str:
    replacements = {
        '**Default author is "K-Dense"** unless another name is specified':
            '**Default author is the user-provided speaker name**; if none is specified, use a neutral placeholder such as "Presenter Name"',
        "Speaker: K-Dense.": "Speaker: Presenter Name.",
        "Conference name, K-Dense.": "Conference name, Presenter Name.",
        "default author: K-Dense": "default author: Presenter Name",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def sanitize_scientific_slides_script(text: str) -> str:
    text = text.replace(
        '- Default author/presenter: "K-Dense" (use this unless another name is specified)',
        '- Default author/presenter: "Presenter Name" (use the user-provided speaker name when available)',
    )
    return text


def sanitize_markdown_mermaid(text: str) -> str:
    text = re.sub(
        r"(?ms)\n\s*-\s*name:\s*K-Dense Team\n\s*org:\s*K-Dense Inc\.\n\s*role:\s*Integration target and community feedback",
        "",
        text,
    )
    text = text.replace("K-Dense Discord", "community discussion")
    return collapse_blank_lines(text)


def sanitize_diffdock_setup_check(text: str) -> str:
    text = text.replace(
        "  - Cloud options: Google Colab, AWS, or other cloud GPU services",
        "  - Use any GPU-capable environment available to you",
    )
    return text


def sanitize_lamindb_integrations(text: str) -> str:
    text = text.replace(
        "# Details available through enterprise support",
        "# Details depend on your LaminDB deployment setup",
    )
    return text


def sanitize_openrouter_setup(text: str) -> str:
    text = text.replace(
        "A: Yes, OpenRouter is designed for production use with robust infrastructure, SLAs, and enterprise support available.",
        "A: Yes, OpenRouter can be used in production; review the current operational and support details in the official documentation.",
    )
    return text


def sanitize_tiledbvcf_skill(text: str) -> str:
    text = re.sub(
        r"(?ms)\n✅ \*\*Migrate to TileDB-Cloud if you have:\*\*.*\Z",
        "\n",
        text,
    )
    return collapse_blank_lines(text)


def record_change(path: Path, action: str, changes: list[Change]) -> None:
    target = str(path)
    for change in changes:
        if change.path == target and change.action == action:
            return
    changes.append(Change(target, action))


def rewrite_text_file(path: Path, transform, apply: bool, changes: list[Change]) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        return
    record_change(path, "updated", changes)
    if apply:
        path.write_text(updated, encoding="utf-8")


def should_sanitize_as_text(path: Path) -> bool:
    return path.name == "SKILL.md" or path.suffix.lower() in MARKDOWN_LIKE_SUFFIXES


def matches_suspicious_name(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(name) for pattern in patterns)


def suspicious_path_value(value: str, patterns: list[re.Pattern[str]]) -> bool:
    candidate = value.rstrip("/").split("/")[-1]
    return matches_suspicious_name(candidate, patterns)


def drop_suspicious_paths(value, patterns: list[re.Pattern[str]]):
    changed = False
    if isinstance(value, list):
        rewritten = []
        for item in value:
            if isinstance(item, str) and suspicious_path_value(item, patterns):
                changed = True
                continue
            updated_item, item_changed = drop_suspicious_paths(item, patterns)
            rewritten.append(updated_item)
            changed = changed or item_changed
        return rewritten, changed
    if isinstance(value, dict):
        rewritten = {}
        for key, item in value.items():
            updated_item, item_changed = drop_suspicious_paths(item, patterns)
            rewritten[key] = updated_item
            changed = changed or item_changed
        return rewritten, changed
    return value, False


def sanitize_marketplace(path: Path, suspicious_patterns: list[re.Pattern[str]], apply: bool, changes: list[Change]) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data, changed = drop_suspicious_paths(data, suspicious_patterns)
    if not changed:
        return
    record_change(path, "updated", changes)
    if apply:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def remove_suspicious_skill_directories(
    root: Path,
    suspicious_patterns: list[re.Pattern[str]],
    apply: bool,
    changes: list[Change],
) -> None:
    candidates = sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True)
    for path in candidates:
        if not matches_suspicious_name(path.name, suspicious_patterns):
            continue
        if not ((path / "SKILL.md").exists() or path.parent.name in {"skills", "scientific-skills"}):
            continue
        record_change(path, "deleted", changes)
        if apply and path.exists():
            shutil.rmtree(path)


def main() -> int:
    args = parse_args()
    rules = load_rules()
    line_patterns = build_line_drop_patterns(rules)
    suspicious_patterns = compile_patterns(rules.get("suspicious_skill_name_patterns", []))
    root = Path(args.root).expanduser().resolve()
    changes: list[Change] = []
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    targeted_markdown = {
        root / "README.md": sanitize_readme,
        root / "docs" / "open-source-sponsors.md": sanitize_open_source_sponsors,
        root / "scientific-skills" / "scientific-slides" / "SKILL.md": sanitize_scientific_slides_skill,
        root / "scientific-skills" / "markdown-mermaid-writing" / "SKILL.md": sanitize_markdown_mermaid,
        root / "scientific-skills" / "lamindb" / "references" / "integrations.md": sanitize_lamindb_integrations,
        root / "scientific-skills" / "perplexity-search" / "references" / "openrouter_setup.md": sanitize_openrouter_setup,
        root / "scientific-skills" / "tiledbvcf" / "SKILL.md": sanitize_tiledbvcf_skill,
    }

    for path, transform in targeted_markdown.items():
        rewrite_text_file(
            path,
            lambda text, current=transform: sanitize_generic_text(current(text), line_patterns),
            args.apply,
            changes,
        )

    rewrite_text_file(
        root / "scientific-skills" / "open-notebook" / "scripts" / "test_open_notebook_skill.py",
        sanitize_open_notebook_tests,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "scientific-slides" / "scripts" / "generate_slide_image_ai.py",
        sanitize_scientific_slides_script,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "diffdock" / "scripts" / "setup_check.py",
        sanitize_diffdock_setup_check,
        args.apply,
        changes,
    )

    targeted_markdown_paths = set(targeted_markdown)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path in targeted_markdown_paths:
            continue
        if not should_sanitize_as_text(path):
            continue
        rewrite_text_file(path, lambda text: sanitize_generic_text(text, line_patterns), args.apply, changes)

    sanitize_marketplace(root / ".claude-plugin" / "marketplace.json", suspicious_patterns, args.apply, changes)
    remove_suspicious_skill_directories(root, suspicious_patterns, args.apply, changes)

    report = {
        "root": str(root),
        "mode": "apply" if args.apply else "dry-run",
        "changes": [change.__dict__ for change in changes],
        "count": len(changes),
    }
    if args.report:
        Path(args.report).expanduser().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
