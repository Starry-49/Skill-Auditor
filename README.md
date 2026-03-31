# Skill-Auditor

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![CI](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml/badge.svg)](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Install via npx](https://img.shields.io/badge/install-npx-black.svg)](https://github.com/Starry-49/Skill-Auditor#install)

`Skill-Auditor` helps you inspect and clean local AI agent skill libraries before they shape agent behavior. It is designed to catch prompt poisoning, ad-style call-to-actions, hosted-platform referrals, vendor-branded defaults, and suspicious skill folders such as `offer-*`, `promo-*`, or `upsell-*`.

The bundled Codex skill installs into `~/.codex/skills`, and the underlying audit and sanitize scripts can target any local skill or prompt library through `--root`.

## Install

```bash
npx github:Starry-49/Skill-Auditor install
```

This installs `skill-auditor` into `$CODEX_HOME/skills/skill-auditor` or `~/.codex/skills/skill-auditor`.

Restart Codex after installation.

## Audit a library

Run the auditor through `npx`:

```bash
npx github:Starry-49/Skill-Auditor audit --root ~/.codex/skills --format markdown --fail-on high
```

Or run the installed Python script directly:

```bash
python3 ~/.codex/skills/skill-auditor/scripts/audit_skills.py --root ~/.codex/skills --format markdown
```

## Sanitize a contaminated repo

Preview the cleanup first:

```bash
npx github:Starry-49/Skill-Auditor sanitize --root ~/.codex/skills/third-party-skills
```

Apply the cleanup:

```bash
npx github:Starry-49/Skill-Auditor sanitize --root ~/.codex/skills/third-party-skills --apply
```

The sanitizer is rule-driven and focuses on high-signal cleanup:

- removes strong referral and CTA copy from markdown-like files
- strips vendor-branded default metadata such as company-name authors
- removes suspicious promo skill entries from manifest-style path lists
- deletes obvious promo skill directories such as `offer-*`, `promo-*`, and `upsell-*`

## What it looks for

- explicit recommendations to visit a service, platform, web app, Slack, Discord, or sales channel
- lines such as `try it free`, `zero setup`, `contact sales`, `book a demo`, `professional services`, or `enterprise support`
- repeated suspicious domains across many files
- vendor-branded default metadata embedded into shared skills
- suspicious skill names and promo-only subskills

## Customize detection

The default rules live in `skill/skill-auditor/rules/default_rules.json`.

Common overrides:

```bash
python3 ~/.codex/skills/skill-auditor/scripts/audit_skills.py \
  --root ~/.codex/skills \
  --deny-domain example.ai \
  --deny-term "hosted dashboard" \
  --allow-domain docs.example.org
```

The repository ships with a small seed denylist for known referral patterns, but the rule engine is intended to be extended for the specific libraries and vendors you audit.

## Typical use cases

- review third-party skills before installation
- audit a shared agent prompt repository in CI
- clean a polluted skill pack after importing it locally
- maintain a private allowlist/denylist for your own agent environment

## Validate locally

```bash
python3 -m unittest discover -s tests -v
```

The GitHub Actions workflow also checks the Python tests, Node CLI syntax, install flow, and CLI smoke paths on every push.
