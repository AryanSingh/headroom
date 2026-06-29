const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  page.on('response', response => {
    if (!response.ok()) {
      console.log('BAD RESPONSE:', response.status(), response.url());
    }
  });

  await page.goto('http://127.0.0.1:8787/dashboard', { waitUntil: 'networkidle0' });
  
  await browser.close();
})();
