(() => {
  let data = null;
  let tutIndex = 0;

  const $ = (sel) => document.querySelector(sel);
  const toast = (msg, isError = false) => {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 4200);
  };

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`#panel-${btn.dataset.tab}`).classList.add("active");
    });
  });

  async function load() {
    const res = await fetch("/api/dashboard");
    data = await res.json();
    render();
  }

  function render() {
    if (!data) return;
    const k = data.kpis;
    $("#kpi-grid").innerHTML = [
      kpi("Pipelines", k.pipelines),
      kpi("Domains", k.domains),
      kpi("Readers ready", `${k.readers_pct}%`, k.readers_pct === 100 ? "good" : "warn"),
      kpi("VRP PASS", k.trust_pass, "good"),
      kpi("VRP FAIL", k.trust_fail, k.trust_fail ? "bad" : ""),
      kpi("Attestations", k.attestations),
      kpi("Deploy ready", k.deploy_ready ? "Yes" : "No", k.deploy_ready ? "good" : "warn"),
    ].join("");

    const d = data.doctor;
    $("#mesh-health").innerHTML = `
      <div class="fact-row"><span>Root</span><span class="mono">${esc(data.root)}</span></div>
      <div class="fact-row"><span>Organization</span><span>${esc(data.organization || "—")}</span></div>
      <div class="fact-row"><span>Domains</span><span>${esc((data.domains || []).join(", ") || "—")}</span></div>
      <div class="fact-row"><span>Readers</span><span>${d.readers_done}/${d.readers_total}</span></div>
      <div class="fact-row"><span>Orchestrator ASL</span><span>${d.has_orchestrator ? "yes" : "no"}</span></div>
      <div class="fact-row"><span>Pending readers</span><span>${
        (d.readers_pending || []).length
          ? d.readers_pending.map((p) => `<code>${esc(p)}</code>`).join("<br>")
          : '<span class="badge pass">all done</span>'
      }</span></div>`;

    const feed = [];
    feed.push(`Loaded dashboard at ${esc(data.generated_at)}`);
    feed.push(`Trust mode: ${esc(data.trust.mode)}`);
    if (data.attestations?.length) {
      feed.push(`${data.attestations.length} PVDM-A attestation(s) found`);
    } else {
      feed.push("No attestations yet — click Attest demo");
    }
    $("#activity").innerHTML = feed.map((t) => `<div class="feed-item">${t}</div>`).join("");

    const rows = data.trust.rows || [];
    const maxRows = Math.max(...rows.map((r) => Number(r.rows) || 1), 1);
    $("#trust-bars").innerHTML = rows
      .map((r) => {
        const h = Math.max(12, Math.round((Number(r.rows) || 1) / maxRows * 110));
        const fail = r.status === "FAIL";
        return `<div class="bar-col"><div class="bar ${fail ? "fail" : ""}" style="height:${h}px"></div><div class="bar-label">${esc(r.domain)}<br>${esc(r.status)}</div></div>`;
      })
      .join("");

    $("#pipe-count").textContent = `${(data.pipelines || []).length} pipelines`;
    $("#pipe-body").innerHTML = (data.pipelines || [])
      .map(
        (p) => `<tr>
          <td>${esc(p.domain)}</td><td>${esc(p.layer)}</td><td>${esc(p.product_id)}</td>
          <td><code>${esc(p.engine)}</code></td>
          <td>${p.has_handler ? '<span class="badge pass">yes</span>' : '<span class="badge warn">no</span>'}</td>
          <td>${p.readers_ready ? '<span class="badge pass">ready</span>' : '<span class="badge fail">TODO</span>'}</td>
          <td><code>${esc(p.path)}</code></td>
        </tr>`
      )
      .join("");

    $("#layer-manifest").textContent = JSON.stringify(data.layer_lambdas || [], null, 2);

    $("#trust-mode").textContent = `Source: ${data.trust.mode}`;
    $("#trust-body").innerHTML = rows
      .map(
        (r) => `<tr>
          <td>${esc(r.domain)}</td>
          <td><span class="badge ${r.status === "PASS" ? "pass" : "fail"}">${esc(r.status)}</span></td>
          <td>${esc(String(r.rows))}</td>
          <td><code>${esc(r.proof_id || "—")}</code></td>
        </tr>`
      )
      .join("");

    const at = data.attestations || [];
    $("#attest-list").innerHTML = at.length
      ? at
          .map(
            (a) => `<div class="feed-item"><strong>${esc(a.decision)}</strong> · ${esc(a.domain_id)} · VRP ${esc(a.vrp_verdict)}<br><code>${esc(a.attestation_id || "")}</code></div>`
          )
          .join("")
      : `<div class="feed-item muted">Run Attest demo to create sealed PVDM-A records.</div>`;

    $("#pvdm-method").textContent = data.pvdm.method;
    $("#pvdm-invariant").textContent = data.pvdm.invariant;
    const copyEl = $("#pvdm-copyright");
    if (copyEl) copyEl.textContent = data.pvdm.copyright || data.pvdm.method;
    $("#phase-grid").innerHTML = (data.pvdm.phases || [])
      .map(
        (p) => `<div class="phase"><div class="id">${esc(p.id)}</div><strong>${esc(p.name)}</strong><p class="muted">${esc(p.detail)}</p><span class="badge pass">${esc(p.status)}</span></div>`
      )
      .join("");

    const dur = data.durable;
    const segPct = Math.round((dur.lambda_timeout_seconds / 900) * 100);
    const workPct = Math.min(100, Math.round((dur.durable_execution_timeout_seconds / 21600) * 100));
    $("#clocks").innerHTML = `
      <div class="clock"><strong>Container clock</strong><div>${dur.lambda_timeout_seconds}s / 900s max</div><div class="meter"><div class="fill" style="width:${segPct}%"></div></div></div>
      <div class="clock"><strong>Workload clock (durable)</strong><div>${dur.durable_execution_timeout_seconds}s total budget</div><div class="meter"><div class="fill" style="width:${workPct}%"></div></div></div>`;
    $("#compute-facts").innerHTML = `
      <div class="fact-row"><span>Durable Lambda</span><span class="badge pass">${dur.enable_durable_execution ? "enabled" : "off"}</span></div>
      <div class="fact-row"><span>MicroVM</span><span>${esc(dur.microvm)}</span></div>
      <div class="fact-row"><span>Compute</span><span>${esc(dur.compute)}</span></div>`;

    renderTutorial();
  }

  function renderTutorial() {
    const steps = data.tutorial || [];
    if (!steps.length) return;
    tutIndex = Math.max(0, Math.min(tutIndex, steps.length - 1));
    const s = steps[tutIndex];
    $("#tut-pos").textContent = `Step ${tutIndex + 1} / ${steps.length}`;
    $("#tutorial-view").innerHTML = `
      <div>
        <img src="${esc(s.gif)}" alt="${esc(s.title)}" onerror="this.onerror=null;this.src='${esc(s.image)}'" />
      </div>
      <div>
        <h3 style="font-family:var(--display);margin:0 0 .5rem">${esc(s.title)}</h3>
        <p class="muted">${esc(s.blurb || "")}</p>
        <div class="feed-item" style="margin-top:.75rem"><strong style="color:var(--accent)">What you do</strong><br>${esc(s.do || "")}</div>
        <p class="cmd">${esc(s.command)}</p>
        <div class="feed-item" style="margin-top:.75rem"><strong style="color:var(--accent-2)">Benefit you get</strong><br>${esc(s.benefit || "")}</div>
        <p class="muted" style="margin-top:1rem"><a href="/walkthrough">Open full demo walkthrough (auto-play) →</a></p>
      </div>`;
  }

  function kpi(label, value, cls = "") {
    return `<div class="kpi"><div class="label">${esc(label)}</div><div class="value ${cls}">${esc(String(value))}</div></div>`;
  }

  function esc(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  $("#btn-refresh").addEventListener("click", () => load().then(() => toast("Dashboard refreshed")));
  $("#tut-prev").addEventListener("click", () => {
    tutIndex -= 1;
    renderTutorial();
  });
  $("#tut-next").addEventListener("click", () => {
    tutIndex += 1;
    renderTutorial();
  });

  async function postAction(url, okMsg) {
    toast("Running…");
    try {
      const res = await fetch(url, { method: "POST" });
      const body = await res.json();
      if (!res.ok || body.ok === false) throw new Error(body.error || "failed");
      await load();
      toast(okMsg);
    } catch (e) {
      toast(String(e.message || e), true);
    }
  }

  $("#btn-demo").addEventListener("click", () =>
    postAction("/api/actions/demo", "PVDM demo finished — trust board updated")
  );
  $("#btn-attest").addEventListener("click", () =>
    postAction("/api/actions/attest-demo", "Attestation created")
  );

  load().catch((e) => toast(String(e), true));
})();
