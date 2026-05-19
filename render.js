/**
 * render.js — Velixia HTML5 → MP4 renderer via Puppeteer
 *
 * Usage:
 *   node render.js tiktok     → velixia_tiktok_final.mp4    (1080×1920)
 *   node render.js instagram  → velixia_instagram_final.mp4 (1080×1080)
 *
 * Requirements:
 *   npm install puppeteer
 *   ffmpeg must be in PATH
 *
 * The script:
 *   1. Launches Chrome headless via Puppeteer
 *   2. Loads the HTML file with --no-sandbox
 *   3. Injects a mock audio.currentTime that advances at real speed
 *   4. Captures PNG frames at FPS rate using Page.screencast or screenshot
 *   5. Pipes frames to ffmpeg → H.264 MP4 with original audio
 */

const puppeteer = require('puppeteer');
const { execSync, spawn } = require('child_process');
const path  = require('path');
const fs    = require('fs');
const os    = require('os');

const FORMAT   = process.argv[2] || 'instagram';
const DIM      = { tiktok: [1080, 1920], instagram: [1080, 1080] }[FORMAT];
const FPS      = 30;
const DURATION = 88; // seconds — full timeline + fade

if (!DIM) {
  console.error('Usage: node render.js [tiktok|instagram]');
  process.exit(1);
}

const [W, H]    = DIM;
const HTML_FILE = path.resolve(__dirname, `index_${FORMAT}.html`);
const AUDIO     = path.resolve(__dirname, 'velixia_voiceover_v1.mp3');
const OUT_MP4   = path.resolve(__dirname, `velixia_${FORMAT}_final.mp4`);
const TMP_DIR   = fs.mkdtempSync(path.join(os.tmpdir(), `velixia-${FORMAT}-`));

const TOTAL_FRAMES = DURATION * FPS;

console.log(`\n▶ Velixia renderer — ${FORMAT.toUpperCase()}`);
console.log(`  Dimensions : ${W}×${H}`);
console.log(`  Duration   : ${DURATION}s @ ${FPS}fps = ${TOTAL_FRAMES} frames`);
console.log(`  Frames dir : ${TMP_DIR}`);
console.log(`  Output     : ${OUT_MP4}\n`);

async function render() {
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-web-security',
      '--allow-file-access-from-files',
      `--window-size=${W},${H}`,
    ],
    defaultViewport: { width: W, height: H, deviceScaleFactor: 1 },
  });

  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });

  // Suppress console noise
  page.on('console', msg => {
    if (msg.type() === 'error') console.error('  PAGE:', msg.text());
  });

  // Load HTML
  await page.goto(`file://${HTML_FILE}`, { waitUntil: 'networkidle0', timeout: 30000 });

  // Wait for fonts
  await page.evaluateHandle(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 1000));

  // Hide play screen and inject a synthetic currentTime
  await page.evaluate(() => {
    // Remove the play screen immediately
    const ps = document.getElementById('play-screen');
    if (ps) ps.style.display = 'none';

    // Override audio object so syncLoop reads our injected currentTime
    window.__velixia_t = 0;
    window.__velixia_speed = 1; // 1 = real-time
    window.__audio_mock = {
      currentTime: 0,
      paused: false,
      ended: false,
      play: () => Promise.resolve(),
      pause: () => {},
      load: () => {},
      addEventListener: (evt, cb) => {
        if (evt === 'play') window.__on_play = cb;
        if (evt === 'seeked') window.__on_seeked = cb;
      },
    };
    // Replace audio reference in global scope
    // (The HTML uses const audio = new Audio(...), so we patch currentTime getter)
    // We'll use a MutationObserver / RAF trick instead:
    // Inject a global time ticker that syncLoop will read
    window.__raf_time = 0;
    const _raf = window.requestAnimationFrame;
    window.requestAnimationFrame = function(cb) {
      return _raf.call(window, (ts) => cb(ts));
    };
  });

  // Start the demo timeline (compressed to real-time via injected timer)
  await page.evaluate(() => {
    // We call startVideo() but since demoMode depends on audio duration
    // we force demo mode manually
    window.demoMode = true;
    if (typeof runDemoTimeline === 'function') {
      runDemoTimeline();
    } else {
      // Fallback: trigger play-screen click
      document.getElementById('play-screen').click();
    }
  });

  // Override demo speed to run at normal pace (SPEED=1 → 1ms/ms)
  // The demo mode uses SPEED=0.15 by default. For rendering we want
  // to capture frame-by-frame, so we re-run with adjusted timing.

  // ── Frame capture loop ────────────────────────────────────────────────────
  console.log('  Capturing frames…');
  const frameTime = 1000 / FPS; // ms per frame

  // Re-inject real-time demo (SPEED=1, ~85 seconds wall time)
  // For rendering we run the full timeline synchronously then screenshot.
  // Approach: inject timeline execution at each synthetic timestamp.

  await page.evaluate((TOTAL_FRAMES, FPS, DURATION) => {
    // Rebuild triggered set and run events at synthetic timestamps
    window.__render_triggered = new Set();
    window.__render_timeline  = window.TIMELINE; // exposed from HTML

    // We'll advance synthetic time via a custom runner
    window.__render_run = function(frame) {
      const t = frame / FPS;
      if (!window.__render_timeline) return;
      for (const [time, id, fn] of window.__render_timeline) {
        if (t >= time - 0.08 && !window.__render_triggered.has(id)) {
          window.__render_triggered.add(id);
          try { fn(); } catch(e) {}
        }
      }
    };
  }, TOTAL_FRAMES, FPS, DURATION);

  let captured = 0;
  const progress = Math.max(1, Math.round(TOTAL_FRAMES / 20));

  for (let frame = 0; frame < TOTAL_FRAMES; frame++) {
    // Advance synthetic timeline
    await page.evaluate((f) => {
      if (typeof window.__render_run === 'function') window.__render_run(f);
    }, frame);

    // Wait one rAF cycle for animations to settle
    await page.evaluate(() => new Promise(r => requestAnimationFrame(r)));

    // Screenshot
    const framePath = path.join(TMP_DIR, `frame_${String(frame).padStart(6,'0')}.png`);
    await page.screenshot({ path: framePath, type: 'png' });
    captured++;

    if (frame % progress === 0) {
      const pct = Math.round(frame / TOTAL_FRAMES * 100);
      process.stdout.write(`\r  Progress: ${pct}% (${frame}/${TOTAL_FRAMES} frames)`);
    }
  }
  console.log(`\r  Progress: 100% (${TOTAL_FRAMES}/${TOTAL_FRAMES} frames) ✓`);

  await browser.close();

  // ── FFmpeg assembly ───────────────────────────────────────────────────────
  console.log('\n  Assembling MP4 with FFmpeg…');

  const ffmpegArgs = [
    '-y',
    '-r', String(FPS),
    '-i', path.join(TMP_DIR, 'frame_%06d.png'),
    '-i', AUDIO,
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-crf', '16',
    '-preset', 'slow',
    '-c:a', 'aac',
    '-b:a', '192k',
    '-shortest',
    '-movflags', '+faststart',
    OUT_MP4,
  ];

  await new Promise((resolve, reject) => {
    const ff = spawn('ffmpeg', ffmpegArgs, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    ff.stderr.on('data', d => { stderr += d.toString(); });
    ff.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error('FFmpeg failed:\n' + stderr.slice(-2000)));
    });
  });

  // Cleanup temp frames
  fs.rmSync(TMP_DIR, { recursive: true, force: true });

  const sizeMB = (fs.statSync(OUT_MP4).size / 1048576).toFixed(1);
  console.log(`\n✅ Done!`);
  console.log(`   ${OUT_MP4}`);
  console.log(`   ${sizeMB} MB, ${W}×${H}, ${FPS}fps\n`);
}

render().catch(err => {
  console.error('\n❌ Error:', err.message);
  process.exit(1);
});
