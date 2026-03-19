const ingestionForm = document.getElementById("ingestion-form");
const hubKey = document.getElementById("hubKey");
const mode = document.getElementById("mode");
const ingestionStatus = document.getElementById("ingestionStatus");
const ingestionResults = document.getElementById("ingestionResults");
const databasePath = document.getElementById("databasePath");
const progressPanel = document.getElementById("progressPanel");
const progressBar = document.getElementById("progressBar");
const progressLabel = document.getElementById("progressLabel");
const progressMeta = document.getElementById("progressMeta");

let activeJobId = null;
let pollHandle = null;

initialize();

async function initialize() {
  try {
    setStatus("Loading hubs and database state...");
    const [hubsResponse, statusResponse] = await Promise.all([
      fetch("/api/hubs"),
      fetch("/api/ingestion/status"),
    ]);
    const hubsPayload = await hubsResponse.json();
    const statusPayload = await statusResponse.json();
    populateHubs(hubsPayload.hubs || []);
    renderStatusTable(statusPayload.regions || []);
    databasePath.value = statusPayload.database_path || "";
    await loadLatestJob();
    setStatus("Ready.");
  } catch (error) {
    setStatus(`Failed to initialize: ${error.message}`);
  }
}

ingestionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Ingestion running. Large regions can take a while...");
  const payload = {
    mode: mode.value,
    hubKey: hubKey.value,
    refresh: ingestionForm.refresh.checked,
  };

  try {
    const response = await fetch("/api/ingestion/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Ingestion failed");
    }
    activeJobId = result.job_id;
    renderJob(result);
    startPolling();
    setStatus("Ingestion started.");
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  }
});

async function refreshStatus() {
  const response = await fetch("/api/ingestion/status");
  const payload = await response.json();
  databasePath.value = payload.database_path || "";
  renderStatusTable(payload.regions || []);
}

function populateHubs(hubs) {
  hubKey.innerHTML = "";
  for (const hub of hubs) {
    hubKey.appendChild(new Option(hub.name, hub.key));
  }
  hubKey.value = "jita";
}

function renderStatusTable(rows) {
  if (!rows.length) {
    ingestionResults.innerHTML = `<tr><td colspan="4" class="empty">No ingestions yet.</td></tr>`;
    return;
  }

  ingestionResults.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.region_name || `Region ${row.region_id}`)}</td>
      <td>${escapeHtml(row.source)}</td>
      <td>${new Intl.NumberFormat("en-US").format(row.orders_written)}</td>
      <td>${escapeHtml(row.completed_at)}</td>
    `;
    ingestionResults.appendChild(tr);
  }
}

function setStatus(message) {
  ingestionStatus.textContent = message;
}

async function loadLatestJob() {
  const response = await fetch("/api/ingestion/job/latest");
  const payload = await response.json();
  if (payload.job) {
    activeJobId = payload.job.job_id;
    renderJob(payload.job);
    if (payload.job.status === "running") {
      startPolling();
    }
  }
}

function startPolling() {
  stopPolling();
  pollHandle = window.setInterval(async () => {
    if (!activeJobId) {
      stopPolling();
      return;
    }
    try {
      const response = await fetch(`/api/ingestion/job?id=${encodeURIComponent(activeJobId)}`);
      const job = await response.json();
      if (!response.ok) {
        throw new Error(job.error || "Failed to refresh progress");
      }
      renderJob(job);
      if (job.status !== "running") {
        stopPolling();
        await refreshStatus();
        if (job.status === "completed") {
          setStatus("Ingestion complete.");
        } else if (job.status === "failed") {
          setStatus(`Ingestion failed: ${job.error || "Unknown error"}`);
        }
      }
    } catch (error) {
      stopPolling();
      setStatus(`Progress polling failed: ${error.message}`);
    }
  }, 1000);
}

function stopPolling() {
  if (pollHandle !== null) {
    window.clearInterval(pollHandle);
    pollHandle = null;
  }
}

function renderJob(job) {
  progressPanel.hidden = false;
  progressBar.style.width = `${job.progress_percent || 0}%`;
  progressLabel.textContent = job.error || job.current_label || "Running";
  progressMeta.textContent =
    `${job.completed_steps} / ${job.total_steps} regions | ${job.progress_percent || 0}%`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
