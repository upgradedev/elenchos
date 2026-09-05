// Record the journey a judge would take, against the deployed site and the real run.
//
// Nothing here is a mockup. Every page this drives is public: the demo surface, the GitHub run that
// went green on a commit built to break the rule, and the workflow file at the line the finding
// names. If any of those stops serving, this script fails rather than recording a blank.
//
// Output contract, unchanged from the kit so build-video.py stays generic:
//   capture/production.webm      one continuous recording
//   capture/capture-receipt.json trimLeadSeconds, the hashes, and any browser error seen
//
// Scene ids and their order must match video/narration.json exactly. A mismatch throws here rather
// than drifting silently into a video where the voice describes a different picture.

import { chromium } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = process.env.ELENCHOS_VIDEO_ROOT;
const releaseSha = process.env.ELENCHOS_RELEASE_SHA;
const refutationRunId = process.env.ELENCHOS_REFUTATION_RUN_ID;

if (!root || !/^[a-f0-9]{40}$/u.test(releaseSha ?? "")) {
  throw new Error("The exact video root and release SHA are required.");
}
if (!/^[1-9][0-9]*$/u.test(refutationRunId ?? "")) {
  throw new Error("The exact refutation run id is required.");
}

const SITE = "https://upgradedev.github.io/elenchos/";
const RUN = `https://github.com/upgradedev/elenchos/actions/runs/${refutationRunId}`;
const TARGET =
  "https://github.com/upgradedev/elenchos/blob/main/.github/workflows/canary-target.yml#L34";
const WILD =
  "https://github.com/FaserF/hassio-addons/blob/main/.github/workflows/orchestrator-ci.yaml#L388";

const captureDir = path.join(root, "capture");
mkdirSync(captureDir, { recursive: false });

const timing = JSON.parse(readFileSync(path.join(root, "narration", "timing.json"), "utf8"));
const holds = Object.fromEntries(
  timing.scenes.map((scene) => [scene.id, Number(scene.holdSeconds) * 1000]),
);

const expectedScenes = ["hook", "proof", "deeper", "wild", "model", "surface", "close"];
if (JSON.stringify(timing.scenes.map((s) => s.id)) !== JSON.stringify(expectedScenes)) {
  throw new Error("The narration and the recorded journey describe different scenes.");
}

const browser = await chromium.launch({ args: ["--force-device-scale-factor=1"] });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  recordVideo: { dir: path.join(captureDir, "raw"), size: { width: 1920, height: 1080 } },
});
const page = await context.newPage();
const video = page.video();
if (!video) throw new Error("Playwright did not create a video recorder.");

// Only errors from our own page count. GitHub's pages are not ours to be graded on.
const errors = [];
const onOurSurface = () => page.url().startsWith(SITE);
page.on("pageerror", (error) => {
  if (onOurSurface()) errors.push(`page:${error.name}`);
});
page.on("console", (message) => {
  if (onOurSurface() && message.type() === "error") errors.push("console:error");
});

const captureStarted = Date.now();

// Load once before the clock starts, so the first beat is not narrating a blank page.
await page.goto(SITE, { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(1_500);

const timelineStarted = Date.now();
const hold = async (id) => {
  await page.waitForTimeout(holds[id] ?? 4_000);
};

// hook. The claim, at the top of our own surface.
await hold("hook");

// proof. The real run, on GitHub, green.
await page.goto(RUN, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(2_000);
await hold("proof");

// deeper. The workflow file, at the line the finding names.
await page.goto(TARGET, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(2_000);
await hold("deeper");

// wild. Somebody else's repository, at the line our command reported.
await page.goto(WILD, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(2_000);
await hold("wild");

// model, surface, close. Back on our surface, scrolling the evidence.
await page.goto(SITE, { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(1_000);
await page.evaluate(() => window.scrollTo({ top: 900, behavior: "smooth" }));
await hold("model");

await page.evaluate(() => window.scrollTo({ top: 1800, behavior: "smooth" }));
await hold("surface");

await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
await hold("close");

await context.close();
await browser.close();

const rawPath = await video.path();
const finalPath = path.join(captureDir, "production.webm");
renameSync(rawPath, finalPath);
const bytes = readFileSync(finalPath);

const receipt = {
  schemaVersion: "elenchos.submission-video-capture/v1",
  releaseSha,
  refutationRunId: Number(refutationRunId),
  sceneCount: expectedScenes.length,
  trimLeadSeconds: Math.max(0, (timelineStarted - captureStarted) / 1000),
  timelineSeconds: Number(timing.totalSeconds),
  pageErrors: errors,
  bytes: bytes.length,
  sha256: createHash("sha256").update(bytes).digest("hex"),
};
writeFileSync(
  path.join(captureDir, "capture-receipt.json"),
  `${JSON.stringify(receipt, null, 2)}\n`,
);

if (errors.length !== 0) {
  throw new Error(`The recorded journey emitted ${errors.length} browser errors on our own surface.`);
}
console.log(JSON.stringify(receipt));
