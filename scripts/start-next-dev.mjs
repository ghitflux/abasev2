import { execFileSync, spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const webDir = path.join(repoRoot, "apps", "web");
const configuredDistDir = process.env.NEXT_DIST_DIR?.trim() || ".next";
const nextDistDir = path.isAbsolute(configuredDistDir)
  ? configuredDistDir
  : path.join(webDir, configuredDistDir);
const nextDevDir = path.join(nextDistDir, "dev");
const lockPath = path.join(nextDevDir, "lock");
const nextCliCandidates = [
  path.join(webDir, "node_modules", "next", "dist", "bin", "next"),
  path.join(webDir, "node_modules", "next", "dist", "bin", "next.js"),
];

function stopExistingNextDev() {
  if (process.platform !== "win32") {
    try {
      execFileSync(
        "pkill",
        ["-f", `${webDir}.+next/dist/bin/next dev`],
        { stdio: "ignore" }
      );
    } catch (error) {
      // pkill exits with status 1 when no process matches, which is expected.
    }
    return;
  }

  const escapedWebDir = webDir.replace(/'/g, "''");
  const command = [
    "$processes = Get-CimInstance Win32_Process",
    "| Where-Object { $_.Name -eq 'node.exe' }",
    "| Where-Object { $_.CommandLine -like '*next*dev*' -and $_.CommandLine -like '*" +
      escapedWebDir +
      "*' }",
    "| Select-Object -ExpandProperty ProcessId;",
    "if ($processes) { Stop-Process -Id $processes -Force }",
  ].join(" ");

  execFileSync(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
    { stdio: "ignore" }
  );
}

function removeLockIfPresent() {
  if (!existsSync(lockPath)) {
    return;
  }

  try {
    rmSync(lockPath, { force: true });
  } catch (error) {
    // Next recreates this file on startup. We only need to clear stale locks.
  }
}

function resetDevArtifacts() {
  if (!existsSync(nextDevDir)) {
    return;
  }

  try {
    rmSync(nextDevDir, { recursive: true, force: true });
  } catch (error) {
    const relativeDir = path.relative(repoRoot, nextDevDir) || nextDevDir;
    console.error(`Falha ao limpar ${relativeDir} antes de iniciar o Next.`);
    throw error;
  }
}

stopExistingNextDev();
removeLockIfPresent();
resetDevArtifacts();

const forwardedArgs = process.argv.slice(2);
const hasPortArg = forwardedArgs.some(
  (arg, index) =>
    arg === "--port" ||
    arg === "-p" ||
    arg.startsWith("--port=") ||
    (index > 0 && (forwardedArgs[index - 1] === "--port" || forwardedArgs[index - 1] === "-p"))
);
const defaultArgs = hasPortArg ? [] : ["--port", process.env.ABASE_WEB_PORT ?? "3000"];
const nextCliPath = nextCliCandidates.find((candidate) => existsSync(candidate));
const nextDevArgs = [nextCliPath, "dev", ...forwardedArgs, ...defaultArgs];

if (!nextCliPath) {
  console.error("Nao foi possivel localizar o CLI do Next em apps/web/node_modules.");
  process.exit(1);
}

const child = spawn(
  process.execPath,
  nextDevArgs,
  {
    cwd: webDir,
    env: process.env,
    stdio: "inherit",
  }
);

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
