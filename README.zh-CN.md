# Skill-Auditor

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![CI](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml/badge.svg)](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Install via npx](https://img.shields.io/badge/install-npx-black.svg)](https://github.com/Starry-49/Skill-Auditor#quick-install)

`Skill-Auditor` 提供一个 Codex skill 和一层轻量 CLI 安装器，用来审查本地 skill 库中是否存在 prompt poisoning、广告式 call-to-action、嵌入式托管平台导流，以及 `offer-*` 这类可疑 skill 命名。

这个仓库分成两层：

- `skill/skill-auditor`：实际的 Codex skill，内含规则和 Python 审查引擎
- `bin/codex-skill-audit.js`：CLI 入口，对外暴露为 `skill-auditor`，同时保留旧别名 `codex-skill-audit`

## 快速安装

直接执行：

```bash
npx github:Starry-49/Skill-Auditor install
```

这会把 `skill-auditor` 复制到 `$CODEX_HOME/skills/skill-auditor` 或 `~/.codex/skills/skill-auditor`。

安装后重启 Codex。

## 快速审查

可以直接通过 `npx` 运行内置审查器：

```bash
npx github:Starry-49/Skill-Auditor audit --format markdown --fail-on high
```

或者在安装之后执行：

```bash
python3 ~/.codex/skills/skill-auditor/scripts/audit_skills.py --format markdown
```

## 它会标记什么

- skill 内部的直接推荐或变相导流语句
- 像 “try it free”、“zero setup”、“contact sales”、“join our Slack” 这样的营销式 CTA
- 在多文件中反复出现的可疑域名
- denylist 中的域名或关键词
- `offer-*`、`promo-*`、`upsell-*` 这类可疑 skill 名称

默认规则内置了一小组针对已知托管平台导流模式的种子 denylist，其中包括 K-Dense 相关词条；审查器本身仍然是通用的，也支持额外传入 `--deny-domain`、`--deny-term` 和 `--allow-domain`。

## 本地验证

这个仓库把审查核心保持在 Python 里，因此即使本地没有 Node，也可以先验证主要逻辑：

```bash
python3 -m unittest discover -s tests -v
```

GitHub Actions 还会在每次 push 时跑一条完整的 CLI smoke path：

- Python 单元测试
- Node 语法检查
- `install` dry-run
- 安装后的 CLI 对 clean fixture 的成功路径
- 安装后的 CLI 对 poisoned fixture 的失败路径

`npx` 入口在目标机器上仍然需要 Node。Python 侧的验证可以在没有 Node 的环境中完成，而 GitHub Actions 会覆盖 Node CLI 路径。

推荐使用的新 CLI 名称是 `skill-auditor`。旧的 `codex-skill-audit` 仍然保留，用于兼容已存在的命令引用。

## 仓库结构

```text
.
├── bin/
├── scripts/
├── skill/skill-auditor/
└── tests/
```
