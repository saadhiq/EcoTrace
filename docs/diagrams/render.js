// Render Mermaid sources to 1920x1080 PNGs (slide size) with Playwright + mermaid from jsDelivr.
// Usage (needs Playwright): node docs/diagrams/render.js docs/diagrams architecture process-flow
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const [, , dir, ...names] = process.argv;
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const name of names) {
    const src = fs.readFileSync(path.join(dir, `${name}.mmd`), 'utf8');
    const title = name === 'architecture' ? 'EcoTrace · Architecture (Google Cloud, asia-south1)' : 'EcoTrace · Process flow';
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;width:1920px;height:1080px;background:#fff;font-family:"Segoe UI",Arial,sans-serif}
h1{margin:0;padding:36px 56px 0;font-size:44px;color:#17201b}
#d{position:absolute;top:120px;left:40px;right:40px;bottom:40px;display:flex;align-items:center;justify-content:center}
#d svg{max-width:100%;max-height:100%;height:auto}</style></head>
<body><h1>${title}</h1><div id="d"></div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad:false,theme:'base',flowchart:{curve:'basis',padding:18,nodeSpacing:40,rankSpacing:60,htmlLabels:true},
themeVariables:{fontFamily:'Segoe UI, Arial, sans-serif',fontSize:'22px',lineColor:'#5b6b62',primaryTextColor:'#17201b',clusterBkg:'#f5f7f5',clusterBorder:'#dce3de',edgeLabelBackground:'#ffffff'}});
mermaid.render('g', ${JSON.stringify(src)}).then(({svg})=>{document.getElementById('d').innerHTML=svg;
const s=document.querySelector('#d svg');s.removeAttribute('style');s.setAttribute('width','100%');s.setAttribute('height','100%');window.done=true}).catch(e=>{window.err=String(e)});</script></body></html>`);
    await page.waitForFunction(() => window.done || window.err, null, { timeout: 30000 });
    const err = await page.evaluate(() => window.err);
    if (err) { console.log(name, 'ERROR', err); continue; }
    await page.screenshot({ path: path.join(dir, `${name}.png`) });
    console.log(name, 'ok');
  }
  await browser.close();
})();
