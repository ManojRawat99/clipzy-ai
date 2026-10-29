let pollTimer = null;
let toastTimeout = null;

// DOM Elements
const youtubeUrlInput = document.getElementById("youtubeUrl");
const clearInputBtn = document.getElementById("clearInputBtn");
const pasteBtn = document.getElementById("pasteBtn");
const sampleBtn = document.getElementById("sampleBtn");
const clipBtn = document.getElementById("clipBtn");
const clipCountSelect = document.getElementById("clipCount");
const aspectRatioSelect = document.getElementById("aspectRatio");

// Progress elements
const progressBox = document.getElementById("progressBox");
const progressStatusText = document.getElementById("progressStatusText");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");

const stepDl = document.getElementById("step-dl");
const stepAi = document.getElementById("step-ai");
const stepCrop = document.getElementById("step-crop");
const stepSub = document.getElementById("step-sub");

// Results elements
const clipsGrid = document.getElementById("clipsGrid");
const clipCountBadge = document.getElementById("clipCountBadge");

// Toast elements
const toastNotification = document.getElementById("toastNotification");
const toastIcon = document.getElementById("toastIcon");
const toastTitle = document.getElementById("toastTitle");
const toastMessage = document.getElementById("toastMessage");
const toastDismissBtn = document.getElementById("toastDismissBtn");

// Settings elements
const settingsModal = document.getElementById("settingsModal");
const openSettingsBtn = document.getElementById("openSettingsBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const geminiKeyInput = document.getElementById("geminiKeyInput");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const settingsStatusMsg = document.getElementById("settingsStatusMsg");

// Segmented Control Buttons
const ratioSegments = document.getElementById("ratioSegments");
const countSegments = document.getElementById("countSegments");

// Sample video URL for quick 1-tap testing
const SAMPLE_URL = "https://www.youtube.com/watch?v=mWlmcjwV44o";

document.addEventListener("DOMContentLoaded", () => {
  loadClips();
  loadSettings();
  setupSegmentControls();

  // Input typing: show/hide clear button
  youtubeUrlInput.addEventListener("input", () => {
    if (youtubeUrlInput.value.trim().length > 0) {
      clearInputBtn.classList.remove("hidden");
    } else {
      clearInputBtn.classList.add("hidden");
    }
  });

  // Clear button
  clearInputBtn.addEventListener("click", () => {
    youtubeUrlInput.value = "";
    clearInputBtn.classList.add("hidden");
    youtubeUrlInput.focus();
  });

  // 1-Tap Paste Button (Specialized for iPhone & Mobile Safari/Chrome)
  pasteBtn.addEventListener("click", async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim().length > 0) {
          youtubeUrlInput.value = text.trim();
          clearInputBtn.classList.remove("hidden");
          showToast("Link Pasted! 📋", "YouTube URL ready to clip.", "success", 2500);
          return;
        }
      }
    } catch (e) {
      console.log("Clipboard API permission required, focusing input field:", e);
    }
    // Fallback: focus input and prompt paste
    youtubeUrlInput.focus();
    youtubeUrlInput.select();
    showToast("Ready to Paste", "Long-press inside the input box and tap Paste.", "info", 3000);
  });

  // Sample video button
  sampleBtn.addEventListener("click", () => {
    youtubeUrlInput.value = SAMPLE_URL;
    clearInputBtn.classList.remove("hidden");
    showToast("Sample Loaded! 🎬", "Ready to generate clips.", "info", 2500);
  });

  // Toast dismiss button
  toastDismissBtn.addEventListener("click", hideToast);
});

// Setup iOS-style segmented controls
function setupSegmentControls() {
  if (ratioSegments) {
    const buttons = ratioSegments.querySelectorAll(".segment-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const val = btn.dataset.value;
        if (aspectRatioSelect) aspectRatioSelect.value = val;
      });
    });
  }

  if (countSegments) {
    const buttons = countSegments.querySelectorAll(".segment-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const val = btn.dataset.value;
        if (clipCountSelect) clipCountSelect.value = val;
      });
    });
  }
}

// In-App Toast Notification (Replaces ugly browser alerts)
function showToast(title, message, type = "info", duration = 4500) {
  if (toastTimeout) clearTimeout(toastTimeout);

  toastTitle.textContent = title;
  toastMessage.textContent = message;

  toastNotification.className = "toast-notification";
  if (type === "error") {
    toastNotification.classList.add("error");
    toastIcon.textContent = "⚠️";
  } else if (type === "success") {
    toastNotification.classList.add("success");
    toastIcon.textContent = "🎉";
  } else {
    toastIcon.textContent = "⚡";
  }

  toastNotification.classList.remove("hidden");

  toastTimeout = setTimeout(() => {
    hideToast();
  }, duration);
}

function hideToast() {
  toastNotification.classList.add("hidden");
}

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
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px 16px; color: #64748b; background: rgba(255,255,255,0.02); border-radius: 16px; border: 1px dashed rgba(255,255,255,0.08);">
        <p style="font-size: 28px; margin-bottom: 8px;">🎬</p>
        <p style="font-size: 15px; font-weight: 700; color: #94a3b8;">No clips generated yet</p>
        <p style="font-size: 12.5px; margin-top: 4px; color: #64748b;">Paste a YouTube link above and tap "Generate Viral Clips"!</p>
      </div>
    `;
    return;
  }

  clips.forEach((clip) => {
    const card = document.createElement("div");
    card.className = "clip-card";

    const displayName = clip.filename
      .replace(/^clip_\d+_[a-z0-9]+_/, "")
      .replace(/\.mp4$/, "")
      .replace(/_/g, " ");

    card.innerHTML = `
      <div class="video-container">
        <video 
          src="${clip.download_url}" 
          controls 
          playsinline 
          webkit-playsinline 
          preload="metadata"
        ></video>
      </div>
      <div class="card-details">
        <div class="card-meta">
          <span class="score-badge">🔥 Viral Clip</span>
          <span class="duration-tag">💾 ${clip.size_mb} MB</span>
        </div>
        <h3>${displayName}</h3>
        <div class="card-actions">
          <a href="${clip.download_url}" download="${clip.filename}" class="btn-download-video">
            ⬇️ Save Video
          </a>
          <button type="button" class="btn-share-video" data-url="${clip.download_url}" data-title="${displayName}" title="Share to Instagram / WhatsApp">
            ↗️
          </button>
        </div>
      </div>
    `;

    // Hook up native iOS Web Share API
    const shareBtn = card.querySelector(".btn-share-video");
    if (shareBtn) {
      shareBtn.addEventListener("click", async () => {
        const fullShareUrl = window.location.origin + clip.download_url;
        if (navigator.share) {
          try {
            await navigator.share({
              title: displayName,
              text: `Check out this viral clip from Clipzy AI!`,
              url: fullShareUrl
            });
          } catch (e) {
            console.log("Share cancelled or failed:", e);
          }
        } else {
          // Fallback: Copy link
          try {
            await navigator.clipboard.writeText(fullShareUrl);
            showToast("Link Copied! 🔗", "Video URL copied to clipboard.", "success", 3000);
          } catch (err) {
            showToast("Video Link", fullShareUrl, "info", 4000);
          }
        }
      });
    }

    clipsGrid.appendChild(card);
  });
}

// Generate Action
clipBtn.addEventListener("click", async () => {
  const url = youtubeUrlInput.value.trim();
  if (!url) {
    showToast("Missing URL", "Please paste a valid YouTube video link first.", "error", 3500);
    youtubeUrlInput.focus();
    return;
  }

  // Get selected values
  const aspect_ratio = aspectRatioSelect ? aspectRatioSelect.value : "9:16";
  const num_clips = parseInt(clipCountSelect ? clipCountSelect.value : "3", 10) || 3;

  clipBtn.disabled = true;
  clipBtn.innerHTML = `
    <span class="btn-content">
      <span class="spinner-small" style="border-color: rgba(255,255,255,0.3); border-top-color: white;"></span>
      <span class="btn-text">Processing Video...</span>
    </span>
  `;
  progressBox.classList.remove("hidden");
  updateProgress(5, "Connecting to video pipeline...");

  try {
    const res = await fetch("/api/clip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        num_clips: num_clips,
        aspect_ratio: aspect_ratio
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to start clipping job");
    }

    const data = await res.json();
    pollStatus(data.job_id);

  } catch (err) {
    showToast("Clipping Error", err.message, "error", 6000);
    resetGenerateButton();
    progressBox.classList.add("hidden");
  }
});

function resetGenerateButton() {
  clipBtn.disabled = false;
  clipBtn.innerHTML = `
    <span class="btn-content">
      <span class="btn-icon">⚡</span>
      <span class="btn-text">Generate Viral Clips</span>
    </span>
  `;
}

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
        resetGenerateButton();
        showToast("Success! 🎉", "Your viral clips are ready below!", "success", 4000);
        setTimeout(() => {
          progressBox.classList.add("hidden");
          loadClips();
          // Smooth scroll to clips section
          clipsGrid.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 1200);
      } else if (job.status === "failed") {
        clearInterval(pollTimer);
        resetGenerateButton();
        const friendlyError = job.error || "An error occurred during video processing.";
        showToast("Processing Failed", friendlyError, "error", 7000);
      } else if (job.status === "not_found") {
        clearInterval(pollTimer);
        resetGenerateButton();
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
settingsModal.querySelector(".modal-backdrop").addEventListener("click", () => settingsModal.classList.add("hidden"));

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
      showToast("Settings Saved", "Gemini API key updated.", "success", 2500);
      setTimeout(() => {
        settingsModal.classList.add("hidden");
        loadSettings();
      }, 1000);
    }
  } catch (e) {
    settingsStatusMsg.textContent = "Failed to save settings.";
    showToast("Settings Error", "Could not save settings.", "error", 3000);
  }
});
