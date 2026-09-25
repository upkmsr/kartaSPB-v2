import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import vm from "node:vm";

const assetsDirectory = join(process.cwd(), "dist", "assets");
const assetNames = await readdir(assetsDirectory);
const workerAssets = assetNames.filter((name) => /^maplibre-gl-worker-[\w-]+\.js$/.test(name));

if (workerAssets.length !== 1) {
  throw new Error(`Expected exactly one emitted MapLibre worker asset, found ${workerAssets.length}`);
}

const workerName = workerAssets[0];
const workerSource = await readFile(join(assetsDirectory, workerName), "utf8");
const normalizedStart = workerSource.trimStart().slice(0, 100).toLowerCase();

if (workerSource.length < 10_000) {
  throw new Error(`MapLibre worker asset is unexpectedly small: ${workerSource.length} bytes`);
}
if (normalizedStart.includes("<!doctype html") || normalizedStart.includes("<html")) {
  throw new Error("MapLibre worker asset contains HTML instead of JavaScript");
}
new vm.Script(workerSource, { filename: workerName });

const applicationAssets = assetNames.filter(
  (name) => name.endsWith(".js") && name !== workerName,
);
const applicationSources = await Promise.all(
  applicationAssets.map((name) => readFile(join(assetsDirectory, name), "utf8")),
);
if (!applicationSources.some((source) => source.includes(workerName))) {
  throw new Error("Production application bundle does not reference the emitted MapLibre worker");
}

process.stdout.write(`Verified production MapLibre worker: dist/assets/${workerName}\n`);
