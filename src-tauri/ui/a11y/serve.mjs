// Static server for the headless-browser accessibility harness.
//
// Serves src-tauri/ui on the A11Y_PORT (default 4173) and exposes an
// /a11y/ index that points its script tag at the esbuild bundle
// (a11y/bundle.a11y.js). Playwright reads the URL from playwright.config.ts.

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PORT = Number.parseInt(process.env.A11Y_PORT ?? '4173', 10);

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon',
};

async function resolveFile(urlPath) {
  const safe = normalize(urlPath).replace(/^(\.\.[\\/])+/, '');
  const candidates = [];
  if (safe === '/' || safe === '/a11y' || safe === '/a11y/') {
    candidates.push(join(ROOT, 'a11y/index.html'));
  } else if (safe.startsWith('/a11y/')) {
    candidates.push(join(ROOT, safe));
    candidates.push(join(ROOT, safe.replace(/^\/a11y\//, '/')));
  } else {
    candidates.push(join(ROOT, safe));
  }
  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) {
        return candidate;
      }
    } catch {
      // ignore: try next candidate
    }
  }
  return null;
}

const server = createServer(async (req, res) => {
  const urlPath = decodeURIComponent((req.url ?? '/').split('?')[0]);
  try {
    const filePath = await resolveFile(urlPath);
    if (!filePath) {
      res.statusCode = 404;
      res.setHeader('content-type', 'text/plain; charset=utf-8');
      res.end('not found');
      return;
    }
    const body = await readFile(filePath);
    const ext = extname(filePath).toLowerCase();
    res.setHeader('content-type', MIME_TYPES[ext] ?? 'application/octet-stream');
    res.setHeader('cache-control', 'no-store');
    res.end(body);
  } catch (error) {
    res.statusCode = 500;
    res.setHeader('content-type', 'text/plain; charset=utf-8');
    res.end(`server error: ${error instanceof Error ? error.message : String(error)}`);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  const address = server.address();
  if (address && typeof address === 'object') {
    process.stdout.write(`${address.address}:${address.port}\n`);
  } else {
    process.stdout.write(`127.0.0.1:${PORT}\n`);
  }
});
