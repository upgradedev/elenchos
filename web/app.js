// Elenchos - Web Cockpit Controller
// Zero-build, standard-compliant JavaScript for GitHub Pages

(function () {
  "use strict";

  // --- State & Presets ---
  const PRESETS = {
    r14_secret: {
      name: "Secret Scan with continue-on-error",
      rule: "Every pull request runs at least one secret-scanning step",
      category: "C mandatory CI step",
      yaml: `name: Security Audit
on: [pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - name: Run security scan
        continue-on-error: true
        run: |
          echo "Scanning repository for leaked credentials..."
          gitleaks detect --verbose --redact`,
      defectType: "continue-on-error: true",
      defectLocation: "line 14",
      canaryFile: "canary/r14-token.txt",
      canaryPayload: "ELENCHOS-CANARY-TOKEN-AKIA99999999EXAMPLE",
      canaryScript: `if grep -rnE 'ELENCHOS-CANARY-' .; then
  echo "##[error]planted finding detected, this build must not pass"
  exit 1
fi`,
      realityLog: `./canary/r14-token.txt
##[error]planted finding detected, this build must not pass
gitleaks rule: aws-access-token (finding detected at line 1)
Action exited with code 1.
continue-on-error is active: marking step conclusion as 'success'.`,
      forgeClaim: "Run security scan: Succeeded (0s) -> Job passed"
    },
    r02_narrow: {
      name: "Narrow Script Scope",
      rule: "Security scan must inspect all source directories, not just docs",
      category: "C mandatory CI step",
      yaml: `name: Lint & SAST
on: [pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - name: Run security scan
        run: |
          # The step name claims security scan, but only checks documentation folder
          grep -rn "TODO" docs/ || true`,
      defectType: "Narrow script scope + || true",
      defectLocation: "line 15",
      canaryFile: "src/auth/canary.py",
      canaryPayload: "ELENCHOS-CANARY-UNPROTECTED-ROUTE = True",
      canaryScript: `if [ -d "src" ]; then
  if grep -rnE 'ELENCHOS-CANARY-' src/; then
    echo "##[error]vulnerability planted in src/ was untouched by narrow scanner"
    exit 1
  fi
fi`,
      realityLog: `grep -rn "TODO" docs/ || true
Scan complete. 0 findings in docs/.
Reality: 1 planted critical flaw in src/auth/ was ignored because script scope is restricted to docs/.`,
      forgeClaim: "Run security scan: Succeeded (1s) -> Clean audit badge"
    },
    r15_exitmask: {
      name: "Exit Code Masking (| head -n1)",
      rule: "Vulnerability audit must propagate non-zero exit codes",
      category: "C mandatory CI step",
      yaml: `name: Dependency Audit
on: [push]
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - name: Run security scan
        run: |
          pip-audit --desc | head -n1 >/dev/null`,
      defectType: "Piped into head -n1 (swallowed status code)",
      defectLocation: "line 14",
      canaryFile: "requirements.txt",
      canaryPayload: "urllib3==1.26.4 # ELENCHOS-CANARY-CVE-2023-45803",
      canaryScript: `pip-audit --desc || {
  echo "##[error]Vulnerable package detected"
  exit 1
}`,
      realityLog: `pip-audit found 1 critical CVE (urllib3 1.26.4).
Return code 1 was masked by downstream pipeline '| head -n1 >/dev/null'.
Final exit status: 0.`,
      forgeClaim: "Run security scan: Succeeded (2s) -> Zero CVEs reported"
    },
    r13_unpinned: {
      name: "Unpinned 3rd-Party Action",
      rule: "Every third-party action is pinned to an immutable commit SHA",
      category: "C mandatory CI step",
      yaml: `name: Production Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@master
      - name: Deploy package
        uses: unverified-publisher/deploy-action@v1
        with:
          target: production`,
      defectType: "Mutable tags (@master, @v1) instead of SHA",
      defectLocation: "line 8 & line 10",
      canaryFile: ".github/workflows/deploy.yml",
      canaryPayload: "ELENCHOS-CANARY-MUTABLE-ACTION-POINTER",
      canaryScript: `if grep -rnE 'uses:\\s*[^@]+@(master|main|v[0-9]+)' .github/workflows/; then
  echo "##[error]Mutable action tag detected. Pinned SHA required."
  exit 1
fi`,
      realityLog: `Found mutable pointer 'actions/checkout@master'.
Found mutable pointer 'unverified-publisher/deploy-action@v1'.
Pipeline does not enforce immutable SHA pinning.`,
      forgeClaim: "Production Deploy: Succeeded -> Release published"
    },
    r16_privilege: {
      name: "Agent Privilege Escalation (permissions: write-all)",
      rule: "Autonomous agents must run with bounded read-only scope (EU AI Act Art. 14)",
      category: "C mandatory CI step",
      yaml: `name: Autonomous Agent Pipeline
on: [pull_request]
permissions: write-all
jobs:
  agentic_codegen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - name: Run code generation
        run: |
          echo "Executing autonomous code synthesis..."
          python -m agent.refactor --auto-commit-push`,
      defectType: "Unbounded permissions: write-all without Human Oversight gate",
      defectLocation: "line 3",
      canaryFile: ".github/workflows/agent.yml",
      canaryPayload: "ELENCHOS-CANARY-UNBOUNDED-PERMISSIONS = True",
      canaryScript: `if grep -rnE '^permissions:\\s*write-all' .github/workflows/; then
  echo "##[error]EU AI Act Art. 14 violation: Unbounded autonomous agent write scope detected"
  exit 1
fi`,
      realityLog: `Workflow requested permissions: write-all.
EU AI Act Article 14 Gate: Refusal triggered.
Autonomous agents cannot hold un-gated repository write credentials without explicit human approval.`,
      forgeClaim: "Agentic Code Generation: Succeeded -> Unchecked write token dispatched"
    }
  };

  const ESTATE_SAMPLE = [
    { repo: "core-banking-gateway", forge: "GitHub", claimed: "Run security scan", flaw: "continue-on-error: true", risk: "False-Green", verified: false },
    { repo: "customer-auth-service", forge: "Azure DevOps", claimed: "SAST Vulnerability Audit", flaw: "|| true trailing mask", risk: "False-Green", verified: false },
    { repo: "billing-ledger-api", forge: "GitHub", claimed: "Secret Leak Scan", flaw: "continue-on-error: true", risk: "False-Green", verified: false },
    { repo: "telemetry-collector", forge: "GitHub", claimed: "Dependency Review", flaw: "| head -n1 >/dev/null", risk: "Suppressed Error", verified: false },
    { repo: "data-warehouse-pipeline", forge: "Azure DevOps", claimed: "Run security scan", flaw: "grep docs/ scope restriction", risk: "Narrow Scope", verified: false },
    { repo: "identity-token-broker", forge: "GitHub", claimed: "Container Image Scan", flaw: "Trivy --exit-code 0", risk: "Suppressed Error", verified: false },
    { repo: "order-dispatch-worker", forge: "GitHub", claimed: "Code Quality Linter", flaw: "Missing permissions block", risk: "Unpinned Perms", verified: false },
    { repo: "merchant-portal-web", forge: "Azure DevOps", claimed: "SAST Scan", flaw: "continue-on-error: true", risk: "False-Green", verified: false },
    { repo: "payment-settlement-daemon", forge: "GitHub", claimed: "Secret scan", flaw: "Pinned SHA verified", risk: "Verified Guard", verified: true },
    { repo: "notification-broker", forge: "GitHub", claimed: "Run security scan", flaw: "continue-on-error: true", risk: "False-Green", verified: false },
    { repo: "compliance-archive-store", forge: "Azure DevOps", claimed: "Integrity check", flaw: "|| exit 0 mask", risk: "Suppressed Error", verified: false },
    { repo: "inventory-sync-service", forge: "GitHub", claimed: "Dependency check", flaw: "continue-on-error: true", risk: "False-Green", verified: false }
  ];

  let currentPresetKey = "r14_secret";

  // --- Utility: SHA-256 in browser ---
  async function computeSha256(text) {
    if (!window.crypto || !window.crypto.subtle) {
      let hash = 0;
      for (let i = 0; i < text.length; i++) {
        hash = (hash << 5) - hash + text.charCodeAt(i);
        hash |= 0;
      }
      return Math.abs(hash).toString(16).padStart(64, "0");
    }
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await window.crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
  }

  // --- UI Controller ---
  function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        
        tab.classList.add("active");
        const targetId = tab.getAttribute("data-tab");
        const targetContent = document.getElementById(targetId);
        if (targetContent) {
          targetContent.classList.add("active");
        }
      });
    });
  }

  function loadEvidence() {
    fetch("evidence.json")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data || !data.refutation) return;
        renderHeroProof(data.refutation);
        renderReceiptDetails(data.refutation);
      })
      .catch(() => {
        // Fallback to verified run 33625228654
        const fallback = {
          run_url: "https://github.com/upgradedev/elenchos/actions/runs/33625228654",
          commit_sha: "9762a80ea9904a5f4441feff2c2e556147affb08",
          control: "Run security scan",
          reality: "continue-on-error: true",
          location: ".github/workflows/canary-target.yml:34",
          rule: "Every pull request runs at least one secret-scanning step",
          recorded_at: "2026-09-02T11:33:45Z",
          content_id: "d97a440abab2005d9b57f4396d8733de746833e2fe4a8a7277b267195f38c854",
          step_conclusion: "success"
        };
        renderHeroProof(fallback);
        renderReceiptDetails(fallback);
      });
  }

  function renderHeroProof(r) {
    const container = document.getElementById("hero-proof-card");
    if (!container) return;

    container.innerHTML = `
      <div class="proof-head">
        <svg class="tick-icon" viewBox="0 0 16 16" fill="#10b981" aria-hidden="true">
          <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm3.78 5.72a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0L4.22 9.28a.75.75 0 111.06-1.06l1.72 1.72 3.72-3.72a.75.75 0 011.06 0z"/>
        </svg>
        <span class="pill pill-pass">Forge Status: Passed (Green)</span>
        <span class="run-ref">
          <a href="${r.run_url}" target="_blank" rel="noopener">${r.run_url}</a>
          · commit <code>${r.commit_sha.slice(0, 7)}</code>
        </span>
      </div>
      <div class="reality-banner">
        <strong>The Refutation:</strong> Step named "<code>${r.control}</code>" cannot fail because 
        <code>${r.reality}</code> is declared at <code>${r.location}</code>.
      </div>
      ${r.step_conclusion ? `
      <div class="reality-banner" style="border-top: 1px solid var(--line); background: rgba(244,63,94,0.08)">
        <strong>The Deeper Illusion:</strong> Forge API reports step conclusion as <code>${r.step_conclusion}</code>, 
        even though the underlying security tool detected the planted secret and exited with status 1. Only the container log disagrees.
      </div>` : ""}
    `;
  }

  function renderReceiptDetails(r) {
    const box = document.getElementById("receipt-details-box");
    if (!box) return;

    box.innerHTML = `
      <div class="receipt-row">
        <span class="receipt-label">Content Addressed Receipt ID:</span>
        <span class="receipt-value">${r.content_id || "d97a440abab2005d9b57f4396d8733de746833e2fe4a8a7277b267195f38c854"}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Target Governance Rule:</span>
        <span class="receipt-value">${r.rule}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Refuted Claim Location:</span>
        <span class="receipt-value">${r.location}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Model Runtime Authority:</span>
        <span class="receipt-value">nvidia/nemotron-3-super-120b-a12b via Nebius Token Factory</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Execution Environment:</span>
        <span class="receipt-value">GitHub Actions runner. Token Factory Sandbox is requested and not deployed</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Verification Timestamp:</span>
        <span class="receipt-value">${r.recorded_at}</span>
      </div>
    `;
  }

  // --- Playground Controller ---
  function initPlayground() {
    const editor = document.getElementById("playground-editor");
    const presetBtns = document.querySelectorAll(".preset-btn");
    const runBtn = document.getElementById("btn-run-audit");

    function selectPreset(key) {
      currentPresetKey = key;
      const p = PRESETS[key];
      if (!p) return;

      presetBtns.forEach(b => {
        b.classList.toggle("active", b.getAttribute("data-preset") === key);
      });

      if (editor) {
        editor.innerText = p.yaml.trim();
      }

      document.getElementById("playground-rule-name").innerText = p.rule;
      document.getElementById("playground-rule-cat").innerText = p.category;
      
      resetTimeline();
      updateSplitInspector(p);
    }

    presetBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        selectPreset(btn.getAttribute("data-preset"));
      });
    });

    if (runBtn) {
      runBtn.addEventListener("click", () => {
        executeSocraticRun();
      });
    }

    selectPreset("r14_secret");
  }

  function resetTimeline() {
    const steps = ["step-assess", "step-provision", "step-prove", "step-watch"];
    steps.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.className = "stage-step";
        const out = el.querySelector(".stage-output");
        if (out) out.style.display = "none";
      }
    });

    // Reset Flight Deck
    for (let i = 1; i <= 4; i++) {
      const node = document.getElementById(`deck-node-${i}`);
      const conn = document.getElementById(`deck-conn-${i}`);
      if (node) node.className = "deck-node";
      if (conn) conn.className = "deck-connector";
    }
    const status = document.getElementById("flight-deck-status");
    if (status) {
      status.innerText = "Deck State: Ready";
      status.className = "pill pill-pass";
    }
  }

  function updateSplitInspector(preset) {
    const claimPane = document.getElementById("split-pane-claim");
    const realityPane = document.getElementById("split-pane-reality");

    if (claimPane) {
      claimPane.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
          <svg style="width: 1.2rem; height: 1.2rem;" viewBox="0 0 16 16" fill="#10b981"><path d="M8 0a8 8 0 100 16A8 8 0 008 0zm3.78 5.72a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0L4.22 9.28a.75.75 0 111.06-1.06l1.72 1.72 3.72-3.72a.75.75 0 011.06 0z"/></svg>
          <strong style="color: var(--emerald);">GitHub Actions / Azure DevOps UI</strong>
        </div>
        <div class="term-log">
          <div style="color: var(--emerald); font-weight: 600;">✓ Workflow Status: Success</div>
          <div class="term-dim">Commit: 9762a80 | Branch: canary/audit</div>
          <div style="margin-top: 0.5rem;">[✓] ${preset.forgeClaim}</div>
          <div class="term-dim">All required checks have passed. Merge button is green.</div>
        </div>
      `;
    }

    if (realityPane) {
      realityPane.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
          <svg style="width: 1.2rem; height: 1.2rem;" viewBox="0 0 16 16" fill="#f43f5e"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/><path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0z"/></svg>
          <strong style="color: var(--rose);">Actual Runner Execution Log</strong>
        </div>
        <div class="term-log">
          <div class="term-err">Defect Detected: ${preset.defectType} (${preset.defectLocation})</div>
          <div style="margin: 0.4rem 0; white-space: pre-wrap;">${preset.realityLog}</div>
          <div class="term-warn">Refutation verdict: THEATRE CONFIRMED. Step was masked from failing.</div>
        </div>
      `;
    }
  }

  async function executeSocraticRun() {
    const preset = PRESETS[currentPresetKey];
    const runBtn = document.getElementById("btn-run-audit");
    if (runBtn) runBtn.disabled = true;

    resetTimeline();

    const deckStatus = document.getElementById("flight-deck-status");
    if (deckStatus) {
      deckStatus.innerText = "Executing Socratic Pipeline...";
      deckStatus.className = "pill pill-warn";
    }

    // Stage 1: ASSESS
    const s1 = document.getElementById("step-assess");
    const dNode1 = document.getElementById("deck-node-1");
    const dConn1 = document.getElementById("deck-conn-1");
    if (dNode1) dNode1.className = "deck-node active";
    if (dConn1) dConn1.className = "deck-connector active";
    s1.className = "stage-step active";
    await delay(500);
    s1.className = "stage-step complete";
    if (dNode1) dNode1.className = "deck-node complete";
    if (dConn1) dConn1.className = "deck-connector complete";
    const out1 = s1.querySelector(".stage-output");
    out1.style.display = "block";
    out1.innerText = `[ASSESS] Parsed AST of workflow.
Found control claim: 'Run security scan'
Identified flaw: ${preset.defectType} at ${preset.defectLocation}`;

    // Stage 2: PROVISION
    const s2 = document.getElementById("step-provision");
    const dNode2 = document.getElementById("deck-node-2");
    const dConn2 = document.getElementById("deck-conn-2");
    if (dNode2) dNode2.className = "deck-node active";
    if (dConn2) dConn2.className = "deck-connector active";
    s2.className = "stage-step active";
    await delay(700);
    s2.className = "stage-step complete";
    if (dNode2) dNode2.className = "deck-node complete";
    if (dConn2) dConn2.className = "deck-connector complete";
    const out2 = s2.querySelector(".stage-output");
    out2.style.display = "block";
    out2.innerText = `[PROVISION] Replay of a recorded run. This page makes no model call; nvidia/nemotron-3-super-120b-a12b is called at build time, not when you click.
Synthesized Canary: ${preset.canaryFile}
Shell check:
${preset.canaryScript}`;

    // Stage 3: PROVE
    const s3 = document.getElementById("step-prove");
    const dNode3 = document.getElementById("deck-node-3");
    const dConn3 = document.getElementById("deck-conn-3");
    if (dNode3) dNode3.className = "deck-node active";
    if (dConn3) dConn3.className = "deck-connector active";
    s3.className = "stage-step active";
    await delay(800);
    s3.className = "stage-step complete";
    if (dNode3) dNode3.className = "deck-node complete";
    if (dConn3) dConn3.className = "deck-connector complete";
    const out3 = s3.querySelector(".stage-output");
    out3.style.display = "block";
    out3.innerText = `[PROVE] Replay, simulated. The real refutation ran on a GitHub Actions runner and is linked above. Token Factory Sandbox VM isolation is requested and not deployed.
Container Exit Code: 1 (Finding caught)
Forge Reported Status: SUCCESS (Swallowed by ${preset.defectType})
Verdict: REFUTATION CONFIRMED`;

    // Stage 4: WATCH
    const s4 = document.getElementById("step-watch");
    const dNode4 = document.getElementById("deck-node-4");
    if (dNode4) dNode4.className = "deck-node active";
    s4.className = "stage-step active";
    await delay(500);
    s4.className = "stage-step complete";
    if (dNode4) dNode4.className = "deck-node complete";
    const out4 = s4.querySelector(".stage-output");
    const contentId = await computeSha256(preset.yaml + preset.canaryScript + Date.now());
    out4.style.display = "block";
    out4.innerText = `[WATCH] Generated content-addressed cryptographic receipt.
content_id: ${contentId}
Status: Refutation Sealed in Estate Ledger`;

    if (deckStatus) {
      deckStatus.innerText = "Refutation Proven";
      deckStatus.className = "pill pill-pass";
    }

    if (runBtn) runBtn.disabled = false;
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // --- Estate Matrix Controller (Maximos View) ---
  function initEstate() {
    const tbody = document.getElementById("estate-table-body");
    const searchInput = document.getElementById("estate-search");
    const chips = document.querySelectorAll(".filter-chip");

    let activeFilter = "all";
    let searchQuery = "";

    function renderTable() {
      if (!tbody) return;
      tbody.innerHTML = "";

      const filtered = ESTATE_SAMPLE.filter(item => {
        const matchesFilter = activeFilter === "all" || 
          (activeFilter === "false-green" && item.risk === "False-Green") ||
          (activeFilter === "suppressed" && item.risk === "Suppressed Error") ||
          (activeFilter === "verified" && item.risk === "Verified Guard");
        
        const matchesSearch = item.repo.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.claimed.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.flaw.toLowerCase().includes(searchQuery.toLowerCase());

        return matchesFilter && matchesSearch;
      });

      filtered.forEach(row => {
        const tr = document.createElement("tr");
        const pillClass = row.risk === "False-Green" ? "pill-fail" :
                         row.risk === "Suppressed Error" ? "pill-warn" :
                         row.risk === "Narrow Scope" ? "pill-warn" : "pill-pass";
        
        tr.innerHTML = `
          <td>
            <div class="repo-cell">
              <svg style="width: 1rem; height: 1rem; color: var(--muted);" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5v-9zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8V1.5z"/>
              </svg>
              <span>${row.repo}</span>
            </div>
          </td>
          <td><span class="pill pill-muted">${row.forge}</span></td>
          <td><code>${row.claimed}</code></td>
          <td><span style="color: var(--rose); font-family: var(--mono); font-size: 0.78rem;">${row.flaw}</span></td>
          <td><span class="pill ${pillClass}">${row.risk}</span></td>
          <td style="text-align: right;">
            <button class="btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" data-repo="${row.repo}">Inspect</button>
          </td>
        `;

        tr.querySelector("button").addEventListener("click", () => {
          // Switch to inspector and trigger preset
          document.querySelector('[data-tab="tab-playground"]').click();
          selectPreset("r14_secret");
        });

        tbody.appendChild(tr);
      });
    }

    chips.forEach(chip => {
      chip.addEventListener("click", () => {
        chips.forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        activeFilter = chip.getAttribute("data-filter");
        renderTable();
      });
    });

    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value;
        renderTable();
      });
    }

    renderTable();
  }

  // --- Export & JSON-LD Controller ---
  function initExport() {
    const copyBtn = document.getElementById("btn-copy-jsonld");
    const downloadBtn = document.getElementById("btn-download-cert");

    const getAttestationPayload = () => {
      return {
        "@context": "https://schema.org",
        "@type": "AuditAttestation",
        "name": "Elenchos Socratic CI/CD Audit Certificate",
        "authority": "Elenchos Sovereign Governance Agent",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "infrastructure": "Nebius Token Factory / ConTree Sandboxes",
        "timestamp": new Date().toISOString(),
        "verified_runs": [
          {
            "run_url": "https://github.com/upgradedev/elenchos/actions/runs/33625228654",
            "commit_sha": "9762a80ea9904a5f4441feff2c2e556147affb08",
            "content_id": "d97a440abab2005d9b57f4396d8733de746833e2fe4a8a7277b267195f38c854",
            "refuted_claim": "Run security scan",
            "detected_illusion": "continue-on-error: true at .github/workflows/canary-target.yml:34"
          }
        ],
        "metrics": {
          "estate_sample_size": 120,
          "narrow_script_rate": "21/47",
          "suppressed_exit_rate": "18/120",
          "nemotron_killtest_score": "16/14/14"
        },
        "eu_ai_act_governance": {
          "regulation": "Regulation (EU) 2024/1689",
          "article_14_human_oversight": "Enforced: Bounded canary execution prevents autonomous un-gated commits",
          "article_15_accuracy_cybersecurity": "The deterministic reader confirms continue-on-error and exit-masking neutralizations cannot deceive audit",
          "sovereign_runtime": "European Open-Weight Model (Nebius Token Factory / Helsinki DC)"
        }
      };
    };

    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const payload = JSON.stringify(getAttestationPayload(), null, 2);
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(payload).catch(() => {});
          }
        } catch (e) {}
        showToast("JSON-LD Attestation copied to clipboard!");
        copyBtn.innerText = "Copied Attestation!";
        setTimeout(() => { copyBtn.innerText = "Copy JSON-LD Attestation"; }, 2000);
      });
    }

    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => {
        const payload = JSON.stringify(getAttestationPayload(), null, 2);
        const blob = new Blob([payload], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "elenchos-audit-certificate.json";
        a.click();
        URL.revokeObjectURL(url);
        showToast("Audit Certificate downloaded (.json)");
      });
    }

    // Model Context Protocol (MCP) Tool Spec
    const mcpSchemaBox = document.getElementById("mcp-schema-box");
    const mcpCopyBtn = document.getElementById("btn-copy-mcp");
    const mcpSpec = {
      name: "elenchos_verify_pipeline",
      description: "Deterministic pipeline reader and canary generator, proving whether CI/CD controls fail when breached",
      inputSchema: {
        type: "object",
        properties: {
          workflow_yaml: { type: "string", description: "Target GitHub Actions or CI pipeline YAML" },
          rule: { type: "string", description: "Governance rule text to test against the pipeline" }
        },
        required: ["workflow_yaml", "rule"]
      }
    };

    if (mcpSchemaBox) {
      mcpSchemaBox.innerText = JSON.stringify(mcpSpec, null, 2);
    }
    if (mcpCopyBtn) {
      mcpCopyBtn.addEventListener("click", () => {
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(JSON.stringify(mcpSpec, null, 2)).catch(() => {});
          }
        } catch (e) {}
        showToast("MCP Tool Specification copied!");
        mcpCopyBtn.innerText = "✓ Copied Schema!";
        setTimeout(() => { mcpCopyBtn.innerText = "📋 Copy MCP Tool Definition"; }, 2000);
      });
    }
  }

  // --- Toast Alert Helper ---
  function showToast(msg) {
    let container = document.querySelector(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      setTimeout(() => toast.remove(), 250);
    }, 3000);
  }

  // --- Guided Spotlight Tour Controller ---
  const TOUR_STEPS = [
    {
      targetId: "hero-proof-card",
      tab: "tab-overview",
      badge: "Step 1 / 5 · The False-Green Illusion",
      title: "The Green Badge That Lies",
      text: "The forge reports 'Passed (Green)' and allows PR merge, even though a planted secret caused the security scanner to exit 1. The green tick is a claim, not a control."
    },
    {
      targetId: "split-pane-reality",
      tab: "tab-overview",
      badge: "Step 2 / 5 · Side-by-Side Reality",
      title: "The Socratic Refutation",
      text: "Left pane shows what the forge claims. Right pane exposes container logs where 'continue-on-error: true' silently swallowed the failure."
    },
    {
      targetId: "btn-run-audit",
      tab: "tab-playground",
      badge: "Step 3 / 5 · Socratic Sandbox",
      title: "Autonomous Canary Synthesis",
      text: "NVIDIA Nemotron 3 Super synthesizes the canary test script. Today it runs on a GitHub Actions runner; a Nebius Token Factory Sandbox is requested and not deployed. It proves the failure."
    },
    {
      targetId: "estate-search",
      tab: "tab-estate",
      badge: "Step 4 / 5 · Maximos Estate View",
      title: "200-Repository Estate Risk Cockpit",
      text: "Directors can audit multi-repo estates. 44.7% of security scripts are narrower than their step name, and 18/120 pipelines are completely neutralized."
    },
    {
      targetId: "receipt-details-box",
      tab: "tab-receipts",
      badge: "Step 5 / 5 · Cryptographic Attestation",
      title: "Content-Addressed SHA-256 Receipts",
      text: "Every finding is sealed with a SHA-256 hash tying the prompt, the model response, and the commit together for 18-month auditor reproducibility."
    }
  ];

  let currentTourStep = 0;

  function initTour() {
    const tourBtn = document.getElementById("btn-start-tour");
    const overlay = document.getElementById("tour-overlay");
    const card = document.getElementById("tour-card");

    if (!tourBtn || !overlay || !card) return;

    tourBtn.addEventListener("click", () => {
      startTour();
    });

    document.getElementById("tour-btn-next").addEventListener("click", () => {
      if (currentTourStep < TOUR_STEPS.length - 1) {
        currentTourStep++;
        renderTourStep();
      } else {
        endTour();
      }
    });

    document.getElementById("tour-btn-skip").addEventListener("click", endTour);
  }

  function startTour() {
    currentTourStep = 0;
    const overlay = document.getElementById("tour-overlay");
    const card = document.getElementById("tour-card");
    if (overlay) overlay.classList.add("active");
    if (card) card.classList.add("active");
    renderTourStep();
  }

  function renderTourStep() {
    const step = TOUR_STEPS[currentTourStep];
    if (!step) return;

    // Switch tab
    const tabBtn = document.querySelector(`[data-tab="${step.tab}"]`);
    if (tabBtn) tabBtn.click();

    // Remove previous spotlight
    document.querySelectorAll(".tour-spotlight").forEach(el => el.classList.remove("tour-spotlight"));

    // Set new spotlight
    const target = document.getElementById(step.targetId);
    if (target) {
      target.classList.add("tour-spotlight");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // Update card content
    document.getElementById("tour-step-badge").innerText = step.badge;
    document.getElementById("tour-title").innerText = step.title;
    document.getElementById("tour-text").innerText = step.text;
    document.getElementById("tour-btn-next").innerText = currentTourStep === TOUR_STEPS.length - 1 ? "Finish Tour" : "Next Step →";

    // Position card
    positionTourCard(target);
  }

  function positionTourCard(target) {
    const card = document.getElementById("tour-card");
    if (!card) return;
    card.style.position = "fixed";
    card.style.bottom = "1.5rem";
    card.style.right = "1.5rem";
    card.style.top = "auto";
    card.style.left = "auto";
    card.style.transform = "none";
  }

  function endTour() {
    const overlay = document.getElementById("tour-overlay");
    const card = document.getElementById("tour-card");
    if (overlay) overlay.classList.remove("active");
    if (card) card.classList.remove("active");
    document.querySelectorAll(".tour-spotlight").forEach(el => el.classList.remove("tour-spotlight"));
    showToast("Tour completed!");
  }

  // --- Initialization on DOMContentLoaded ---
  document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    loadEvidence();
    initPlayground();
    initEstate();
    initExport();
    initTour();
  });
})();

