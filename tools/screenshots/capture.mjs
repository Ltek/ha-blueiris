// Take the README screenshots from a real Home Assistant running this integration
// against the made-up Blue Iris server (tools/screenshots/fake_blue_iris.py).
// Run through tools/screenshots/run.sh, which starts both and then this script:
//   HA_URL=http://127.0.0.1:8124 node tools/screenshots/capture.mjs
// Needs playwright-core and its Chromium (npx playwright install chromium).
// Files go to screenshots/; push them and the GitHub workflow rebuilds the README gallery.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, '../../screenshots');
const HA = process.env.HA_URL || 'http://127.0.0.1:8124';
const BI_PORT = process.env.BI_PORT || '8181';

let chromium;
for (const mod of [process.env.PLAYWRIGHT_CORE, 'playwright-core', 'playwright'].filter(Boolean)) {
  try {
    ({ chromium } = await import(mod));
    break;
  } catch (_e) { /* try the next one */ }
}
if (!chromium) {
  console.error('playwright-core not found: npm i --no-save playwright-core, or set PLAYWRIGHT_CORE');
  process.exit(1);
}

fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1400, height: 950 },
  deviceScaleFactor: 1,
  colorScheme: 'dark',
});
const page = await context.newPage();

const settle = (ms = 1500) => page.waitForTimeout(ms);
const shot = async (name, options = {}) => {
  await settle(options.wait ?? 1200);
  const file = path.join(OUT, `${name}.png`);
  if (options.dialog) {
    await page.locator('ha-dialog, dialog-data-entry-flow').first().waitFor();
  }
  await page.screenshot({ path: file, fullPage: false });
  console.log('saved', path.relative(process.cwd(), file));
};

async function login() {
  await page.goto(`${HA}/`);
  await page.getByLabel('Username', { exact: true }).fill('demo');
  await page.getByLabel('Password', { exact: true }).fill('demo');
  await page.keyboard.press('Enter');
  await page.waitForURL(/lovelace|cameras|config|history/, { timeout: 30000 });
  await settle(2500);
}

// Websocket call through the frontend's own connection
const ws = (msg) => page.evaluate((m) => document.querySelector('home-assistant').hass.callWS(m), msg);

async function deviceId(entityId) {
  const entities = await ws({ type: 'config/entity_registry/list' });
  return entities.find((e) => e.entity_id === entityId)?.device_id;
}

async function submitFlowDialog() {
  await page.getByRole('button', { name: /^(Submit|Next|Finish)$/ }).last().click();
  await settle(2500);
}

await login();

// 1-2: setup (server details, then the features page)
await page.goto(`${HA}/_my_redirect/config_flow_start?domain=blueiris`);
await page.getByRole('button', { name: 'OK', exact: true }).click(); // "Do you want to set up ...?"
await page.getByLabel('Host', { exact: true }).waitFor({ timeout: 30000 });
await page.getByLabel('Host', { exact: true }).fill('192.168.1.60');
await page.getByLabel('Port', { exact: true }).fill('81');
await page.getByLabel('Username', { exact: true }).fill('demo');
await page.getByLabel('Password', { exact: true }).fill('demo');
await shot('01-setup-server-details');
// The made-up server listens on localhost
await page.getByLabel('Host', { exact: true }).fill('127.0.0.1');
await page.getByLabel('Port', { exact: true }).fill(BI_PORT);
await submitFlowDialog();
await shot('02-setup-features');
await submitFlowDialog();
await page.keyboard.press('Escape');
await settle(8000); // first polls: entities, camera images

// 3: dashboard
await page.goto(`${HA}/lovelace/cameras`);
await shot('03-dashboard', { wait: 6000 });

// 4-5: server device, tall window so the whole page fits
await page.setViewportSize({ width: 1400, height: 3050 });
const server = await deviceId('sensor.bi5_connection_health');
await page.goto(`${HA}/config/devices/device/${server}`);
await shot('04-server-device', { wait: 3500 });

// 5: a camera device (controls, sensors, auto reset settings)
await page.setViewportSize({ width: 1400, height: 1750 });
const camera = await deviceId('camera.bi5_side_gate');
await page.goto(`${HA}/config/devices/device/${camera}`);
await shot('05-camera-device', { wait: 3500 });
await page.setViewportSize({ width: 1400, height: 950 });

// 6: the auto reset notification for the camera with no signal
// (first reset 30 s after the problem is seen, on the next 30 s poll)
await page.goto(`${HA}/lovelace/cameras`);
for (let i = 0; i < 60; i++) {
  const attempts = await page.evaluate(() => document.querySelector('home-assistant')
    ?.hass?.states['binary_sensor.bi5_side_gate_problem']?.attributes.auto_reset_attempts);
  if (attempts >= 1) break;
  await settle(2000);
}
await settle(2000);
await page.getByText('Notifications', { exact: true }).first().click();
await shot('06-auto-reset-notification', { wait: 2000 });
await page.keyboard.press('Escape');

// 7: options, page 1
await page.goto(`${HA}/config/integrations/integration/blueiris`);
await settle(3000);
await page.getByRole('button', { name: /Configure/i }).first().click({ force: true });
await shot('07-options', { wait: 3000 });

await browser.close();
