const startButton = document.getElementById("startButton");
const statusPill = document.getElementById("statusPill");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const currentSite = document.getElementById("currentSite");
const totalSites = document.getElementById("totalSites");
const completedSites = document.getElementById("completedSites");
const emailsFound = document.getElementById("emailsFound");
const phonesFound = document.getElementById("phonesFound");
const resultsBody = document.getElementById("resultsBody");
const errorMessage = document.getElementById("errorMessage");

async function fetchStatus() {
  const response = await fetch("/api/status");
  return response.json();
}

function renderStatus(status) {
  const running = status.running;
  const total = status.total_sites || 0;
  const completed = status.completed_sites || 0;

  totalSites.textContent = total;
  completedSites.textContent = completed;

  const emailsCount = (status.results || []).reduce(
    (sum, result) => sum + (result.emails?.length || 0),
    0,
  );
  const phonesCount = (status.results || []).reduce(
    (sum, result) => sum + (result.phones?.length || 0),
    0,
  );

  emailsFound.textContent = emailsCount;
  phonesFound.textContent = phonesCount;

  const progress = total ? Math.round((completed / total) * 100) : 0;
  progressBar.style.width = `${progress}%`;
  progressText.textContent = `${completed} / ${total} sites`;
  currentSite.textContent = status.current_site
    ? `Current: ${status.current_site}`
    : "";

  if (running) {
    statusPill.textContent = "Running";
    statusPill.classList.add("running");
    statusPill.classList.remove("complete");
  } else if (completed && completed === total) {
    statusPill.textContent = "Complete";
    statusPill.classList.remove("running");
    statusPill.classList.add("complete");
  } else {
    statusPill.textContent = "Idle";
    statusPill.classList.remove("running");
    statusPill.classList.remove("complete");
  }

  startButton.disabled = running;
  errorMessage.textContent = status.error || "";

  resultsBody.innerHTML = "";
  (status.results || []).slice(-20).forEach((result) => {
    const row = document.createElement("div");
    row.className = "row";

    const site = document.createElement("div");
    site.textContent = result.site;

    const emails = document.createElement("div");
    emails.textContent = result.emails?.join(", ") || "";

    const phones = document.createElement("div");
    phones.textContent = result.phones?.join(", ") || "";

    const statusCell = document.createElement("div");
    statusCell.textContent = result.error ? "Error" : "OK";

    row.append(site, emails, phones, statusCell);
    resultsBody.append(row);
  });
}

async function poll() {
  try {
    const status = await fetchStatus();
    renderStatus(status);
  } catch (error) {
    errorMessage.textContent = "Unable to reach crawler server.";
  }
}

startButton.addEventListener("click", async () => {
  errorMessage.textContent = "";
  const response = await fetch("/api/start", { method: "POST" });
  if (!response.ok) {
    const payload = await response.json();
    errorMessage.textContent = payload.error || "Unable to start crawl.";
  }
});

poll();
setInterval(poll, 2000);
