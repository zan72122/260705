// ほしのかわ「み」E2E検証
//   実行: cd test && npm install && node e2e.spec.mjs
//   - なぞりエミュレーション(正しい書き順 → 完成・進化・保存)
//   - ネガティブ系(始点以外・逆走 → 罰なし・進行なし)
//   - 回転(川の再投影)・簡易パフォーマンス
//   - 縦/横/iPad スクリーンショット出力(screenshots/)
import { launch, boot, tap, trace, strokePoints, ok, summary } from './helpers.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOT = p => path.join(__dirname, 'screenshots', p);
fs.mkdirSync(path.join(__dirname, 'screenshots'), { recursive: true });

const IPHONE_P = { width: 390, height: 844 };
const IPHONE_L = { width: 844, height: 390 };
const IPAD_P = { width: 820, height: 1180 };

/* =============== 1. メインフロー(iPhone縦) =============== */
console.log('\n[1] 正しい書き順で「み」完成(iPhone縦)');
{
  const { browser, page, cdp, errors } = await launch(IPHONE_P);
  await page.screenshot({ path: SHOT('01-boot-portrait.png') });
  await boot(page, cdp);

  // --- 1画目
  let pts = await strokePoints(page, 0);
  const mid = Math.floor(pts.length / 2);
  const tracePromise = trace(cdp, pts);
  // なぞり途中のスクショ(非同期でなぞりつつ中間で撮る)
  await new Promise(r => setTimeout(r, Math.floor(mid * 18)));
  await page.screenshot({ path: SHOT('02-tracing-stroke1.png') });
  await tracePromise;
  let s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex, sub: window.__MI_APP__.Game.sub, rivers: window.__MI_APP__.River.count() }));
  ok(s.idx === 1, `1画目完了で strokeIndex=1 (actual: ${s.idx})`);
  ok(s.rivers === 1, `光の川が1本定着 (actual: ${s.rivers})`);

  // --- 2画目
  pts = await strokePoints(page, 1);
  await trace(cdp, pts);
  s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex, sub: window.__MI_APP__.Game.sub }));
  ok(s.sub === 'celebrate', `2画完成で CELEBRATION 発動 (actual: ${s.sub})`);
  await page.screenshot({ path: SHOT('03-celebration.png') });

  // --- 演出終了 → 保存・進化を確認
  await page.waitForFunction(() => window.__MI_APP__.Game.sub === 'idle', null, { timeout: 8000 });
  const prog = await page.evaluate(() => {
    const saved = JSON.parse(localStorage.getItem('hoshinokawa.v1'));
    return { saved, mem: window.__MI_APP__.Progress.data, idx: window.__MI_APP__.Tracer.strokeIndex };
  });
  ok(prog.saved && prog.saved.completions === 1, `localStorage に completions=1 保存 (actual: ${prog.saved && prog.saved.completions})`);
  ok(prog.mem.inkLevel === 1, `1回完成でインク Lv1 に進化 (actual: ${prog.mem.inkLevel})`);
  ok(prog.idx === 0, `次の周回に向けて strokeIndex リセット (actual: ${prog.idx})`);
  ok(prog.saved.wordsHeard.length === 1, `「み」のことばを1つ獲得 (actual: ${prog.saved.wordsHeard.length})`);

  // --- 2周目も完走できる(川の置き換え・進化後インク)
  await trace(cdp, await strokePoints(page, 0));
  await trace(cdp, await strokePoints(page, 1));
  await page.waitForFunction(() => window.__MI_APP__.Game.sub === 'idle', null, { timeout: 8000 });
  const c2 = await page.evaluate(() => window.__MI_APP__.Progress.data.completions);
  ok(c2 === 2, `2周目も完成 completions=2 (actual: ${c2})`);

  ok(errors.length === 0, `JSエラーなし (actual: ${errors.join(' | ') || 'none'})`);
  await browser.close();
}

/* =============== 2. ネガティブ系(罰ゼロ設計) =============== */
console.log('\n[2] 始点以外・逆走 → 進行せず・エラーにもならない');
{
  const { browser, page, cdp, errors } = await launch(IPHONE_P);
  await boot(page, cdp);

  // --- 始点から遠い場所でなぞり → 自由描きのまま
  const far = await page.evaluate(() => {
    const A = window.__MI_APP__;
    const [sx, sy] = A.Tracer.startPoint();
    // 始点から十分離れた場所(画面内)を返す
    return [sx > innerWidth / 2 ? 40 : innerWidth - 40, sy > innerHeight / 2 ? 80 : innerHeight - 80];
  });
  await trace(cdp, [far, [far[0] + 30, far[1] + 40], [far[0] + 60, far[1] + 80]]);
  let s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex, sub: window.__MI_APP__.Game.sub }));
  ok(s.idx === 0 && s.sub === 'idle', `始点以外は自由描き扱い(strokeIndex=${s.idx}, sub=${s.sub})`);

  // --- 始点から逆方向へなぞる → 静かに降格、進行なし
  const pts = await strokePoints(page, 0);
  const [sx, sy] = pts[0];
  const away = [];
  for (let i = 0; i <= 10; i++) away.push([sx - i * 14, sy + i * 20]);   // 正解と逆へ
  await trace(cdp, away);
  s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex, sub: window.__MI_APP__.Game.sub, tracing: window.__MI_APP__.Tracer.tracing }));
  ok(s.idx === 0 && !s.tracing, `逆走は進まず静かに降格(strokeIndex=${s.idx}, tracing=${s.tracing})`);

  // --- 途中まで正しくなぞって指を離す → 罰なし・同じ画をやり直せる
  await trace(cdp, pts.slice(0, Math.floor(pts.length * 0.4)));
  s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex, rivers: window.__MI_APP__.River.count() }));
  ok(s.idx === 0 && s.rivers === 0, `40%で離すと未完了・川は増えない(strokeIndex=${s.idx})`);
  await trace(cdp, pts);
  s = await page.evaluate(() => ({ idx: window.__MI_APP__.Tracer.strokeIndex }));
  ok(s.idx === 1, `やり直しで完了できる (strokeIndex=${s.idx})`);

  ok(errors.length === 0, `JSエラーなし (actual: ${errors.join(' | ') || 'none'})`);
  await browser.close();
}

/* =============== 3. 回転(縦→横)で川が再投影される =============== */
console.log('\n[3] 画面回転で光の川が画面内に再投影される');
{
  const { browser, page, cdp, errors } = await launch(IPHONE_P);
  await boot(page, cdp);
  await trace(cdp, await strokePoints(page, 0));
  await page.setViewportSize(IPHONE_L);
  await page.waitForTimeout(600);   // resize デバウンス
  const box = await page.evaluate(() => {
    const r = window.__MI_APP__.River.rivers[0];
    let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
    for (const [x, y] of r.poly) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    return { minX, maxX, minY, maxY, w: innerWidth, h: innerHeight };
  });
  ok(box.minX >= 0 && box.maxX <= box.w && box.minY >= 0 && box.maxY <= box.h,
    `横画面でも川が画面内 (bbox ${box.minX.toFixed(0)},${box.minY.toFixed(0)} - ${box.maxX.toFixed(0)},${box.maxY.toFixed(0)} in ${box.w}x${box.h})`);
  await page.screenshot({ path: SHOT('04-landscape-river.png') });

  // 横画面のままなぞれる(再投影後の判定も正しい)
  await trace(cdp, await strokePoints(page, 1));
  const s = await page.evaluate(() => window.__MI_APP__.Game.sub);
  ok(s === 'celebrate', `横画面でも2画目を完了できる (sub=${s})`);
  ok(errors.length === 0, `JSエラーなし (actual: ${errors.join(' | ') || 'none'})`);
  await browser.close();
}

/* =============== 4. 簡易パフォーマンス =============== */
console.log('\n[4] パーティクル大量発生中のフレーム時間');
{
  const { browser, page, cdp, errors } = await launch(IPHONE_P);
  await boot(page, cdp);
  // 画面中をぐるぐる自由描きして負荷をかける
  const swirl = [];
  for (let i = 0; i < 60; i++) {
    swirl.push([195 + Math.cos(i * 0.4) * 150, 420 + Math.sin(i * 0.4) * 300]);
  }
  const tracePromise = trace(cdp, swirl, { stepMs: 8 });
  const avgDt = await page.evaluate(() => new Promise(res => {
    let n = 0, sum = 0, last = performance.now();
    function f(t) { sum += t - last; last = t; if (++n >= 100) res(sum / n); else requestAnimationFrame(f); }
    requestAnimationFrame(f);
  }));
  await tracePromise;
  ok(avgDt < 25, `平均フレーム時間 ${avgDt.toFixed(1)}ms < 25ms(ヘッドレス緩め閾値)`);
  ok(errors.length === 0, `JSエラーなし`);
  await browser.close();
}

/* =============== 5. ビジュアル確認用スクリーンショット =============== */
console.log('\n[5] 各画面サイズのスクリーンショット出力');
{
  // ?d ガイド表示(字形確認用)
  const d = await launch(IPHONE_P, { query: '?d&test' });
  await boot(d.page, d.cdp);
  await d.page.waitForTimeout(400);
  await d.page.screenshot({ path: SHOT('05-debug-guides.png') });
  await d.browser.close();

  // iPad縦: 1画目の川がある状態
  const t = await launch(IPAD_P);
  await boot(t.page, t.cdp);
  await trace(t.cdp, await strokePoints(t.page, 0));
  await t.page.waitForTimeout(700);
  await t.page.screenshot({ path: SHOT('06-ipad-river.png') });
  await t.browser.close();
  console.log('  ✓ screenshots/ に6枚出力');
}

summary();
