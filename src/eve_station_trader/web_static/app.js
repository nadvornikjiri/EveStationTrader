const form = document.getElementById("scan-form");
const sourceHub = document.getElementById("sourceHub");
const destinationHub = document.getElementById("destinationHub");
const statusNode = document.getElementById("status");
const resultsBody = document.getElementById("resultsBody");
const summaryPanel = document.getElementById("summaryPanel");
const summaryText = document.getElementById("summaryText");

boot();

async function boot() {
  try {
    setStatus("Loading hub list...");
    const response = await fetch("/api/hubs");
    const payload = await response.json();
    populateHubs(payload.hubs || []);
    setStatus("Ready.");
  } catch (error) {
    setStatus(`Failed to load hubs: ${error.message}`);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Running scan. This can take a bit on a fresh ESI pull...");
  renderEmpty("Scanning market data...");

  const payload = {
    sourceHub: sourceHub.value,
    destinationHub: destinationHub.value,
    strategy: form.strategy.value,
    top: Number(form.top.value),
    minProfit: Number(form.minProfit.value),
    minRoi: Number(form.minRoi.value),
    salesTax: Number(form.salesTax.value),
    destinationBrokerFee: Number(form.destinationBrokerFee.value),
    refresh: form.refresh.checked,
  };

  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Scan failed");
    }
    renderSummary(data);
    renderResults(data.opportunities || []);
    setStatus(`Scan complete. Found ${data.count} opportunities.`);
  } catch (error) {
    summaryPanel.hidden = true;
    renderEmpty(error.message);
    setStatus(`Error: ${error.message}`);
  }
});

function populateHubs(hubs) {
  sourceHub.innerHTML = "";
  destinationHub.innerHTML = "";
  for (const hub of hubs) {
    sourceHub.appendChild(new Option(hub.name, hub.key));
    destinationHub.appendChild(new Option(hub.name, hub.key));
  }
  sourceHub.value = "jita";
  destinationHub.value = "amarr";
}

function renderSummary(data) {
  summaryPanel.hidden = false;
  summaryText.textContent =
    `${data.source_hub.name} -> ${data.destination_hub.name} | ` +
    `${labelStrategy(data.strategy)} | ${data.count} opportunities | source: ${data.data_source}`;
}

function renderResults(items) {
  if (!items.length) {
    renderEmpty("No opportunities matched the current filters.");
    return;
  }

  resultsBody.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <strong>${escapeHtml(item.item_name)}</strong>
        <div class="meta">Type ${item.type_id}</div>
      </td>
      <td>${formatIsk(item.source_buy_price)}</td>
      <td>${formatIsk(item.strategy === "instant" ? item.destination_buy_price : item.destination_sell_price)}</td>
      <td class="${item.net_profit_per_unit >= 0 ? "positive" : "negative"}">${formatIsk(item.net_profit_per_unit)}</td>
      <td>${formatPercent(item.roi_percent)}</td>
      <td>${formatInt(item.tradable_units)}</td>
      <td class="${item.estimated_profit >= 0 ? "positive" : "negative"}">${formatIsk(item.estimated_profit)}</td>
    `;
    resultsBody.appendChild(row);
  }
}

function renderEmpty(message) {
  resultsBody.innerHTML = `<tr><td colspan="7" class="empty">${escapeHtml(message)}</td></tr>`;
}

function setStatus(message) {
  statusNode.textContent = message;
}

function formatIsk(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value) + " ISK";
}

function formatPercent(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value) + "%";
}

function formatInt(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function labelStrategy(value) {
  return value === "relist" ? "Relist" : "Instant sell";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
