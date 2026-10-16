// Copies the QR decoder's WebAssembly file into public/ so it is served from
// our own Hosting domain (the library would otherwise fetch it from a CDN on
// browsers without a native BarcodeDetector, e.g. iOS Safari).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "node_modules/zxing-wasm/dist/reader/zxing_reader.wasm");
const targetDir = join(root, "public/vendor");

mkdirSync(targetDir, { recursive: true });
copyFileSync(source, join(targetDir, "zxing_reader.wasm"));
console.log("copied zxing_reader.wasm -> public/vendor/");
