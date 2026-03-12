import { execFileSync, spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const webDir = path.join(repoRoot, "apps", "web");
const lockPath = path.join(webDir, ".next", "dev", "lock");

function stopExistingNextDev() {
  if (process.platform !== "win32") {
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

stopExistingNextDev();
removeLockIfPresent();

const forwardedArgs = process.argv.slice(2);
const hasPortArg = forwardedArgs.some(
  (arg, index) =>
    arg === "--port" ||
    arg === "-p" ||
    arg.startsWith("--port=") ||
    (index > 0 && (forwardedArgs[index - 1] === "--port" || forwardedArgs[index - 1] === "-p"))
);
const defaultArgs = hasPortArg ? [] : ["--port", process.env.ABASE_WEB_PORT ?? "8000"];

const child = spawn("pnpm", ["exec", "next", "dev", "--turbopack", ...forwardedArgs, ...defaultArgs], {
  cwd: webDir,
  stdio: "inherit",
  shell: true,
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
