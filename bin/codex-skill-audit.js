#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..');
const installScript = path.join(repoRoot, 'scripts', 'install_skill.py');
const bundledAuditScript = path.join(
  repoRoot,
  'skill',
  'skill-auditor',
  'scripts',
  'audit_skills.py'
);
const bundledSanitizeScript = path.join(
  repoRoot,
  'skill',
  'skill-auditor',
  'scripts',
  'sanitize_marketing_text.py'
);

function codexHome() {
  return process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
}

function installedAuditScript() {
  return path.join(codexHome(), 'skills', 'skill-auditor', 'scripts', 'audit_skills.py');
}

function installedSanitizeScript() {
  return path.join(codexHome(), 'skills', 'skill-auditor', 'scripts', 'sanitize_marketing_text.py');
}

function runPython(scriptPath, args) {
  const result = spawnSync('python3', [scriptPath, ...args], {
    stdio: 'inherit'
  });

  if (result.error) {
    if (result.error.code === 'ENOENT') {
      console.error('python3 is required but was not found in PATH.');
    } else {
      console.error(result.error.message);
    }
    process.exit(1);
  }

  process.exit(typeof result.status === 'number' ? result.status : 1);
}

function printHelp() {
  console.log(`Usage:
  skill-auditor install [--dest-root PATH] [--name NAME] [--force]
  skill-auditor audit [audit-script-args...]
  skill-auditor sanitize [sanitize-script-args...]
  skill-auditor where
  skill-auditor help

Examples:
  skill-auditor install
  skill-auditor audit --format markdown --fail-on high
  skill-auditor sanitize --root ~/.codex/skills/third-party-skills --apply
  skill-auditor where

Legacy alias:
  codex-skill-audit ...`);
}

const argv = process.argv.slice(2);
const command = argv[0] || 'install';

if (command === 'help' || command === '--help' || command === '-h') {
  printHelp();
  process.exit(0);
}

if (command === 'where') {
  console.log(`Repository root: ${repoRoot}`);
  console.log(`Bundled skill source: ${path.join(repoRoot, 'skill', 'skill-auditor')}`);
  console.log(`Default install target: ${path.join(codexHome(), 'skills', 'skill-auditor')}`);
  process.exit(0);
}

if (command === 'install') {
  runPython(installScript, argv.slice(1));
}

if (command === 'audit') {
  const scriptPath = fs.existsSync(installedAuditScript())
    ? installedAuditScript()
    : bundledAuditScript;
  runPython(scriptPath, argv.slice(1));
}

if (command === 'sanitize') {
  const scriptPath = fs.existsSync(installedSanitizeScript())
    ? installedSanitizeScript()
    : bundledSanitizeScript;
  runPython(scriptPath, argv.slice(1));
}

console.error(`Unknown command: ${command}`);
printHelp();
process.exit(1);
