import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const project = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const templates = resolve(project, "../../templates/progress-dashboard");
const vite = resolve(project, "node_modules/vite/bin/vite.js");
const temp = await mkdtemp(join(tmpdir(), "gauntlet-progress-assets-"));
const first = join(temp, "first");
const second = join(temp, "second");

function build(outDir) {
  const result = spawnSync(process.execPath, [vite, "build", "--outDir", outDir, "--emptyOutDir"], {
    cwd: project,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    process.stderr.write(result.stdout);
    process.stderr.write(result.stderr);
    process.exit(result.status ?? 1);
  }
}

async function files(root, directory = root) {
  const entries = await readdir(directory, { withFileTypes: true });
  const found = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) found.push(...await files(root, path));
    else found.push(relative(root, path));
  }
  return found;
}

async function digest(root) {
  const names = await files(root);
  const hash = createHash("sha256");
  for (const name of names) {
    hash.update(name);
    hash.update("\0");
    hash.update(await readFile(join(root, name)));
    hash.update("\0");
  }
  return { names, sha256: hash.digest("hex") };
}

try {
  build(first);
  build(second);
  const firstDigest = await digest(first);
  const secondDigest = await digest(second);

  if (JSON.stringify(firstDigest) !== JSON.stringify(secondDigest)) {
    throw new Error("successive source builds produced different assets");
  }

  const installedDigest = await digest(templates);
  if (JSON.stringify(installedDigest) !== JSON.stringify(firstDigest)) {
    throw new Error("compiled templates do not match a fresh source build");
  }

  const expected = ["assets/app.css", "assets/app.js", "index.html"];
  if (JSON.stringify(firstDigest.names) !== JSON.stringify(expected)) {
    throw new Error(`unexpected bundle file set: ${firstDigest.names.join(", ")}`);
  }

  const builtText = (await Promise.all(
    installedDigest.names.map((name) => readFile(join(templates, name), "utf8")),
  )).join("\n");
  const forbidden = [
    "GAUNTLET · WORKING PROTOTYPE",
    "Play all states",
    "Pause sequence",
    "Preview a progress state",
    "Choose a state or play the sequence",
    "review board",
    "Autoscaler Control Plane",
  ];
  const foundForbidden = forbidden.filter((label) => builtText.toLowerCase().includes(label.toLowerCase()));
  if (foundForbidden.length > 0) {
    throw new Error(`bundle retained forbidden preview content: ${foundForbidden.join(", ")}`);
  }
  const urls = builtText.match(/https?:\/\/[^\s"'`),]+/gi) ?? [];
  const libraryConstants = [
    "http://www.w3.org/",
    "https://react.dev/errors/",
  ];
  const runtimeUrls = urls.filter(
    (url) => !libraryConstants.some((prefix) => url.startsWith(prefix)),
  );
  if (runtimeUrls.length > 0) {
    throw new Error(`bundle contains a third-party runtime URL: ${runtimeUrls[0]}`);
  }

  process.stdout.write(
    `deterministic bundle ${firstDigest.sha256} (${firstDigest.names.join(", ")}); preview labels and runtime URLs absent\n`,
  );
} finally {
  await rm(temp, { recursive: true, force: true });
}
