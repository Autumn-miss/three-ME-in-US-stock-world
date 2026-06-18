const { chromium } = require("playwright");

async function capture() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });

  const pages = [
    {
      url: "https://github.com/Autumn-miss/three-ME-in-US-stock-world",
      path: "assets/screenshots/github-repo-home.png",
      viewport: { width: 1440, height: 1600 },
      fullPage: false,
      waitFor: { selector: "article.markdown-body" },
    },
    {
      url: "http://127.0.0.1:8501/",
      path: "assets/screenshots/strategy-dashboard.png",
      viewport: { width: 1440, height: 1400 },
      fullPage: false,
      waitFor: { selector: '[data-testid="stAppViewContainer"]' },
      afterLoad: async (page) => {
        await page.getByText("Strategy", { exact: true }).click();
        await page.waitForTimeout(1200);
      },
    },
    {
      url: "http://127.0.0.1:8501/",
      path: "assets/screenshots/returns-dashboard.png",
      viewport: { width: 1440, height: 1400 },
      fullPage: false,
      waitFor: { selector: '[data-testid="stAppViewContainer"]' },
      afterLoad: async (page) => {
        await page.getByText("Returns", { exact: true }).click();
        await page.waitForTimeout(1200);
      },
    },
    {
      url: "http://127.0.0.1:8501/",
      path: "assets/screenshots/holdings-dashboard.png",
      viewport: { width: 1440, height: 1400 },
      fullPage: false,
      waitFor: { selector: '[data-testid="stAppViewContainer"]' },
      afterLoad: async (page) => {
        await page.getByText("Holdings", { exact: true }).click();
        await page.waitForTimeout(1200);
      },
    },
  ];

  for (const pageDef of pages) {
    const page = await browser.newPage({ viewport: pageDef.viewport });
    await page.goto(pageDef.url, { waitUntil: "networkidle" });
    if (pageDef.waitFor?.selector) {
      await page.waitForSelector(pageDef.waitFor.selector, { timeout: 30000 });
    }
    if (pageDef.afterLoad) {
      await pageDef.afterLoad(page);
    }
    await page.screenshot({ path: pageDef.path, fullPage: pageDef.fullPage });
    await page.close();
  }

  await browser.close();
}

capture().catch((error) => {
  console.error(error);
  process.exit(1);
});
