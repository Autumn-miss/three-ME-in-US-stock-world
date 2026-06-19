const { chromium } = require("playwright");
const path = require("path");

async function main() {
  const repoRoot = path.resolve(__dirname, "..");
  const svgPath = path.join(repoRoot, "assets", "social", "repo-cover.svg");
  const pngPath = path.join(repoRoot, "assets", "social", "repo-cover.png");
  const fileUrl = `file://${svgPath}`;

  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });

  const page = await browser.newPage({
    viewport: { width: 1280, height: 640 },
    deviceScaleFactor: 1,
  });

  await page.goto(fileUrl, { waitUntil: "load" });
  await page.screenshot({ path: pngPath });
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
