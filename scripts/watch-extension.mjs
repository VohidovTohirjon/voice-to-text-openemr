import { watch } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const extensionDir = path.join(projectRoot, "extension");

let buildProcess = null;
let pending = false;

function runBuild() {
  if (buildProcess) {
    pending = true;
    return;
  }

  buildProcess = spawn(process.execPath, [path.join(__dirname, "build-extension.mjs")], {
    cwd: projectRoot,
    stdio: "inherit"
  });

  buildProcess.on("exit", function () {
    buildProcess = null;
    if (pending) {
      pending = false;
      runBuild();
    }
  });
}

runBuild();
console.log("Watching extension sources in", extensionDir);

watch(extensionDir, { recursive: true }, function (_eventType, filename) {
  if (!filename) {
    return;
  }

  runBuild();
});
