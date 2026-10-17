// Next.js 16 static export writes route-segment payloads as nested files
// (e.g. collector/__next.collector/__PAGE__.txt) but the client router requests
// dotted names (collector/__next.collector.__PAGE__.txt). Firebase Hosting
// can't rewrite one into the other, so every client navigation 404'd and fell
// back to a full page load. Copy each nested payload to its dotted name.
import { copyFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "out");
let copied = 0;

function filesUnder(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? filesUnder(full) : [full];
  });
}

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (!statSync(full).isDirectory()) continue;
    if (name.startsWith("__next.")) {
      for (const file of filesUnder(full)) {
        const dotted = join(dir, `${name}.${relative(full, file).split(sep).join(".")}`);
        if (!existsSync(dotted)) {
          copyFileSync(file, dotted);
          copied++;
        }
      }
    } else {
      walk(full);
    }
  }
}

if (!existsSync(out)) {
  console.error("flatten-rsc: no out/ directory (run next build first)");
  process.exit(1);
}
walk(out);
console.log(`flatten-rsc: copied ${copied} route payload files to dotted names`);
