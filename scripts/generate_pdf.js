const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  const htmlPath = path.resolve(__dirname, '../docs/lore.html');
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0' });

  // Apply light theme for cleaner PDF output
  await page.evaluate(() => {
    document.documentElement.setAttribute('data-theme', 'light');
  });

  // Wait for any transitions to settle
  await new Promise(r => setTimeout(r, 500));

  const pdfPath = path.resolve(__dirname, '../docs/lore.pdf');
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    margin: { top: '14mm', bottom: '14mm', left: '14mm', right: '14mm' },
    displayHeaderFooter: false,
  });

  await browser.close();
  console.log('PDF saved to docs/lore.pdf');
})();
