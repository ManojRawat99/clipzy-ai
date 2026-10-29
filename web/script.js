let pollTimer = null;

const youtubeUrlInput = document.getElementById("youtubeUrl");
const clipBtn = document.getElementById("clipBtn");
const clipCountSelect = document.getElementById("clipCount");
const aspectRatioSelect = document.getElementById("aspectRatio");

const progressBox = document.getElementById("progressBox");
const progressStatusText = document.getElementById("progressStatusText");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");

const stepDl = document.getElementById("step-dl");
const stepAi = document.getElementById("step-ai");
const stepCrop = document.getElementById("step-crop");
const stepSub = document.getElementById("step-sub");

const clipsGrid = document.getElementById("clipsGrid");
const clipCountBadge = document.getElementById("clipCountBadge");

// Settings Modal
const settingsModal = document.getElementById("settingsModal");
const openSettingsBtn = document.getElementById("openSettingsBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const geminiKeyInput = document.getElementById("geminiKeyInput");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const settingsStatusMsg = document.getElementById("settingsStatusMsg");

document.addEventListener("DOMContentLoaded", () => {
  loadClips();
  loadSettings();
});

// Load existing clips
async function loadClips() {
  try {
    const res = await fetch("/api/clips");
    if (!res.ok) return;
    const clips = await res.json();
    renderClipsGrid(clips);
  } catch (err) {
    console.error("Failed to load clips", err);
  }
}

function renderClipsGrid(clips) {
  clipsGrid.innerHTML = "";
  clipCountBadge.textContent = `${clips.length} Clips`;

  if (clips.length === 0) {
    clipsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px; color: #64748b;">
        <p style="font-size: 16px;">No clips generated yet.</p>
        <p style="font-size: 13px; margin-top: 6px;">Paste a YouTube video link above to generate your first 9:16 viral clip!</p>
      </div>
    `;
    return;
  }

  clips.forEach((clip) => {
    const card = document.createElement("div");
    card.className = "clip-card";

    // Clean display title
    const displayName = clip.filename.replace(/^clip_\d+_[a-z0-9]+_/, "").replace(/\.mp4$/, "").replace(/_/g, " ");

    card.innerHTML = `
      <div class="video-container">
        <video src="${clip.download_url}" controls playsinline preload="metadata"></video>
      </div>
      <div class="card-details">
        <div class="card-meta">
          <span class="score-badge">🔥 Viral Clip</span>
          <span class="duration-tag">💾 ${clip.size_mb} MB</span>
        </div>
        <h3>${displayName}</h3>
        <a href="${clip.download_url}" download="${clip.filename}" class="btn-download-video">
          ⬇️ Download 9:16 Video
        </a>
      </div>
    `;
    clipsGrid.appendChild(card);
  });
}

// Generate Action
clipBtn.addEventListener("click", async () => {
  const url = youtubeUrlInput.value.trim();
  if (!url) {
    alert("Please enter a valid YouTube link!");
    return;
  }

  clipBtn.disabled = true;
  clipBtn.innerHTML = "<span>⚡ Processing Video...</span>";
  progressBox.classList.remove("hidden");
  updateProgress(5, "Connecting to video pipeline...");

  try {
    const res = await fetch("/api/clip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        num_clips: parseInt(clipCountSelect.value, 10) || 3,
        aspect_ratio: aspectRatioSelect ? aspectRatioSelect.value : "9:16"
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to start job");
    }

    const data = await res.json();
    pollStatus(data.job_id);

  } catch (err) {
    alert(`Error: ${err.message}`);
    clipBtn.disabled = false;
    clipBtn.innerHTML = "<span>⚡ Generate Viral Clips</span>";
    progressBox.classList.add("hidden");
  }
});

function pollStatus(jobId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      if (!res.ok) return;

      const job = await res.json();
      updateProgress(job.progress, job.message);

      if (job.status === "completed") {
        clearInterval(pollTimer);
        clipBtn.disabled = false;
        clipBtn.innerHTML = "<span>⚡ Generate More Clips</span>";
        setTimeout(() => {
          progressBox.classList.add("hidden");
          loadClips();
        }, 1500);
      } else if (job.status === "failed") {
        clearInterval(pollTimer);
        clipBtn.disabled = false;
        clipBtn.innerHTML = "<span>⚡ Try Again</span>";
        alert(`Clipping failed: ${job.error || "Unknown error"}`);
      } else if (job.status === "not_found") {
        clearInterval(pollTimer);
        clipBtn.disabled = false;
        clipBtn.innerHTML = "<span>⚡ Generate Viral Clips</span>";
        progressBox.classList.add("hidden");
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
  }, 1000);
}

function updateProgress(percent, message) {
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  progressStatusText.textContent = message;

  stepDl.classList.toggle("active", percent >= 15);
  stepAi.classList.toggle("active", percent >= 30);
  stepCrop.classList.toggle("active", percent >= 60);
  stepSub.classList.toggle("active", percent >= 85);
}

// Settings modal
openSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("hidden"));
closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const data = await res.json();
      if (data.has_gemini_key) {
        settingsStatusMsg.textContent = `Active Key: ${data.masked_key}`;
      }
    }
  } catch (e) {}
}

saveSettingsBtn.addEventListener("click", async () => {
  const key = geminiKeyInput.value.trim();
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gemini_api_key: key })
    });
    if (res.ok) {
      settingsStatusMsg.textContent = "Settings saved successfully!";
      geminiKeyInput.value = "";
      setTimeout(() => {
        settingsModal.classList.add("hidden");
        loadSettings();
      }, 1000);
    }
  } catch (e) {
    settingsStatusMsg.textContent = "Failed to save settings.";
  }
});

