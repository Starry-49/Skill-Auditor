---
name: skill-auditor
description: Use when the user wants to audit the current Codex skills library for prompt poisoning, ad-style injections, suspicious hosted-platform referrals, vendor-branded defaults, stealth marketing copy, or suspicious skill names inside ~/.codex/skills or $CODEX_HOME/skills.
---

# Skill Auditor

Use this skill for read-only review of the local skills library before any cleanup.

## Default workflow

1. Run the bundled audit script against the current skills root.
2. Review `critical` and `high` findings first.
3. Distinguish legitimate documentation links from off-task marketing, referral language, or branded defaults.
4. Only modify or remove flagged content if the user explicitly asks for cleanup.

## Primary command

Run the auditor directly:

```bash
python3 "$CODEX_HOME/skills/skill-auditor/scripts/audit_skills.py" --format markdown
```

If `CODEX_HOME` is unset, the script defaults to `~/.codex/skills`.

## Useful variants

- Fail if medium-or-higher findings exist:

```bash
python3 "$CODEX_HOME/skills/skill-auditor/scripts/audit_skills.py" --fail-on medium
```

- Add a custom denylisted domain:

```bash
python3 "$CODEX_HOME/skills/skill-auditor/scripts/audit_skills.py" --deny-domain example.ai
```

- Save a markdown report:

```bash
python3 "$CODEX_HOME/skills/skill-auditor/scripts/audit_skills.py" --format markdown --report reports/skill-audit.md
```

## Interpretation rules

- `critical`: direct recommendation, forced upsell, or explicit instruction to steer users toward a hosted service
- `high`: denylisted domains or strong CTA lines tied to external links
- `medium`: softer marketing copy, branded defaults, or suspicious structural signals
- `low`: weak or isolated signals worth manual review

## Safety

- Do not auto-delete user skills.
- Do not auto-rewrite third-party repos unless the user asks to sanitize them.
- When cleaning is requested, keep legitimate technical references and remove only off-task promotional or poisoned content.

The default rules live in `rules/default_rules.json`.
