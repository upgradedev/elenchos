// @ts-check
import { test, expect } from '@playwright/test';

test.describe('Elenchos Web Cockpit E2E UAT Testbook', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('UAT-01: Landing Page & Live Hero Proof Verification', async ({ page }) => {
    // Assert title & headline
    await expect(page).toHaveTitle(/Elenchos/);
    await expect(page.locator('h1.hero-title')).toContainText('claim');
    
    // Check that hero proof card loads run url
    const proofCard = page.locator('#hero-proof-card');
    await expect(proofCard).toBeVisible();
    await expect(proofCard).toContainText('The Refutation');
    await expect(proofCard).toContainText('continue-on-error: true');
  });

  test('UAT-02: Side-by-Side Reality Inspector shows both claim and reality', async ({ page }) => {
    const claimPane = page.locator('#split-pane-claim');
    const realityPane = page.locator('#split-pane-reality');
    
    await expect(claimPane).toBeVisible();
    await expect(claimPane).toContainText('Workflow Status: Success');
    
    await expect(realityPane).toBeVisible();
    await expect(realityPane).toContainText('Defect Detected: continue-on-error: true');
  });

  test('UAT-03: Socratic Playground Execution & 4-Stage Trace Flow', async ({ page }) => {
    // Navigate to playground tab
    await page.click('button[data-tab="tab-playground"]');
    await expect(page.locator('#tab-playground')).toHaveClass(/active/);

    // Select preset 2: Narrow SAST scope
    await page.click('button[data-preset="r02_narrow"]');
    await expect(page.locator('#playground-rule-name')).toContainText('Security scan must inspect all source directories');

    // Trigger Socratic Refutation
    const runBtn = page.locator('#btn-run-audit');
    await expect(runBtn).toBeEnabled();
    await runBtn.click();

    // Verify 4 stages complete sequentially
    await expect(page.locator('#step-assess')).toHaveClass(/complete/, { timeout: 4000 });
    await expect(page.locator('#step-provision')).toHaveClass(/complete/, { timeout: 4000 });
    await expect(page.locator('#step-prove')).toHaveClass(/complete/, { timeout: 4000 });
    await expect(page.locator('#step-watch')).toHaveClass(/complete/, { timeout: 4000 });

    // Verify cryptographic output is rendered
    const watchOut = page.locator('#step-watch .stage-output');
    await expect(watchOut).toBeVisible();
    await expect(watchOut).toContainText('content_id:');
  });

  test('UAT-04: Estate Cockpit 200 Repos Filter & Search', async ({ page }) => {
    // Navigate to estate tab
    await page.click('button[data-tab="tab-estate"]');
    await expect(page.locator('#tab-estate')).toHaveClass(/active/);

    // Initial rows check
    const rows = page.locator('#estate-table-body tr');
    await expect(rows).toHaveCount(12);

    // Search for billing
    await page.fill('#estate-search', 'billing');
    await expect(page.locator('#estate-table-body tr')).toHaveCount(1);
    await expect(page.locator('#estate-table-body tr').first()).toContainText('billing-ledger-api');

    // Clear search and filter by False-Green
    await page.fill('#estate-search', '');
    await page.click('span[data-filter="false-green"]');
    const filteredRows = page.locator('#estate-table-body tr');
    const count = await filteredRows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('UAT-05: 60s Guided Spotlight Tour completes all 5 steps', async ({ page }) => {
    // Launch tour
    const tourBtn = page.locator('#btn-start-tour');
    await expect(tourBtn).toBeVisible();
    await tourBtn.click();

    const tourCard = page.locator('#tour-card');
    await expect(tourCard).toBeVisible();
    await expect(page.locator('#tour-step-badge')).toContainText('Step 1 / 5');

    // Step 2
    await page.click('#tour-btn-next');
    await expect(page.locator('#tour-step-badge')).toContainText('Step 2 / 5');

    // Step 3 (Switches to playground tab)
    await page.click('#tour-btn-next');
    await expect(page.locator('#tour-step-badge')).toContainText('Step 3 / 5');
    await expect(page.locator('#tab-playground')).toHaveClass(/active/);

    // Step 4 (Switches to estate tab)
    await page.click('#tour-btn-next');
    await expect(page.locator('#tour-step-badge')).toContainText('Step 4 / 5');
    await expect(page.locator('#tab-estate')).toHaveClass(/active/);

    // Step 5 (Switches to receipts tab)
    await page.click('#tour-btn-next');
    await expect(page.locator('#tour-step-badge')).toContainText('Step 5 / 5');
    await expect(page.locator('#tab-receipts')).toHaveClass(/active/);

    // Finish tour
    await page.click('#tour-btn-next');
    await expect(tourCard).not.toBeVisible();
  });

  test('UAT-06: Cryptographic Attestation Copy and Download', async ({ page }) => {
    await page.click('button[data-tab="tab-receipts"]');
    const copyBtn = page.locator('#btn-copy-jsonld');
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    await expect(copyBtn).toContainText('Copied Attestation!');
  });
});
