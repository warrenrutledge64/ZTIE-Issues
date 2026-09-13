/*
 * ZTIE Story 4.3 (RD-043) — real-time dashboard render client.
 *
 * RENDER ONLY over the Story 4.2 `dashboard.contract.v1` payload. It re-derives
 * NOTHING, calls no model, and enforces NOTHING (the human accept/reject ACTION +
 * routing is Story 4.4/4.6/4.7). It surfaces the 3.5 `recommended_verdict` + the pending
 * human decision AS ADVISORY (never an effective decision). It reads the payload from the
 * Story 4.2 hub_dashboard Lambda through the GET API front:
 *   GET {apiBaseUrl}dashboard            -> view=fleet   (optional ?limit=)
 *   GET {apiBaseUrl}status/{intake_id}   -> view=intake
 *
 * SECURITY: every value pulled from the (derived) payload is inserted via textContent or
 * an explicit escape — NEVER via innerHTML of raw values — so there is no stored XSS in
 * the Hub even though the payload is derived from untrusted input (RD-013: the render
 * escapes crossed data).
 *
 * TENANT-AWARE (RD-028): reads carry the configured subscriber_id (per-subscriber,
 * org-shared) so a later per-subscriber partitioning needs no render change.
 *
 * The API uses IAM/SigV4 auth. A browser Cognito login is a deferred follow-on; when the
 * dashboard is opened without signed credentials the fetch will fail auth, and the client
 * renders a clear, non-alarming notice explaining the read path (so the static render is
 * still demonstrably correct and the live validation is driven via awscurl/SigV4, exactly
 * like the intake API).
 */

(function () {
  "use strict";

  var CONFIG = window.ZTIE_CONFIG || {
    apiBaseUrl: "",
    subscriberId: "ztie-tenant-zero",
    contractVersion: "1.0",
  };

  // ---- Small pure helpers (safe DOM construction) --------------------------

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function tierClass(tier) {
    var allowed = ["unknown", "low", "medium", "high", "critical"];
    var t = allowed.indexOf(tier) >= 0 ? tier : "unknown";
    return "tier tier-" + t;
  }

  function tierPill(tier) {
    var pill = el("span", tierClass(tier), tier || "unknown");
    return pill;
  }

  function kv(k, v) {
    var row = el("div", "kv");
    row.appendChild(el("span", "k", k));
    row.appendChild(
      el("span", "v", v === undefined || v === null ? "\u2014" : v),
    );
    return row;
  }

  // ---- API access ----------------------------------------------------------

  function apiUrl(pathAndQuery) {
    var base = CONFIG.apiBaseUrl || "";
    // apiBaseUrl already ends with "/". Append the resource path (no leading slash).
    return base + pathAndQuery;
  }

  function subscriberQuery() {
    // RD-028: carry the subscriber scope on every read (org-shared, per-subscriber).
    return "subscriber_id=" + encodeURIComponent(CONFIG.subscriberId || "");
  }

  function fetchJson(url) {
    return fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      // credentials omitted: IAM/SigV4 signing is not done from the browser in this
      // story (deferred Cognito front). A signed proxy or awscurl drives live validation.
    }).then(function (resp) {
      return resp.text().then(function (body) {
        var data = null;
        try {
          data = body ? JSON.parse(body) : null;
        } catch (e) {
          data = null;
        }
        return { ok: resp.ok, status: resp.status, data: data, raw: body };
      });
    });
  }

  // ---- State ---------------------------------------------------------------

  var fleetEl = document.getElementById("fleet-view");
  var intakeEl = document.getElementById("intake-view");
  var refreshState = document.getElementById("refresh-state");

  function setRefreshState(text, kind) {
    refreshState.textContent = text;
    refreshState.className = "badge " + (kind || "badge-muted");
  }

  function showError(container, status, message) {
    var box = el("div", "error-box");
    box.appendChild(el("strong", null, "Could not load data"));
    box.appendChild(document.createTextNode(" "));
    box.appendChild(
      document.createTextNode(
        "(HTTP " +
          status +
          "). " +
          (message || "See the read-path note below."),
      ),
    );
    var note = el(
      "p",
      "muted",
      "The dashboard read API uses IAM/SigV4 auth. A browser Cognito login is a " +
        "deferred follow-on; drive the live validation via awscurl (SigV4) against " +
        "GET /dashboard and GET /status/{intake_id}.",
    );
    box.appendChild(note);
    container.appendChild(box);
  }

  // ---- Fleet view ----------------------------------------------------------

  function renderMetrics(metrics) {
    var host = document.getElementById("metrics");
    clear(host);
    if (!metrics) return;

    host.appendChild(countsCard("By stage", metrics.by_stage));
    host.appendChild(
      countsCard(
        "By recommendation (advisory)",
        metrics.by_recommended_verdict,
      ),
    );
    host.appendChild(countsCard("By threat tier", metrics.by_threat_tier));
    host.appendChild(
      healthCard("Operational health", [
        ["AMI build", metrics.ami_build_health],
        ["Sensors", metrics.sensor_status],
        ["Cost", metrics.cost],
      ]),
    );
  }

  function countsCard(title, obj) {
    var card = el("div", "metric-card");
    card.appendChild(el("h4", null, title));
    if (obj && typeof obj === "object") {
      Object.keys(obj).forEach(function (k) {
        var line = el("div", "metric-line");
        line.appendChild(el("span", "k", k));
        line.appendChild(el("span", "vv", obj[k]));
        card.appendChild(line);
      });
    } else {
      card.appendChild(el("div", "placeholder", "no data"));
    }
    return card;
  }

  function healthCard(title, entries) {
    var card = el("div", "metric-card");
    card.appendChild(el("h4", null, title));
    entries.forEach(function (pair) {
      var label = pair[0];
      var block = pair[1] || {};
      var status = block.status || "not_wired";
      var line = el("div", "metric-line");
      line.appendChild(el("span", "k", label));
      var val = el("span", "health-" + status, humanHealth(status));
      if (block.detail) val.title = block.detail;
      line.appendChild(val);
      card.appendChild(line);
    });
    return card;
  }

  function humanHealth(status) {
    // A stubbed `not_wired` source is the CORRECT state (its data source is a deferred
    // follow-on), NOT an error — render it as "not available yet".
    if (status === "not_wired") return "not available yet";
    return status;
  }

  function renderOpsCards(payload) {
    var metrics = (payload.fleet && payload.fleet.metrics) || {};
    var count = (payload.fleet && payload.fleet.returned_count) || 0;

    var activity = document.getElementById("ops-activity-body");
    clear(activity);
    activity.appendChild(
      el(
        "div",
        null,
        count +
          " intake" +
          (count === 1 ? "" : "s") +
          " in the current window.",
      ),
    );
    var running = (metrics.by_stage && countRunning(metrics.by_stage)) || 0;
    activity.appendChild(
      el("div", "muted", running + " still in flight (pre-recommendation)."),
    );

    // Restore-point health: 4.2 surfaces it under the operational-health blocks; when
    // its source is deferred it arrives not_wired. Render honestly as a first-class card.
    var restore = document.getElementById("ops-restore-body");
    clear(restore);
    restore.appendChild(
      el(
        "div",
        "placeholder",
        "Restore-point status/health source is a deferred follow-on (not available yet).",
      ),
    );

    // Port <-> MITRE view (PROJECT_PLAN §7): its data is not carried by the 4.2 payload
    // yet — render an explicit placeholder pending its deferred data source.
    var pm = document.getElementById("ops-portmitre-body");
    clear(pm);
    pm.appendChild(
      el(
        "div",
        "placeholder",
        "Port-to-MITRE detail is not in the dashboard payload yet (deferred data source).",
      ),
    );
  }

  function countRunning(byStage) {
    var running = 0;
    [
      "received",
      "classified",
      "collected",
      "correlated",
      "scored",
      "assessed",
    ].forEach(function (s) {
      running += Number(byStage[s] || 0);
    });
    return running;
  }

  function recSpan(rv) {
    if (!rv) return el("span", "muted", "\u2014");
    return el("span", "rec-" + rv, rv);
  }

  function renderFleet(payload) {
    intakeEl.classList.add("hidden");
    fleetEl.classList.remove("hidden");

    var fleet = payload.fleet || {};
    renderMetrics(fleet.metrics);
    renderOpsCards(payload);

    var tbody = document.getElementById("fleet-rows");
    clear(tbody);
    var rows = fleet.intakes || [];
    var empty = document.getElementById("fleet-empty");
    var trunc = document.getElementById("fleet-truncated");
    var count = document.getElementById("fleet-count");

    count.textContent =
      "showing " + (fleet.returned_count || rows.length) + " intake(s)";

    if (rows.length === 0) {
      empty.classList.remove("hidden");
    } else {
      empty.classList.add("hidden");
    }

    if (fleet.truncated) {
      trunc.textContent =
        "More recent intakes exist than shown (window capped). Showing the newest.";
      trunc.classList.remove("hidden");
    } else {
      trunc.classList.add("hidden");
    }

    rows.forEach(function (row) {
      var tr = el("tr", "row-" + tierClass(row.threat_tier).split(" ")[1]);
      var tdTier = el("td");
      tdTier.appendChild(tierPill(row.threat_tier));
      tr.appendChild(tdTier);

      var tdId = el("td");
      tdId.appendChild(el("span", "mono", row.intake_id));
      tr.appendChild(tdId);

      tr.appendChild(el("td", null, row.overall_stage || "\u2014"));

      var tdRec = el("td");
      tdRec.appendChild(recSpan(row.recommended_verdict));
      tr.appendChild(tdRec);

      tr.appendChild(el("td", null, row.decision || "pending"));
      tr.appendChild(el("td", "muted", row.received_at || "\u2014"));

      tr.addEventListener("click", function () {
        loadIntake(row.intake_id);
      });
      tbody.appendChild(tr);
    });
  }

  // ---- Per-intake detail ---------------------------------------------------

  function scoreBar(label, laneObj) {
    // A lane score is an object { status, score? } (status.contract.v1). `score` is
    // present only when status === "scored"; otherwise show the honest status.
    var lane = laneObj || {};
    var hasScore = typeof lane.score === "number";
    var display = hasScore ? lane.score : lane.status || "\u2014";

    var wrap = el("div", "score-bar-wrap");
    var lab = el("div", "score-label");
    lab.appendChild(el("span", null, label));
    lab.appendChild(el("span", null, display));
    wrap.appendChild(lab);
    var track = el("div", "score-track");
    var fill = el("div", "score-fill");
    var v = hasScore ? Math.max(0, Math.min(100, Number(lane.score))) : 0;
    fill.style.width = v + "%";
    fill.style.background = hasScore ? scoreColor(v) : "var(--tier-unknown)";
    track.appendChild(fill);
    wrap.appendChild(track);
    return wrap;
  }

  function scoreColor(v) {
    // Graduated: reuse the threat-band cut lines for a consistent color language.
    if (v >= 75) return "var(--tier-critical)";
    if (v >= 55) return "var(--tier-high)";
    if (v >= 30) return "var(--tier-medium)";
    return "var(--tier-low)";
  }

  function renderIntake(payload) {
    fleetEl.classList.add("hidden");
    intakeEl.classList.remove("hidden");

    var body = document.getElementById("intake-body");
    clear(body);

    var intake = payload.intake || {};
    var status = intake.status || {};
    var threat = intake.threat || {};
    var action = intake.action || {};

    var grid = el("div", "detail-grid");

    // Identity + stage
    var idCard = el("div", "detail-card");
    idCard.appendChild(el("h3", null, "Intake"));
    idCard.appendChild(kv("intake_id", action.intake_id || status.intake_id));
    idCard.appendChild(kv("sha256", action.sha256 || status.sha256));
    idCard.appendChild(kv("overall stage", status.overall_stage));
    idCard.appendChild(kv("status", status.status));
    idCard.appendChild(kv("received", status.received_at));
    grid.appendChild(idCard);

    // Threat band
    var threatCard = el("div", "detail-card");
    threatCard.appendChild(el("h3", null, "Threat (display band)"));
    var tierRow = el("div", "kv");
    tierRow.appendChild(el("span", "k", "tier"));
    var tierVal = el("span", "v");
    tierVal.appendChild(tierPill(threat.tier));
    tierRow.appendChild(tierVal);
    threatCard.appendChild(tierRow);
    threatCard.appendChild(kv("combined score", threat.combined_score));
    threatCard.appendChild(
      kv("highest gap severity", threat.highest_gap_severity),
    );
    threatCard.appendChild(
      kv("contradiction present", String(!!threat.contradiction_present)),
    );
    threatCard.appendChild(
      el(
        "p",
        "muted",
        "A display band derived from the evidence \u2014 never a verdict.",
      ),
    );
    grid.appendChild(threatCard);

    // Scores (context, echoed — never re-blended)
    var scores = status.scores;
    if (scores) {
      var scoreCard = el("div", "detail-card");
      scoreCard.appendChild(el("h3", null, "Risk scores (context)"));
      scoreCard.appendChild(scoreBar("static", scores.static));
      scoreCard.appendChild(scoreBar("dynamic", scores.dynamic));
      scoreCard.appendChild(scoreBar("combined", scores.combined));
      scoreCard.appendChild(
        el(
          "p",
          "muted",
          "Echoed as context; the combined score is its own assessment.",
        ),
      );
      grid.appendChild(scoreCard);
    }

    // Findings summary
    var fs = status.findings_summary;
    if (fs) {
      var fsCard = el("div", "detail-card");
      fsCard.appendChild(el("h3", null, "Findings summary"));
      fsCard.appendChild(kv("status", fs.status));
      fsCard.appendChild(kv("findings", fs.finding_count));
      fsCard.appendChild(
        kv("candidate false positives", fs.candidate_false_positive_count),
      );
      fsCard.appendChild(kv("gaps", fs.gap_count));
      fsCard.appendChild(kv("remediations", fs.remediation_count));
      fsCard.appendChild(kv("highest gap severity", fs.highest_gap_severity));
      fsCard.appendChild(
        kv("contradiction present", String(!!fs.contradiction_present)),
      );
      grid.appendChild(fsCard);
    }

    // Pipeline stages presence
    if (status.stages && typeof status.stages === "object") {
      var stagesCard = el("div", "detail-card");
      stagesCard.appendChild(el("h3", null, "Pipeline stages"));
      var chips = el("div");
      Object.keys(status.stages).forEach(function (name) {
        var present = status.stages[name] === "present";
        var chip = el(
          "span",
          "stage-chip " + (present ? "stage-present" : "stage-absent"),
          name + (present ? " \u2713" : ""),
        );
        chips.appendChild(chip);
      });
      stagesCard.appendChild(chips);
      grid.appendChild(stagesCard);
    }

    body.appendChild(grid);

    // The human APPROVE/REJECT control SURFACE (advisory recommendation + pending
    // decision). RD-040: the recommendation is ADVISORY and NEVER acted upon here — the
    // buttons are a surface only (the action + routing is Story 4.4/4.6/4.7), so they are
    // present but DISABLED with an explicit note.
    var rec = status.recommendation || {};
    var actionCard = el("div", "detail-card action-card");
    actionCard.appendChild(el("h3", null, "Human decision gate"));
    var recRow = el("div", "kv");
    recRow.appendChild(el("span", "k", "recommended verdict (advisory)"));
    var recVal = el("span", "v");
    recVal.appendChild(
      recSpan(rec.recommended_verdict || action.recommended_verdict),
    );
    recRow.appendChild(recVal);
    actionCard.appendChild(recRow);
    actionCard.appendChild(
      kv("recommendation status", rec.status || action.recommendation_status),
    );
    actionCard.appendChild(kv("human decision", action.decision || "pending"));
    if (rec.summary) actionCard.appendChild(kv("summary", rec.summary));
    actionCard.appendChild(
      el(
        "p",
        "action-note",
        "Advisory only \u2014 never acted upon automatically. A human selects PASS or " +
          "REJECT at the gate (that action is Story 4.4; the controls below are a " +
          "surface only in this release).",
      ),
    );
    var buttons = el("div", "action-buttons");
    var approve = el("button", "btn btn-approve", "Approve \u2192 PDE");
    var reject = el("button", "btn btn-reject", "Reject \u2192 destroy");
    approve.setAttribute("disabled", "disabled");
    reject.setAttribute("disabled", "disabled");
    approve.title = "The accept action is Story 4.4 (not wired in 4.3).";
    reject.title = "The reject action is Story 4.7 (not wired in 4.3).";
    buttons.appendChild(approve);
    buttons.appendChild(reject);
    actionCard.appendChild(buttons);
    body.appendChild(actionCard);
  }

  // ---- Loaders -------------------------------------------------------------

  function loadFleet() {
    setRefreshState("loading\u2026", "badge-muted");
    var container = document.getElementById("fleet-view");
    // clear any stale error boxes
    Array.prototype.slice
      .call(container.querySelectorAll(".error-box"))
      .forEach(function (n) {
        n.parentNode.removeChild(n);
      });
    return fetchJson(apiUrl("dashboard?" + subscriberQuery()))
      .then(function (res) {
        if (!res.ok || !res.data || res.data.error) {
          var msg = res.data && res.data.error ? res.data.error.message : "";
          showError(container, res.status, msg);
          setRefreshState("error", "badge-muted");
          return;
        }
        renderFleet(res.data);
        setRefreshState(
          "updated " + new Date().toLocaleTimeString(),
          "badge-muted",
        );
      })
      .catch(function () {
        showError(
          container,
          "network",
          "The dashboard could not reach the read API.",
        );
        setRefreshState("error", "badge-muted");
      });
  }

  function loadIntake(intakeId) {
    setRefreshState("loading\u2026", "badge-muted");
    var container = document.getElementById("intake-view");
    intakeEl.classList.remove("hidden");
    fleetEl.classList.add("hidden");
    var body = document.getElementById("intake-body");
    clear(body);
    return fetchJson(
      apiUrl(
        "status/" + encodeURIComponent(intakeId) + "?" + subscriberQuery(),
      ),
    )
      .then(function (res) {
        if (!res.ok || !res.data || res.data.error) {
          var msg = res.data && res.data.error ? res.data.error.message : "";
          showError(body, res.status, msg);
          setRefreshState("error", "badge-muted");
          return;
        }
        renderIntake(res.data);
        setRefreshState(
          "updated " + new Date().toLocaleTimeString(),
          "badge-muted",
        );
      })
      .catch(function () {
        showError(
          body,
          "network",
          "The dashboard could not reach the read API.",
        );
        setRefreshState("error", "badge-muted");
      });
  }

  // ---- Wire up -------------------------------------------------------------

  function init() {
    var badge = document.getElementById("subscriber-badge");
    badge.textContent = "subscriber: " + (CONFIG.subscriberId || "\u2014");

    document.getElementById("footer-note").textContent =
      "ZTIE dashboard render (Story 4.3) \u2014 renders dashboard.contract.v1 " +
      (CONFIG.contractVersion || "1.0") +
      ". Read-only; recommendations advisory.";

    document
      .getElementById("refresh-btn")
      .addEventListener("click", function () {
        if (!intakeEl.classList.contains("hidden")) {
          // stay on the fleet on refresh from detail
          loadFleet();
        } else {
          loadFleet();
        }
      });

    document
      .getElementById("close-intake")
      .addEventListener("click", function () {
        loadFleet();
      });

    loadFleet();
  }

  // Expose the pure-ish render entry points for testing in a DOM-less checker is not
  // needed; keep the module self-contained.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
