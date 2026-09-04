#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.resolve(__dirname, '..', 'web', 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];

if (scripts.length !== 1) {
  throw new Error(`Expected one inline script in ${htmlPath}; found ${scripts.length}`);
}

new Function(scripts[0][1]);
console.log(`Inline JavaScript syntax is valid: ${htmlPath}`);
