#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


README_DROP_PATTERNS = [
    re.compile(r"^\[!\[(X|LinkedIn|YouTube)\]"),
    re.compile(r"K-Dense Web", re.IGNORECASE),
    re.compile(r"k-dense\.ai", re.IGNORECASE),
    re.compile(r"Join Our Community", re.IGNORECASE),
    re.compile(r"Join our Slack", re.IGNORECASE),
    re.compile(r"commercial support", re.IGNORECASE),
    re.compile(r"sponsor maintainers", re.IGNORECASE),
    re.compile(r"K-Dense community highlights", re.IGNORECASE),
    re.compile(r"Regular Updates.*K-Dense team", re.IGNORECASE),
    re.compile(r"Enterprise Ready", re.IGNORECASE),
    re.compile(r"^\>\s*⭐ .*repository useful", re.IGNORECASE),
    re.compile(r"^\>\s*🎬 .*getting started", re.IGNORECASE),
]

GENERIC_LINE_DROP_PATTERNS = [
    re.compile(r"^\s*skill-author:\s*K-Dense Inc\b.*$", re.IGNORECASE),
]


@dataclass
class Change:
    path: str
    action: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize K-Dense-style marketing text from a local claude-scientific-skills installation."
    )
    parser.add_argument(
        "--root",
        default=str(Path.home() / ".codex" / "skills" / "claude-scientific-skills"),
        help="Root of the local claude-scientific-skills installation.",
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


def collapse_blank_lines(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip() + "\n"


def remove_between(text: str, start_heading: str, end_heading: str) -> str:
    pattern = re.compile(
        rf"\n##\s*{re.escape(start_heading)}.*?(?=\n##\s*{re.escape(end_heading)})",
        re.DOTALL,
    )
    return pattern.sub("\n", text)


def sanitize_readme(text: str) -> str:
    text = text.replace("created by [K-Dense](https://k-dense.ai). ", "")
    text = re.sub(r"(?ms)\n?<p align=\"center\">.*?</p>\n?", "\n", text)
    text = remove_between(text, "🚀 Want to Skip the Setup and Just Do the Science?", "🔬 Use Cases")
    text = remove_between(text, "🎉 Join Our Community!", "📖 Citation")

    lines = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in README_DROP_PATTERNS):
            continue
        lines.append(line)
    return collapse_blank_lines("\n".join(lines))


def sanitize_open_source_sponsors(text: str) -> str:
    text = re.sub(
        r"(?ms)\n## A Note from K-Dense.*?(?=\n\*This list is not exhaustive\.)",
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


def apply_generic_line_filters(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in GENERIC_LINE_DROP_PATTERNS):
            continue
        lines.append(line)
    return collapse_blank_lines("\n".join(lines))


def rewrite_text_file(path: Path, transform, apply: bool, changes: list[Change]) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    updated = apply_generic_line_filters(updated)
    if updated == original:
        return
    changes.append(Change(str(path), "updated"))
    if apply:
        path.write_text(updated, encoding="utf-8")


def drop_offer_paths(value):
    changed = False
    if isinstance(value, list):
        rewritten = []
        for item in value:
            if item == "./scientific-skills/offer-k-dense-web":
                changed = True
                continue
            updated_item, item_changed = drop_offer_paths(item)
            rewritten.append(updated_item)
            changed = changed or item_changed
        return rewritten, changed
    if isinstance(value, dict):
        rewritten = {}
        for key, item in value.items():
            updated_item, item_changed = drop_offer_paths(item)
            rewritten[key] = updated_item
            changed = changed or item_changed
        return rewritten, changed
    return value, False


def sanitize_marketplace(path: Path, apply: bool, changes: list[Change]) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data, changed = drop_offer_paths(data)
    if not changed:
        return
    changes.append(Change(str(path), "updated"))
    if apply:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def remove_offer_directory(path: Path, apply: bool, changes: list[Change]) -> None:
    if not path.exists():
        return
    changes.append(Change(str(path), "deleted"))
    if apply:
        shutil.rmtree(path)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    changes: list[Change] = []
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    rewrite_text_file(root / "README.md", sanitize_readme, args.apply, changes)
    rewrite_text_file(root / "docs" / "open-source-sponsors.md", sanitize_open_source_sponsors, args.apply, changes)
    rewrite_text_file(
        root / "scientific-skills" / "open-notebook" / "scripts" / "test_open_notebook_skill.py",
        sanitize_open_notebook_tests,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "scientific-slides" / "SKILL.md",
        sanitize_scientific_slides_skill,
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
        root / "scientific-skills" / "markdown-mermaid-writing" / "SKILL.md",
        sanitize_markdown_mermaid,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "diffdock" / "scripts" / "setup_check.py",
        sanitize_diffdock_setup_check,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "lamindb" / "references" / "integrations.md",
        sanitize_lamindb_integrations,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "perplexity-search" / "references" / "openrouter_setup.md",
        sanitize_openrouter_setup,
        args.apply,
        changes,
    )
    rewrite_text_file(
        root / "scientific-skills" / "tiledbvcf" / "SKILL.md",
        sanitize_tiledbvcf_skill,
        args.apply,
        changes,
    )

    for skill_md in root.rglob("SKILL.md"):
        rewrite_text_file(skill_md, lambda text: text, args.apply, changes)

    sanitize_marketplace(root / ".claude-plugin" / "marketplace.json", args.apply, changes)
    remove_offer_directory(root / "scientific-skills" / "offer-k-dense-web", args.apply, changes)

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
