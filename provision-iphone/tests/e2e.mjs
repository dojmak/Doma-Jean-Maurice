// e2e.mjs — test de bout en bout de la web app dans Chromium en émulation iPhone.
// Compare le fichier produit dans le navigateur (Pyodide) à celui produit par le moteur natif.
// Usage : node tests/e2e.mjs <url_app> <classeur.xlsx> <dossier_sortie>
// (NODE_PATH doit pointer vers une installation de playwright)
import { chromium, devices } from "playwright";
import path from "node:path";

const [url, sample, outDir] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ ...devices["iPhone 13"], acceptDownloads: true });
const page = await ctx.newPage();
page.on("pageerror", e => console.error("pageerror:", e.message));

await page.goto(url);
await page.setInputFiles("#file", sample);
await page.waitForSelector("#btnPreview:not([disabled])", { timeout: 120000 });
await page.click("#btnPreview");
await page.waitForSelector("#secConfirm:not(.hidden) dl dd");
console.log("ENTREES:", (await page.textContent("#inputs")).replace(/\s+/g, " "));
await page.screenshot({ path: path.join(outDir, "iphone_step2.png"), fullPage: true });
await page.check("#confirm");
await page.fill("#prevR", "500000");
await page.click("#btnRun");
await page.waitForSelector("#secResult:not(.hidden) #kpi div", { timeout: 120000 });
console.log("STDOUT:\n" + await page.textContent("#stdout"));
console.log("BANNIERES:", (await page.textContent("#resultBanners")).replace(/\s+/g, " "));
await page.screenshot({ path: path.join(outDir, "iphone_step4.png"), fullPage: true });
const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#dl button")]);
const target = path.join(outDir, "web_" + dl.suggestedFilename());
await dl.saveAs(target);
console.log("DOWNLOAD:", target);
await browser.close();
