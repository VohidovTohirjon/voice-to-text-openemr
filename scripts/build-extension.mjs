import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const sourceDir = path.join(projectRoot, "extension");
const outputDir = path.join(projectRoot, "dist", "extension");

if (!existsSync(sourceDir)) {
  console.error("Extension source directory not found:", sourceDir);
  process.exit(1);
}

rmSync(outputDir, { recursive: true, force: true });
mkdirSync(outputDir, { recursive: true });
cpSync(sourceDir, outputDir, { recursive: true });

console.log("Built extension into", outputDir);
