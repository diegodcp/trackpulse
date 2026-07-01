// @vitest-environment node
// Security regression test — ensures the frontend source tree does not embed
// OpenF1 credential env var names or hardcoded secret values.
// These patterns must never appear in browser-executed code.

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const SOURCE_EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx']);

/**
 * Recursively collect all source files under `dir`.
 * Skips node_modules and the test/ setup directory.
 */
function collectSourceFiles(dir) {
  const results = [];
  for (const entry of readdirSync(dir)) {
    // Skip the test setup dir and this file itself to avoid false positives on
    // the pattern strings defined below.
    if (entry === 'node_modules' || entry === 'security.test.js') continue;
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      results.push(...collectSourceFiles(full));
    } else if (SOURCE_EXTENSIONS.has(extname(entry))) {
      results.push(full);
    }
  }
  return results;
}

// Secret env var names that must never appear as literals in frontend source.
// The frontend must only communicate with the backend proxy — it must not read
// or reference OpenF1 authentication credentials directly.
const FORBIDDEN_LITERAL_NAMES = [
  'TRACKPULSE_OPENF1_BEARER_TOKEN',
  'TRACKPULSE_OPENF1_PASSWORD',
  'TRACKPULSE_OPENF1_USERNAME',
  'OPENF1_TOKEN',
  'OPENF1_SECRET',
  'OPENF1_API_KEY',
];

// Regex patterns that indicate a hardcoded credential value.
const FORBIDDEN_VALUE_PATTERNS = [
  // JWT Bearer token embedded as a string literal
  /Bearer\s+ey[A-Za-z0-9_-]{40,}/,
  // PEM private key block
  /-----BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+|DSA\s+)?PRIVATE KEY-----/,
];

describe('frontend source: no secret env names or hardcoded credentials', () => {
  const files = collectSourceFiles(__dirname);

  it('does not reference OpenF1 credential env var names', () => {
    const violations = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf-8');
      for (const name of FORBIDDEN_LITERAL_NAMES) {
        if (content.includes(name)) {
          violations.push(`${file} contains forbidden literal: ${name}`);
        }
      }
    }
    expect(violations, violations.join('\n')).toEqual([]);
  });

  it('does not contain hardcoded credential values', () => {
    const violations = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf-8');
      for (const pattern of FORBIDDEN_VALUE_PATTERNS) {
        if (pattern.test(content)) {
          violations.push(`${file} matches forbidden pattern: ${pattern}`);
        }
      }
    }
    expect(violations, violations.join('\n')).toEqual([]);
  });

  it('does not call api.openf1.org directly', () => {
    const violations = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf-8');
      if (/api\.openf1\.org/.test(content)) {
        violations.push(`${file} contains a direct api.openf1.org reference`);
      }
    }
    expect(violations, violations.join('\n')).toEqual([]);
  });
});
