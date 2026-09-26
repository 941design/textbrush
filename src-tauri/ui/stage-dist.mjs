// Stage only browser runtime assets; never embed dependencies or test fixtures.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync } from 'node:fs';

const source = new URL('./', import.meta.url);
const output = new URL('../ui-dist/', import.meta.url);
rmSync(output, { recursive: true, force: true });
mkdirSync(new URL('styles/', output), { recursive: true });
const assets = ['index.html', 'bundle.js', ...readdirSync(new URL('styles/', source))
  .filter(name => name.endsWith('.css')).map(name => `styles/${name}`)];
for (const name of assets) {
  writeFileSync(new URL(name, output), readFileSync(new URL(name, source)));
}
