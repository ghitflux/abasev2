#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.QA_PLAYWRIGHT_MODULE ?? "playwright-core");

const BASE_URL = process.env.QA_BASE_URL ?? "http://localhost:3000";
const CHROMIUM_PATH = process.env.QA_CHROMIUM_PATH ?? "/usr/bin/chromium-browser";
const OUTPUT_PATH =
  process.env.QA_OUTPUT_PATH ??
  path.join(process.cwd(), "docs", "QA_EXECUCAO_CHECKLIST_2026-03-22.md");

const credentials = {
  ADMIN: { email: "admin@abase.local", password: "Admin@123", defaultRoute: "/dashboard" },
  AGENTE: {
    email: "agente@abase.local",
    password: "Senha@123",
    defaultRoute: "/agentes/meus-contratos",
  },
  ANALISTA: {
    email: "analista@abase.local",
    password: "Senha@123",
    defaultRoute: "/analise",
  },
  COORDENADOR: {
    email: "coordenador@abase.local",
    password: "Senha@123",
    defaultRoute: "/coordenacao/refinanciamento",
  },
  TESOUREIRO: {
    email: "tesoureiro@abase.local",
    password: "Senha@123",
    defaultRoute: "/tesouraria",
  },
};

const accessibleRoutes = {
  ADMIN: ["/dashboard", "/associados", "/relatorios", "/importacao", "/tesouraria/despesas"],
  AGENTE: [
    "/agentes/meus-contratos",
    "/agentes/cadastrar-associado",
    "/agentes/esteira-pendencias",
    "/agentes/refinanciados",
    "/agentes/pagamentos",
  ],
  ANALISTA: ["/analise", "/analise/aptos", "/associados/1"],
  COORDENADOR: [
    "/dashboard",
    "/coordenacao/refinanciamento",
    "/coordenacao/refinanciados",
    "/importacao",
    "/associados",
    "/configuracoes/usuarios",
  ],
  TESOUREIRO: [
    "/tesouraria",
    "/tesouraria/refinanciamentos",
    "/tesouraria/baixa-manual",
    "/tesouraria/liquidacoes",
    "/tesouraria/devolucoes",
    "/tesouraria/despesas",
    "/associados/1",
  ],
};

const blockedExamples = {
  AGENTE: ["/dashboard", "/importacao", "/relatorios", "/coordenacao/refinanciamento"],
  ANALISTA: ["/dashboard", "/importacao", "/relatorios", "/tesouraria/despesas"],
  COORDENADOR: ["/relatorios", "/tesouraria/despesas"],
  TESOUREIRO: ["/dashboard", "/importacao", "/relatorios", "/coordenacao/refinanciamento"],
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function absolute(urlPath) {
  return new URL(urlPath, BASE_URL).toString();
}

async function waitForStableLocation(page, timeout = 15000) {
  const startedAt = Date.now();
  let previous = page.url();
  let stableFor = 0;

  while (Date.now() - startedAt < timeout) {
    await sleep(250);
    const current = page.url();
    if (current === previous) {
      stableFor += 250;
      if (stableFor >= 2500) {
        return current;
      }
    } else {
      previous = current;
      stableFor = 0;
    }
  }

  return page.url();
}

async function login(page, role) {
  const { email, password, defaultRoute } = credentials[role];
  await page.goto(absolute("/login"), { waitUntil: "domcontentloaded" });
  await page.waitForSelector('input[name="email"]', { timeout: 15000 });
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.getByRole("button", { name: /entrar/i }).click();
  await sleep(4000);
  const finalUrl = await waitForStableLocation(page);
  return {
    expected: absolute(defaultRoute),
    actual: finalUrl,
    ok: finalUrl.includes(defaultRoute),
  };
}

async function openProfileMenu(page) {
  await page.waitForLoadState("domcontentloaded").catch(() => null);
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => null);
  await sleep(500);
  const header = page.locator("header");
  if ((await header.count()) === 0) {
    return false;
  }
  const trigger = header.locator("button").last();
  if ((await trigger.count()) === 0) {
    return false;
  }
  await trigger.click();
  await page.waitForTimeout(300);
  return true;
}

async function checkNoSessionRedirect(browser, targetPath) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(absolute(targetPath), { waitUntil: "domcontentloaded" });
  await sleep(4000);
  const finalUrl = await waitForStableLocation(page);
  await context.close();
  return {
    path: targetPath,
    finalUrl,
    ok:
      finalUrl.includes("/login") &&
      (targetPath === "/" ||
        finalUrl.includes(`next=${encodeURIComponent(targetPath)}`) ||
        finalUrl.includes(`next=${targetPath}`)),
  };
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROMIUM_PATH,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const report = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    phase0: {},
    roleChecks: {},
  };

  report.phase0.rootRedirect = await checkNoSessionRedirect(browser, "/");
  report.phase0.protectedRedirects = [];
  for (const target of ["/associados", "/dashboard", "/tesouraria"]) {
    report.phase0.protectedRedirects.push(await checkNoSessionRedirect(browser, target));
  }

  const invalidContext = await browser.newContext();
  const invalidPage = await invalidContext.newPage();
  await invalidPage.goto(absolute("/login"), { waitUntil: "domcontentloaded" });
  await invalidPage.waitForSelector('input[name="email"]');
  await invalidPage.fill('input[name="email"]', credentials.ADMIN.email);
  await invalidPage.fill('input[name="password"]', "SenhaErrada@123");
  await invalidPage.getByRole("button", { name: /entrar/i }).click();
  await invalidPage.waitForTimeout(1500);
  const invalidText = await invalidPage.textContent("body");
  report.phase0.invalidLogin = {
    ok:
      invalidPage.url().includes("/login") &&
      /falha ao autenticar|credenciais|unauthorized|não autorizado|nao autorizado/i.test(
        invalidText ?? "",
      ),
    finalUrl: invalidPage.url(),
  };
  await invalidContext.close();

  for (const role of Object.keys(credentials)) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const loginResult = await login(page, role);
    const profileMenuOpened = await openProfileMenu(page);
    const profileText = profileMenuOpened ? await page.textContent("[data-radix-popper-content-wrapper]") : "";
    const dashboardVisible = /dashboard/i.test(profileText ?? "");

    const accessible = [];
    for (const route of accessibleRoutes[role] ?? []) {
      await page.goto(absolute(route), { waitUntil: "domcontentloaded" });
      await sleep(4000);
      const finalUrl = await waitForStableLocation(page);
      accessible.push({
        route,
        finalUrl,
        ok: finalUrl.includes(route),
      });
    }

    const blocked = [];
    for (const route of blockedExamples[role] ?? []) {
      await page.goto(absolute(route), { waitUntil: "domcontentloaded" });
      await sleep(4000);
      const finalUrl = await waitForStableLocation(page);
      blocked.push({
        route,
        finalUrl,
        ok: finalUrl.includes(credentials[role].defaultRoute),
      });
    }

    report.roleChecks[role] = {
      login: loginResult,
      dashboardVisibleInProfile: dashboardVisible,
      dashboardExpectedInProfile: role === "ADMIN" || role === "COORDENADOR",
      accessible,
      blocked,
    };

    await context.close();
  }

  await browser.close();

  const lines = [];
  lines.push("# Execução QA do Checklist Web");
  lines.push("");
  lines.push(`Gerado em ${new Date(report.generatedAt).toISOString()}.`);
  lines.push("");
  lines.push("## Fase 0");
  lines.push("");
  lines.push(
    `- Acesso raiz sem sessão: ${report.phase0.rootRedirect.ok ? "OK" : "FALHOU"} -> ${report.phase0.rootRedirect.finalUrl}`,
  );
  lines.push(
    `- Login inválido: ${report.phase0.invalidLogin.ok ? "OK" : "FALHOU"} -> ${report.phase0.invalidLogin.finalUrl}`,
  );
  for (const item of report.phase0.protectedRedirects) {
    lines.push(`- Guard sem sessão ${item.path}: ${item.ok ? "OK" : "FALHOU"} -> ${item.finalUrl}`);
  }
  lines.push("");
  lines.push("## Acessos por Papel");
  lines.push("");
  for (const [role, result] of Object.entries(report.roleChecks)) {
    lines.push(`### ${role}`);
    lines.push(
      `- Login/redirect: ${result.login.ok ? "OK" : "FALHOU"} -> esperado ${result.login.expected}, atual ${result.login.actual}`,
    );
    lines.push(
      `- Menu de perfil / Dashboard: ${
        result.dashboardVisibleInProfile === result.dashboardExpectedInProfile ? "OK" : "FALHOU"
      } -> visível=${result.dashboardVisibleInProfile}, esperado=${result.dashboardExpectedInProfile}`,
    );
    lines.push("- Rotas permitidas:");
    for (const item of result.accessible) {
      lines.push(`  - ${item.route}: ${item.ok ? "OK" : "FALHOU"} -> ${item.finalUrl}`);
    }
    lines.push("- Rotas bloqueadas:");
    for (const item of result.blocked) {
      lines.push(`  - ${item.route}: ${item.ok ? "OK" : "FALHOU"} -> ${item.finalUrl}`);
    }
    lines.push("");
  }

  await fs.writeFile(OUTPUT_PATH, `${lines.join("\n")}\n`, "utf8");
  process.stdout.write(`${OUTPUT_PATH}\n`);
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
