(() => {
  /** @typedef {{ id: string, domain_id: string, layers: Set<string> }} DesignDomain */

  const $ = (sel) => document.querySelector(sel);
  /** @type {DesignDomain[]} */
  let domains = [];
  let dragKind = null;
  let selectedDomainId = null;

  const toast = (msg, isError = false) => {
    const el = $("#toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("error", !!isError);
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 4200);
  };

  function status(msg, isError = false) {
    const el = $("#design-status");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("err", !!isError);
  }

  function setLiveBadge(text, kind = "pass") {
    const el = $("#design-live-badge");
    if (!el) return;
    el.textContent = text;
    el.className = `badge ${kind}`;
  }

  function defaultLayer(layer, domainId) {
    const upstream =
      layer === "silver" ? "bronze" : layer === "gold" ? "silver" : null;
    const engine = layer === "bronze" ? "pyarrow" : "pyspark";
    return {
      target_table: `${domainId}_${layer}${layer === "gold" ? "_daily" : ""}`,
      source_namespace: `${layer}_${domainId}`,
      upstream_layer: upstream,
      description: `${layer} layer for ${domainId}`,
      identity_fields: layer === "bronze" ? ["id", "line_id"] : ["id"],
      content_fields:
        layer === "bronze"
          ? ["id", "line_id", "raw_json", "ingested_at"]
          : ["id", "payload_hash", "updated_at"],
      runtime: {
        engine,
        lambda_memory_mb: engine === "pyspark" ? 10240 : 3008,
        ...(engine === "pyspark" ? { package_extras: "spark" } : {}),
      },
      transforms: layer === "bronze" ? ["landing_copy"] : ["curate"],
      max_chunk_records: 5000,
      auto_repair: layer !== "bronze",
      ...(layer === "gold"
        ? {
            consumer_slas: [
              {
                consumer_id: "analytics-team",
                target_table: `${domainId}_gold_daily`,
                max_freshness_minutes: 60,
                min_completeness_pct: 99.0,
                required_columns: ["id"],
                enforcement: "vrp_backed",
              },
            ],
          }
        : {}),
    };
  }

  function splitIds(raw) {
    return String(raw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function radioValue(name, fallback) {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el?.value || fallback;
  }

  function syncAccountFields() {
    const multi = radioValue("design-acct-mode", "single") === "multi";
    document.querySelectorAll(".design-multi-only").forEach((el) => {
      el.classList.toggle("is-hidden", !multi);
    });
    if (!multi) {
      const p = $("#design-acct-producer")?.value || "111111111111";
      if ($("#design-acct-steward")) $("#design-acct-steward").value = p;
      if ($("#design-acct-publisher")) $("#design-acct-publisher").value = p;
    }
  }

  function syncVpcFields() {
    const mode = radioValue("design-vpc-mode", "none");
    document.querySelectorAll(".design-vpc-existing").forEach((el) => {
      el.classList.toggle("is-hidden", mode !== "existing");
    });
    document.querySelectorAll(".design-vpc-create").forEach((el) => {
      el.classList.toggle("is-hidden", mode !== "create");
    });
    const hint = $("#design-aws-hint");
    if (!hint) return;
    if (mode === "existing") {
      hint.innerHTML =
        "Attach writers to <strong>your</strong> private subnets + SG. Values go into <code>mesh.yaml</code> and <code>terraform.contract.txt</code> as <code>vpc_mode=existing</code>.";
    } else if (mode === "create") {
      hint.innerHTML =
        "Terraform module <code>vpc-lambda</code> will create a private VPC + subnets + Lambda SG (<code>vpc_mode=create</code>). IAM still auto-created.";
    } else {
      hint.innerHTML =
        "Default = <strong>no VPC</strong> (AWS-managed Lambda network). This is <em>not</em> your account default VPC. Choose existing or create only for private ENIs.";
    }
  }

  function buildContract() {
    const org = ($("#design-org")?.value || "xyz-org").trim();
    const prefix = ($("#design-prefix")?.value || "xyz").trim();
    const region = ($("#design-region")?.value || "us-east-2").trim();
    const acctMode = radioValue("design-acct-mode", "single");
    let producer = ($("#design-acct-producer")?.value || "111111111111").trim();
    let steward = ($("#design-acct-steward")?.value || producer).trim();
    let publisher = ($("#design-acct-publisher")?.value || producer).trim();
    if (acctMode === "single") {
      steward = producer;
      publisher = producer;
    }
    const vpcMode = radioValue("design-vpc-mode", "none");
    let networking;
    if (vpcMode === "existing") {
      networking = {
        mode: "existing",
        vpc_id: ($("#design-vpc-id")?.value || "").trim() || null,
        subnet_ids: splitIds($("#design-subnets")?.value),
        security_group_ids: splitIds($("#design-sgs")?.value),
        note: "vpc_mode=existing — set lambda_subnet_ids / lambda_security_group_ids in terraform.tfvars",
      };
    } else if (vpcMode === "create") {
      networking = {
        mode: "create",
        cidr_block: ($("#design-vpc-cidr")?.value || "10.80.0.0/16").trim(),
        az_count: Number($("#design-vpc-azs")?.value || 2),
        note: "vpc_mode=create — Terraform module vpc-lambda creates private VPC + Lambda SG",
      };
    } else {
      networking = {
        mode: "none",
        note: "vpc_mode=none — no VPC attachment (AWS-managed network, not account default VPC)",
      };
    }
    return {
      apiVersion: "sdm/v1",
      kind: "MedallionMesh",
      metadata: {
        organization: org,
        description:
          "Mesh designed in control UI. Compile with serverless-data-mesh apply.",
      },
      spec: {
        name_prefix: prefix,
        aws_region: region,
        account_topology: acctMode,
        accounts: {
          producer,
          steward,
          publisher,
        },
        networking,
        domains: domains.map((d) => {
          const layers = {};
          for (const layer of ["bronze", "silver", "gold"]) {
            if (d.layers.has(layer)) {
              layers[layer] = defaultLayer(layer, d.domain_id);
            }
          }
          return {
            domain_id: d.domain_id,
            owner_team: `${d.domain_id}-platform`,
            description: `${d.domain_id} medallion product`,
            schedule_cron: "0 2 * * *",
            layers,
          };
        }),
      },
    };
  }

  function refreshJson() {
    const pre = $("#design-json");
    if (!pre) return;
    pre.textContent = JSON.stringify(buildContract(), null, 2);
    const empty = $("#design-empty");
    if (empty) {
      empty.classList.toggle("is-hidden", domains.length > 0);
      empty.setAttribute("aria-hidden", domains.length > 0 ? "true" : "false");
    }
    const nLayers = domains.reduce((n, d) => n + d.layers.size, 0);
    setLiveBadge(
      domains.length ? `${domains.length} domain · ${nLayers} layers` : "editing",
      domains.length ? "pass" : "warn"
    );
  }

  function stackHtml(d) {
    const order = ["bronze", "silver", "gold"];
    const parts = [];
    order.forEach((layer, i) => {
      const on = d.layers.has(layer);
      const table = on
        ? `${d.domain_id}_${layer}${layer === "gold" ? "_daily" : ""}`
        : "—";
      parts.push(`<div class="stack-node ${on ? "on" : "off"} ${layer}" data-domain="${esc(
        d.id
      )}" data-layer="${layer}">
        <div>
          <div class="ln">${layer}</div>
          <div class="tbl">${esc(table)}</div>
        </div>
        <span class="badge ${on ? "pass" : "warn"}">${on ? "on" : "off"}</span>
      </div>`);
      if (i < order.length - 1) {
        const lit = on && d.layers.has(order[i + 1]);
        parts.push(`<div class="stack-connector${lit ? "" : " dim"}" aria-hidden="true"></div>`);
      }
    });
    return `<div class="medallion-stack">${parts.join("")}</div>`;
  }

  function renderCanvas() {
    const host = $("#design-nodes");
    if (!host) return;
    host.innerHTML = domains
      .map((d) => {
        const selected = d.id === selectedDomainId ? " selected" : "";
        return `<div class="domain-card${selected}" data-domain-id="${esc(d.id)}" data-drop-domain="1">
          <div class="domain-head">
            <strong>${esc(d.domain_id)}</strong>
            <div class="domain-tools">
              <button type="button" class="btn ghost mini" data-rename="${esc(d.id)}">Rename</button>
              <button type="button" class="btn ghost mini" data-remove="${esc(d.id)}">✕</button>
            </div>
          </div>
          ${stackHtml(d)}
        </div>`;
      })
      .join("");

    host.querySelectorAll(".domain-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        selectedDomainId = card.getAttribute("data-domain-id");
        renderCanvas();
      });
      card.addEventListener("dragover", (e) => {
        e.preventDefault();
        card.classList.add("drop-target");
      });
      card.addEventListener("dragleave", () => card.classList.remove("drop-target"));
      card.addEventListener("drop", (e) => {
        e.preventDefault();
        card.classList.remove("drop-target");
        const kind = e.dataTransfer.getData("text/plain") || dragKind;
        const id = card.getAttribute("data-domain-id");
        if (["bronze", "silver", "gold"].includes(kind)) {
          addLayer(id, kind);
        }
      });
    });

    host.querySelectorAll("[data-rename]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        renameDomain(btn.getAttribute("data-rename"));
      });
    });
    host.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeDomain(btn.getAttribute("data-remove"));
      });
    });
    host.querySelectorAll(".stack-node").forEach((node) => {
      node.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = node.getAttribute("data-domain");
        const layer = node.getAttribute("data-layer");
        toggleLayer(id, layer);
      });
    });

    refreshJson();
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function addDomain(name) {
    const domain_id = (name || `domain_${domains.length + 1}`)
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_]+/g, "_")
      .replace(/^_|_$/g, "") || `domain_${domains.length + 1}`;
    const id = `d-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    domains.push({ id, domain_id, layers: new Set() });
    selectedDomainId = id;
    renderCanvas();
    status(`Added domain ${domain_id}. Drop bronze → silver → gold onto the stack.`);
  }

  function removeDomain(id) {
    domains = domains.filter((d) => d.id !== id);
    if (selectedDomainId === id) selectedDomainId = domains[0]?.id || null;
    renderCanvas();
  }

  function renameDomain(id) {
    const d = domains.find((x) => x.id === id);
    if (!d) return;
    const next = prompt("Domain id", d.domain_id);
    if (!next) return;
    d.domain_id = next
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_]+/g, "_");
    renderCanvas();
  }

  function addLayer(domainId, layer) {
    const d = domains.find((x) => x.id === domainId);
    if (!d) return;
    if (layer === "silver" && !d.layers.has("bronze")) {
      d.layers.add("bronze");
      status("Auto-added bronze (required upstream of silver).");
    }
    if (layer === "gold") {
      if (!d.layers.has("bronze")) d.layers.add("bronze");
      if (!d.layers.has("silver")) d.layers.add("silver");
      status("Auto-added bronze→silver (required upstream of gold).");
    }
    d.layers.add(layer);
    selectedDomainId = domainId;
    renderCanvas();
  }

  function toggleLayer(domainId, layer) {
    const d = domains.find((x) => x.id === domainId);
    if (!d) return;
    if (d.layers.has(layer)) d.layers.delete(layer);
    else addLayer(domainId, layer);
    renderCanvas();
  }

  function download(filename, text, mime) {
    const blob = new Blob([text], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function wirePalette() {
    document.querySelectorAll(".palette-item").forEach((el) => {
      el.addEventListener("dragstart", (e) => {
        dragKind = el.getAttribute("data-kind");
        e.dataTransfer.setData("text/plain", dragKind);
        e.dataTransfer.effectAllowed = "copy";
      });
      el.addEventListener("dragend", () => {
        dragKind = null;
      });
    });

    const canvas = $("#design-canvas");
    if (!canvas) return;
    canvas.addEventListener("dragover", (e) => {
      e.preventDefault();
      canvas.classList.add("drag-over");
    });
    canvas.addEventListener("dragleave", () => canvas.classList.remove("drag-over"));
    canvas.addEventListener("drop", (e) => {
      e.preventDefault();
      canvas.classList.remove("drag-over");
      const kind = e.dataTransfer.getData("text/plain") || dragKind;
      if (kind === "domain") {
        addDomain(prompt("New domain id", "xyz") || "xyz");
        return;
      }
      if (["bronze", "silver", "gold"].includes(kind)) {
        if (!selectedDomainId && domains.length) selectedDomainId = domains[0].id;
        if (!selectedDomainId) {
          addDomain("xyz");
        }
        addLayer(selectedDomainId, kind);
      }
    });
  }

  async function runApply() {
    const btns = [$("#btn-design-apply"), $("#btn-design-apply-secondary")].filter(Boolean);
    btns.forEach((b) => {
      b.disabled = true;
    });
    status("Saving mesh.yaml and generating pipelines…");
    setLiveBadge("generating…", "warn");
    try {
      const res = await fetch("/api/designer/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract: buildContract() }),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.error || "Apply failed");
      const pending = (payload.readers_pending || []).length;
      status(
        `Wrote ${payload.contract_path} · generated ${payload.pipeline_count} pipelines → ${payload.generated}` +
          (pending
            ? ` · ${pending} readers.py still TODO`
            : " · ready to package + terraform apply")
      );
      setLiveBadge("generated", "pass");
      toast(`Generated ${payload.pipeline_count} pipelines`);
      window.dispatchEvent(new CustomEvent("sdm-journey", { detail: { step: "generate" } }));
      window.dispatchEvent(new Event("sdm-dashboard-refresh"));
      window.dispatchEvent(new CustomEvent("sdm-goto-tab", { detail: { tab: "pipelines" } }));
    } catch (err) {
      status(String(err.message || err), true);
      setLiveBadge("error", "fail");
      toast(String(err.message || err), true);
    } finally {
      btns.forEach((b) => {
        b.disabled = false;
      });
    }
  }

  function wireButtons() {
    $("#btn-design-add-domain")?.addEventListener("click", () => {
      addDomain(prompt("Domain id", `xyz${domains.length ? domains.length + 1 : ""}`) || "xyz");
    });
    $("#btn-design-clear")?.addEventListener("click", () => {
      domains = [];
      selectedDomainId = null;
      renderCanvas();
      status("Canvas cleared.");
    });
    $("#btn-design-sample")?.addEventListener("click", () => {
      domains = [
        { id: "d-xyz", domain_id: "xyz", layers: new Set(["bronze", "silver", "gold"]) },
      ];
      selectedDomainId = "d-xyz";
      $("#design-org").value = "xyz-org";
      $("#design-prefix").value = "xyz";
      renderCanvas();
      status("Sample xyz domain with bronze → silver → gold.");
    });

    [
      "design-org",
      "design-prefix",
      "design-region",
      "design-acct-producer",
      "design-acct-steward",
      "design-acct-publisher",
      "design-subnets",
      "design-sgs",
      "design-vpc-id",
      "design-vpc-cidr",
      "design-vpc-azs",
    ].forEach((id) => {
      $(`#${id}`)?.addEventListener("input", refreshJson);
      $(`#${id}`)?.addEventListener("change", refreshJson);
    });

    document.querySelectorAll('input[name="design-acct-mode"]').forEach((el) => {
      el.addEventListener("change", () => {
        syncAccountFields();
        refreshJson();
      });
    });
    document.querySelectorAll('input[name="design-vpc-mode"]').forEach((el) => {
      el.addEventListener("change", () => {
        syncVpcFields();
        refreshJson();
      });
    });
    syncAccountFields();
    syncVpcFields();

    $("#btn-design-copy")?.addEventListener("click", async () => {
      const text = JSON.stringify(buildContract(), null, 2);
      await navigator.clipboard.writeText(text);
      toast("JSON copied");
    });

    $("#btn-design-dl-json")?.addEventListener("click", () => {
      const prefix = ($("#design-prefix")?.value || "mesh").trim();
      download(`${prefix}.mesh.json`, JSON.stringify(buildContract(), null, 2), "application/json");
    });

    $("#btn-design-dl-yaml")?.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/designer/to-yaml", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ contract: buildContract() }),
        });
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.error || "YAML failed");
        const prefix = ($("#design-prefix")?.value || "mesh").trim();
        download(`${prefix}.mesh.yaml`, payload.yaml, "text/yaml");
        toast("YAML downloaded");
      } catch (err) {
        toast(String(err.message || err), true);
      }
    });

    $("#btn-design-validate")?.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/designer/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ contract: buildContract() }),
        });
        const payload = await res.json();
        if (payload.ok) {
          status(`Valid MedallionMesh · ${payload.pipeline_estimate || "?"} layer pipelines`);
          setLiveBadge("valid", "pass");
          toast("Contract valid");
        } else {
          status((payload.errors || ["invalid"]).join("; "), true);
          setLiveBadge("invalid", "fail");
          toast("Validation failed", true);
        }
      } catch (err) {
        toast(String(err.message || err), true);
      }
    });

    $("#btn-design-save")?.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/designer/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contract: buildContract(),
            format: "both",
          }),
        });
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.error || "Save failed");
        status(
          `Saved mesh.yaml at ${payload.contract_yaml || payload.directory}. Next: Generate pipelines.`
        );
        setLiveBadge("saved", "pass");
        toast("Saved mesh.yaml in project folder");
      } catch (err) {
        toast(String(err.message || err), true);
      }
    });

    $("#btn-design-apply")?.addEventListener("click", runApply);
    $("#btn-design-apply-secondary")?.addEventListener("click", runApply);
  }

  function init() {
    if (!$("#panel-design")) return;
    wirePalette();
    wireButtons();
    renderCanvas();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
