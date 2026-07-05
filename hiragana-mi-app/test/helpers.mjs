// テスト共有ヘルパー: 起動・タッチエミュレーション・なぞり
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const APP_URL = 'file://' + path.resolve(__dirname, '..', 'index.html');

// この環境のプリインストールChromium(README参照)
const EXEC = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';

export async function launch(viewport, { query = '?test' } = {}) {
  const browser = await chromium.launch({ executablePath: EXEC });
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 2,
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(APP_URL + query);
  await page.waitForFunction(() => window.__MI_APP__ && window.__MI_APP__.Game);
  const cdp = await context.newCDPSession(page);
  return { browser, context, page, cdp, errors };
}

export async function tap(cdp, x, y) {
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
}

// BOOT解除(音アンロック用の初回タップ)
export async function boot(page, cdp) {
  const [w, h] = await page.evaluate(() => [window.innerWidth, window.innerHeight]);
  await tap(cdp, w / 2, h / 2);
  await page.waitForFunction(() => window.__MI_APP__.Game.state === 'play');
}

// アプリ自身の字形データから画 i のなぞり点列を取得(実装と座標変換を共有)
export function strokePoints(page, i, spacing = 12) {
  return page.evaluate(([idx, sp]) => window.__MI_APP__.getStrokeScreenPoints(idx, sp), [i, spacing]);
}

// 点列に沿って本番同等のタッチなぞり(touchStart → move… → touchEnd)
export async function trace(cdp, points, { stepMs = 18 } = {}) {
  const [sx, sy] = points[0];
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: sx, y: sy }] });
  for (let i = 1; i < points.length; i++) {
    const [x, y] = points[i];
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y }] });
    await new Promise(r => setTimeout(r, stepMs));
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
}

// 簡易アサート
let failures = 0;
export function ok(cond, label) {
  if (cond) console.log(`  ✓ ${label}`);
  else { failures++; console.error(`  ✗ FAIL: ${label}`); }
}
export function summary() {
  if (failures) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
  console.log('\nall assertions passed');
}
