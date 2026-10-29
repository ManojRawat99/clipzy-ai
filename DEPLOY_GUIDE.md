# 🚀 Clipzy AI - Cloud & Mobile Deployment Guide

## 📱 Mobile iPhone / Android Access

Your cloud service is live on Render:
👉 **`https://clipzy-ai-a073.onrender.com`**

### Features on Mobile:
- **1-Tap Paste Button**: Tap "📋 Tap to Paste Link" to instantly paste your copied YouTube URL.
- **Visual Segment Controls**: Thumb-friendly buttons for Aspect Ratio (📱 9:16 Shorts/Reels, 🟦 1:1, 🖼️ 4:5, 💻 16:9) and Clip Count (1, 3, 5).
- **Direct iPhone Save**: Tap "⬇️ Save Video" to download directly to your iPhone Camera Roll or Files app.
- **Native Social Share**: Tap "↗️" to share directly to Instagram, WhatsApp, or TikTok from iOS Safari.

---

## 🛡️ Overcoming YouTube Bot Checks & Region Issues

YouTube blocks certain datacenter IPs from fetching video streams without credentials. Clipzy AI uses a 3-tier bypass architecture:

1. **Android & iOS Player Client Emulation**: Emulates native mobile YouTube app requests, bypassing standard datacenter bot challenges.
2. **Multi-Region Geo Bypass**: Automatically routes format lookups across US and IN regions.
3. **Optional YouTube Cookies (For Age-Restricted & Region-Locked Videos)**:
   - If a video is age-restricted or region-locked:
   - Export cookies using Chrome/Edge extension *"Get cookies.txt LOCALLY"*.
   - In Render Dashboard: Go to **Environment** ➔ Add Environment Variable:
     - **Key:** `YOUTUBE_COOKIES`
     - **Value:** Paste the contents of your `cookies.txt`
   - Clipzy AI automatically detects and uses them!
