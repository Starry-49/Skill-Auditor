# Skill-Auditor

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![CI](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml/badge.svg)](https://github.com/Starry-49/Skill-Auditor/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Install via npx](https://img.shields.io/badge/install-npx-black.svg)](https://github.com/Starry-49/Skill-Auditor#install)

`Skill-Auditor` 用来审查和清理本地 AI agent skill 库，避免第三方 skill 中的 prompt poisoning、广告式 CTA、托管平台导流、品牌默认值注入，以及 `offer-*`、`promo-*`、`upsell-*` 这类可疑目录影响 agent 行为。

随仓库提供的 Codex skill 会安装到 `~/.codex/skills`，而底层的审查脚本和清理脚本可以通过 `--root` 指向任意本地 skill / prompt 仓库，不只限于 Codex。

## 安装

```bash
npx github:Starry-49/Skill-Auditor install
```

这会把 `skill-auditor` 安装到 `$CODEX_HOME/skills/skill-auditor` 或 `~/.codex/skills/skill-auditor`。

安装后重启 Codex。

## 审查技能库

通过 `npx` 直接运行：

```bash
npx github:Starry-49/Skill-Auditor audit --root ~/.codex/skills --format markdown --fail-on high
```

或者直接执行安装后的 Python 脚本：

```bash
python3 ~/.codex/skills/skill-auditor/scripts/audit_skills.py --root ~/.codex/skills --format markdown
```

## 清理已污染的仓库

先 dry-run 预览：

```bash
npx github:Starry-49/Skill-Auditor sanitize --root ~/.codex/skills/third-party-skills
```

确认后落盘：

```bash
npx github:Starry-49/Skill-Auditor sanitize --root ~/.codex/skills/third-party-skills --apply
```

清理逻辑是规则驱动的，重点处理高信号污染：

- 从 markdown 类文件中移除明显的导流和营销文案
- 去掉共享 skill 中被硬编码的品牌默认元数据
- 从 manifest / marketplace 路径列表中移除可疑 promo skill
- 删除 `offer-*`、`promo-*`、`upsell-*` 这类明显只为导流存在的目录

## 它会识别什么

- 明示用户去访问某个 service、platform、web app、Slack、Discord 或销售渠道的语句
- `try it free`、`zero setup`、`contact sales`、`book a demo`、`professional services`、`enterprise support` 这类营销文案
- 多文件中重复出现的可疑域名
- 注入到共享 skill 里的品牌默认 metadata
- 可疑 skill 名称和 promo-only 子技能

## 如何自定义

默认规则位于 `skill/skill-auditor/rules/default_rules.json`。

常见覆盖方式：

```bash
python3 ~/.codex/skills/skill-auditor/scripts/audit_skills.py \
  --root ~/.codex/skills \
  --deny-domain example.ai \
  --deny-term "hosted dashboard" \
  --allow-domain docs.example.org
```

仓库默认只带一小组种子规则，用来命中已知的导流模式；规则引擎本身是通用的，建议按你自己的 skill 生态和供应商情况继续扩展。

## 典型使用场景

- 安装第三方 skill 前先做安全审查
- 在 CI 中审查共享 agent prompt / skill 仓库
- 本地导入一个 skill 包之后做一轮文本级净化
- 为自己的 agent 环境维护 allowlist / denylist

## 本地验证

```bash
python3 -m unittest discover -s tests -v
```

GitHub Actions 还会在每次 push 时检查 Python 测试、Node CLI 语法、安装流程，以及 CLI smoke path。
