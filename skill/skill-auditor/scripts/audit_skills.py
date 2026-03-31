#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

TEXT_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".py",
    ".js",
    ".ts",
    ".sh",
}
IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}
URL_RE = re.compile(r"https?://[^\s<>()\\[\\]\"']+")
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    skill: str
    path: str
    line: int | None
    rule: str
    evidence: str
    note: str


def default_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills"


def default_rules_path() -> Path:
    return Path(__file__).resolve().parents[1] / "rules" / "default_rules.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a Codex skills library for suspicious referral, marketing, and prompt-poisoning patterns."
    )
    parser.add_argument("--root", default=str(default_root()), help="Root skills directory to scan.")
    parser.add_argument(
        "--rules",
        default=str(default_rules_path()),
        help="Path to the JSON rules file.",
    )
    parser.add_argument(
        "--deny-domain",
        action="append",
        default=[],
        help="Extra denylisted domain. Can be passed multiple times.",
    )
    parser.add_argument(
        "--deny-term",
        action="append",
        default=[],
        help="Extra denylisted term. Can be passed multiple times.",
    )
    parser.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Allowlisted domain that should not trigger repeated-domain or deny-domain findings.",
    )
    parser.add_argument(
        "--only-skill",
        action="append",
        default=[],
        help="Restrict output to one or more top-level skill directories.",
    )
    parser.add_argument(
        "--ignore-skill",
        action="append",
        default=[],
        help="Ignore one or more top-level skill directories.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional output file. Parent directories are created automatically.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "low", "medium", "high", "critical"),
        default="none",
        help="Return exit code 1 if findings at or above this severity exist.",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=1024,
        help="Skip files larger than this size in KB.",
    )
    return parser.parse_args()


def load_rules(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def top_level_skill(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return root.name if len(rel.parts) == 1 else rel.parts[0]


def should_skip(path: Path, root: Path, max_bytes: int) -> bool:
    rel = path.relative_to(root)
    if any(part in IGNORE_DIRS for part in rel.parts):
        return True
    if not path.is_file():
        return True
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return True
    try:
        return path.stat().st_size > max_bytes
    except OSError:
        return True


def iter_text_files(root: Path, max_bytes: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if should_skip(path, root, max_bytes):
            continue
        yield path


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def add_finding(
    findings: list[Finding],
    seen: set[tuple],
    *,
    severity: str,
    category: str,
    skill: str,
    path: str,
    line: int | None,
    rule: str,
    evidence: str,
    note: str,
) -> None:
    key = (severity, category, skill, path, line, rule, evidence)
    if key in seen:
        return
    seen.add(key)
    findings.append(
        Finding(
            severity=severity,
            category=category,
            skill=skill,
            path=path,
            line=line,
            rule=rule,
            evidence=evidence.strip(),
            note=note,
        )
    )


def detect_suspicious_skill_names(
    *,
    root: Path,
    rules: dict,
    findings: list[Finding],
    seen: set[tuple],
    only_skills: set[str],
    ignore_skills: set[str],
) -> None:
    patterns = compile_patterns(rules.get("suspicious_skill_name_patterns", []))
    for skill_md in root.rglob("SKILL.md"):
        if any(part in IGNORE_DIRS for part in skill_md.relative_to(root).parts):
            continue
        skill = top_level_skill(root, skill_md)
        if only_skills and skill not in only_skills:
            continue
        if skill in ignore_skills:
            continue
        folder_name = skill_md.parent.name
        for pattern in patterns:
            if pattern.search(folder_name):
                add_finding(
                    findings,
                    seen,
                    severity="high",
                    category="suspicious_skill_name",
                    skill=skill,
                    path=str(skill_md.relative_to(root)),
                    line=None,
                    rule=pattern.pattern,
                    evidence=folder_name,
                    note="Skill directory name matches an offer/promo/upsell pattern.",
                )


def scan_files(
    *,
    root: Path,
    rules: dict,
    only_skills: set[str],
    ignore_skills: set[str],
    max_bytes: int,
) -> tuple[list[Finding], dict]:
    deny_domains = {normalize_domain(item) for item in rules.get("deny_domains", [])}
    deny_domains.update(normalize_domain(item) for item in rules.get("extra_deny_domains", []))
    deny_terms = {item.lower() for item in rules.get("deny_terms", [])}
    allow_domains = {normalize_domain(item) for item in rules.get("allow_domains", [])}
    critical_patterns = compile_patterns(rules.get("critical_patterns", []))
    cta_patterns = compile_patterns(rules.get("cta_patterns", []))
    metadata_patterns = compile_patterns(rules.get("metadata_patterns", []))
    findings: list[Finding] = []
    seen: set[tuple] = set()
    scanned_files = 0
    scanned_skills: set[str] = set()
    domain_files: dict[str, set[str]] = defaultdict(set)
    domain_skills: dict[str, set[str]] = defaultdict(set)
    cta_domains: set[str] = set()

    detect_suspicious_skill_names(
        root=root,
        rules=rules,
        findings=findings,
        seen=seen,
        only_skills=only_skills,
        ignore_skills=ignore_skills,
    )

    for path in iter_text_files(root, max_bytes):
        rel_path = path.relative_to(root)
        skill = top_level_skill(root, path)
        if only_skills and skill not in only_skills:
            continue
        if skill in ignore_skills:
            continue
        if (
            skill == "skill-auditor"
            and len(rel_path.parts) >= 2
            and rel_path.parts[1] in {"rules", "scripts"}
        ):
            # Do not flag the auditor's own detection machinery as live marketing content.
            continue

        scanned_files += 1
        scanned_skills.add(skill)

        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line_no, line in enumerate(lines, start=1):
            lowered = line.lower()
            urls = URL_RE.findall(line)
            hosts: set[str] = set()
            for url in urls:
                host = normalize_domain(urlparse(url).netloc)
                if not host or host in allow_domains:
                    continue
                hosts.add(host)
                domain_files[host].add(str(rel_path))
                domain_skills[host].add(skill)

            matched_critical = next((p.pattern for p in critical_patterns if p.search(line)), None)
            matched_cta = next((p.pattern for p in cta_patterns if p.search(line)), None)
            matched_metadata = next((p.pattern for p in metadata_patterns if p.search(line)), None)
            denied_domain_hits = sorted(host for host in hosts if host in deny_domains)
            denied_terms_hits = sorted(term for term in deny_terms if term in lowered)

            if matched_critical:
                add_finding(
                    findings,
                    seen,
                    severity="critical",
                    category="directive",
                    skill=skill,
                    path=str(rel_path),
                    line=line_no,
                    rule=matched_critical,
                    evidence=line,
                    note="Direct recommendation or steering language was found.",
                )

            if denied_domain_hits:
                for host in denied_domain_hits:
                    add_finding(
                        findings,
                        seen,
                        severity="high",
                        category="deny_domain",
                        skill=skill,
                        path=str(rel_path),
                        line=line_no,
                        rule="deny_domain",
                        evidence=host,
                        note="Line references a denylisted domain.",
                    )

            if denied_terms_hits:
                for term in denied_terms_hits:
                    add_finding(
                        findings,
                        seen,
                        severity="high",
                        category="deny_term",
                        skill=skill,
                        path=str(rel_path),
                        line=line_no,
                        rule="deny_term",
                        evidence=term,
                        note="Line contains a denylisted term.",
                    )

            if matched_cta:
                if hosts:
                    cta_domains.update(hosts)
                add_finding(
                    findings,
                    seen,
                    severity="high" if hosts else "medium",
                    category="marketing_cta",
                    skill=skill,
                    path=str(rel_path),
                    line=line_no,
                    rule=matched_cta,
                    evidence=line,
                    note="Marketing CTA language appears in a file that should stay task-focused.",
                )

            if matched_metadata:
                add_finding(
                    findings,
                    seen,
                    severity="medium",
                    category="vendor_metadata",
                    skill=skill,
                    path=str(rel_path),
                    line=line_no,
                    rule=matched_metadata,
                    evidence=line,
                    note="Vendor-branded metadata or default content was found.",
                )

    repeat_threshold = int(rules.get("repeat_domain_threshold", 5))
    for host, file_set in sorted(domain_files.items()):
        if host in allow_domains:
            continue
        if len(file_set) < repeat_threshold:
            continue
        if host not in deny_domains and host not in cta_domains:
            continue
        add_finding(
            findings,
            seen,
            severity="high" if host in deny_domains else "medium",
            category="repeated_domain",
            skill="*",
            path="*",
            line=None,
            rule="repeat_domain_threshold",
            evidence=host,
            note=(
                f"Domain appears in {len(file_set)} files across "
                f"{len(domain_skills[host])} top-level skill directories."
            ),
        )

    summary = {
        "root": str(root),
        "skills_scanned": len(scanned_skills),
        "files_scanned": scanned_files,
        "severity_counts": dict(Counter(finding.severity for finding in findings)),
        "total_findings": len(findings),
    }
    return sort_findings(findings), summary


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (
            -SEVERITY_ORDER[item.severity],
            item.skill,
            item.path,
            item.line or 0,
            item.category,
        ),
    )


def render_text(summary: dict, findings: list[Finding]) -> str:
    lines = [
        f"Root: {summary['root']}",
        f"Scanned skills: {summary['skills_scanned']}",
        f"Scanned files: {summary['files_scanned']}",
        f"Findings: {summary['total_findings']}",
    ]
    if summary["severity_counts"]:
        severity_bits = ", ".join(
            f"{severity}={count}"
            for severity, count in sorted(
                summary["severity_counts"].items(),
                key=lambda item: -SEVERITY_ORDER[item[0]],
            )
        )
        lines.append(f"Severity counts: {severity_bits}")
    if not findings:
        lines.append("No suspicious findings detected.")
        return "\n".join(lines)

    lines.append("")
    for finding in findings:
        location = finding.path if finding.line is None else f"{finding.path}:{finding.line}"
        lines.append(f"[{finding.severity}] {finding.skill} | {location}")
        lines.append(f"  category: {finding.category}")
        lines.append(f"  rule: {finding.rule}")
        lines.append(f"  evidence: {finding.evidence}")
        lines.append(f"  note: {finding.note}")
    return "\n".join(lines)


def render_markdown(summary: dict, findings: list[Finding]) -> str:
    lines = [
        "# Skill Audit Report",
        "",
        f"- Root: `{summary['root']}`",
        f"- Scanned skills: `{summary['skills_scanned']}`",
        f"- Scanned files: `{summary['files_scanned']}`",
        f"- Findings: `{summary['total_findings']}`",
    ]
    if summary["severity_counts"]:
        severity_bits = ", ".join(
            f"`{severity}={count}`"
            for severity, count in sorted(
                summary["severity_counts"].items(),
                key=lambda item: -SEVERITY_ORDER[item[0]],
            )
        )
        lines.append(f"- Severity counts: {severity_bits}")
    lines.append("")
    if not findings:
        lines.append("No suspicious findings detected.")
        return "\n".join(lines)

    for finding in findings:
        location = finding.path if finding.line is None else f"{finding.path}:{finding.line}"
        lines.append(f"## {finding.severity.upper()} | {finding.skill} | `{location}`")
        lines.append("")
        lines.append(f"- Category: `{finding.category}`")
        lines.append(f"- Rule: `{finding.rule}`")
        lines.append(f"- Evidence: `{finding.evidence}`")
        lines.append(f"- Note: {finding.note}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_json(summary: dict, findings: list[Finding]) -> str:
    payload = {
        "summary": summary,
        "findings": [asdict(item) for item in findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")


def should_fail(findings: list[Finding], threshold: str) -> bool:
    if threshold == "none":
        return False
    cutoff = SEVERITY_ORDER[threshold]
    return any(SEVERITY_ORDER[item.severity] >= cutoff for item in findings)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    rules_path = Path(args.rules).expanduser().resolve()

    if not root.exists():
        print(f"Skills root does not exist: {root}", file=sys.stderr)
        return 2
    if not rules_path.exists():
        print(f"Rules file does not exist: {rules_path}", file=sys.stderr)
        return 2

    rules = load_rules(rules_path)
    if args.deny_domain:
        rules["deny_domains"] = list(rules.get("deny_domains", [])) + list(args.deny_domain)
    if args.deny_term:
        rules["deny_terms"] = list(rules.get("deny_terms", [])) + list(args.deny_term)
    if args.allow_domain:
        rules["allow_domains"] = list(rules.get("allow_domains", [])) + list(args.allow_domain)

    findings, summary = scan_files(
        root=root,
        rules=rules,
        only_skills=set(args.only_skill),
        ignore_skills=set(args.ignore_skill),
        max_bytes=args.max_file_size_kb * 1024,
    )

    if args.format == "json":
        output = render_json(summary, findings)
    elif args.format == "markdown":
        output = render_markdown(summary, findings)
    else:
        output = render_text(summary, findings)

    if args.report:
        write_report(Path(args.report).expanduser(), output)

    print(output)
    return 1 if should_fail(findings, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
