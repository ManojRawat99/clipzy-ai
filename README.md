# ⚡ Clipzy AI - YouTube to Viral Shorts & Reels Clipper

Turn any long YouTube video into viral clips (for YouTube Shorts, Instagram Reels, and TikTok) 100% free of cost!

---

## 🚀 Key Features

* **Multi-Format Support:** 9:16 Vertical (Shorts/Reels), 1:1 Square (Instagram Posts), 4:5 Portrait, and 16:9 Landscape.
* **AI Hook & Virality Scoring:** Scans video transcripts to find the highest-retention moments (25–55 seconds).
* **Smart Face-Tracking:** Automatically detects speakers using MediaPipe to keep them centered in vertical/square video.
* **Animated Viral Captions:** Burns synchronized, high-visibility captions (Alex Hormozi / MrBeast style) onto the clip.
* **Chrome Extension:** Injects a "⚡ Clip with Clipzy" button right on YouTube watch pages or allows 1-click clipping from the extension popup.
* **Web Dashboard:** Studio interface at `http://localhost:8000` with video previews and one-click downloads.
* **100% Free of Cost:** Runs locally with zero paid subscriptions.

---

## 🛠️ Step 1: Start the Local Backend Server

* **For PC only:** Double click **`start.bat`** (or run `python backend/app.py`).
* **For iPhone / Mobile Access:** Double click **`start_mobile.bat`** (or run `python start_mobile.py`).
  * It will give you an instant secure HTTPS link (e.g. `https://xyz.trycloudflare.com`) to open directly in your iPhone Safari/Chrome!

---

## 🌐 Step 2: Install the Chrome Extension

1. Open **Google Chrome** and visit: `chrome://extensions/`
2. Turn **ON** the **Developer mode** toggle in the top-right corner.
3. Click the **"Load unpacked"** button in the top-left corner.
4. Select the folder: **`d:\kixy\extension`**
5. Pin the **Clipzy AI** icon in your Chrome toolbar!

---

## 🎬 How to Use

### Method A: Directly from YouTube
1. Open any YouTube video in Chrome (e.g. podcast, interview, speech).
2. Look for the **"⚡ Clip with Clipzy"** button next to the Like/Share buttons.
3. Click it — the video will automatically be processed in the background!

### Method B: From the Extension Popup
1. Click the Clipzy AI icon in your browser toolbar.
2. Select your desired Aspect Ratio (9:16, 1:1, 4:5, 16:9).
3. Click **"⚡ Generate Viral Clips"** and watch the live progress.
4. Download your finished MP4s!

### Method C: From the Web Dashboard
1. Open **[http://localhost:8000](http://localhost:8000)** in your browser.
2. Choose your Aspect Ratio, paste the link, and download your viral clips.

---

## 🔑 AI Settings (Optional - 100% Free)
* Out of the box, Clipzy includes a built-in **Smart NLP Hook Analyzer** that needs no API key.
* If you want Google Gemini AI to analyze transcripts, get a free key from **[Google AI Studio](https://aistudio.google.com/)** and paste it into the Settings box.
