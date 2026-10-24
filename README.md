# Nixi AI Desktop Assistant ✦

An ultra-fast, minimal desktop AI assistant for Windows inspired by **HeyNixi** and Apple's **Dynamic Island**. Features an always-on-top, hover-expandable glassmorphism capsule with animated glowing eyes, real-time sentence-by-sentence streaming neural voice, live screen vision, instant focused-window dictation, and autonomous browser/form automation.

---

## ✨ Features

- **🏝️ Dynamic Island UI**: Lives at the top-center of your screen as a 156×42 capsule with multi-emotion animated eyes (`happy`, `listening`, `thinking`, `speaking`, `surprised`, `winking`) and a live **5-bar reactive audio wave visualizer**. Expands smoothly on hover to a 510×295 glassmorphic control drawer with text prompt input, mic tool, and god-mode action chips.
- **⚡ Sub-Second Concurrent Voice Streaming**: Speaks text **concurrently sentence-by-sentence** while the LLM generates tokens on screen. Instant barge-in interruption halts speech immediately when you speak.
- **🗣️ Natural Neural TTS**: Powered by Microsoft Neural Voices (`en-US-AvaNeural`) with sub-250ms synthesis time, decoded in memory and played via `sounddevice` at 24kHz.
- **👑 God-Mode System & OS Authority**:
  - **Volume & Media**: Control master volume (`volume 70`, `mute`, `unmute`), media playback (`play`, `pause`, `next track`, `skip`).
  - **Window Management**: `tile left`, `tile right`, `maximize`, `minimize all`, `show desktop`, `lock computer`.
  - **Hardware Diagnostics**: Instant CPU, RAM, Disk, and Battery diagnostics (`system status`).
  - **🔍 Exa Neural Search**: Semantic web search powered by Exa AI (`search web for...`, `exa search...`) with live highlights and content extraction.
  - **👁️ Agent Reach Internet Access**: Read clean markdown from any URL via Jina Reader (`read page <url>`), extract YouTube video info and subtitles (`summarize video <url>`), and check reachability (`agent reach doctor`).
  - **PowerShell & Shell**: Execute arbitrary terminal commands silently (`run powershell ...`).
  - **File Search**: Locate files across Desktop, Documents, and Downloads in milliseconds.
- **🎯 Autonomous Browser & Screen Automation**: Observes form fields, tables (e.g. Siemens Polarion, Jira, Google Forms), buttons, and inputs, and populates or executes actions in under 0.15s.
- **🎙️ Direct-to-App Dictation**: Transcribes your speech in real time and automatically types it into whatever window is currently focused.
- **👁️ Screen Vision**: Captures high-speed screenshots in `<10ms` and describes on-screen content or answers questions about what you are viewing.
- **🧠 Zero-Cost Intelligence**: Powered by **FreeLLMAPI** (`http://localhost:3001`), supporting 30+ free providers with zero subscription fees.
- **⌨️ Global Windows Hotkeys**:
  - `F8`: Toggle instant dictation on/off.
  - `F9`: Expand/collapse the Dynamic Island drawer.
  - `F10`: Analyze active screen content with Vision AI.

---

## 🛠️ System Architecture

```mermaid
graph TD
    User([User Voice / Keyboard / Mouse]) --> Island[Nixi Dynamic Island UI - PyQt6]
    Island --> Core[Main Controller - nixi/main.py]

    subgraph Audio Engine
        AudioCap[Audio Capture & VAD] --> STT[Speech-to-Text / Whisper]
        STT --> Core
        TTS[Streaming Neural TTS - edge-tts / sounddevice] <-- Core
    end

    subgraph Vision & Execution
        Core --> Screen[Screen Reader - MSS / Bilinear Scale]
        Core --> BrowserAgent[Browser & Screen Execution Agent]
        BrowserAgent --> AutoGUI[PyAutoGUI & PyPerclip Injection]
    end

    subgraph Intelligence
        Core --> FreeLLM[FreeLLMAPI Gateway - http://127.0.0.1:3001]
    end
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Windows 10 / 11**
- **Python 3.10+** (ensure `python` is added to your system `PATH`)
- **Node.js 18+** (for the local FreeLLMAPI gateway)

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/Naserkhan07/AI-assistant.git
cd AI-assistant
```

Run the automated setup script in PowerShell:
```powershell
.\setup.ps1
```
This script creates a virtual environment, installs Python dependencies, configures `.env`, and sets up FreeLLMAPI.

### 3. Launching Nixi
Start the assistant anytime with:
```powershell
.\start.ps1
```
The floating Dynamic Island capsule will appear at the top-center of your screen.

---

## ⚙️ Configuration (`.env`)

Copy `.env.example` to `.env`:
```env
FREELLMAPI_URL=http://127.0.0.1:3001/v1
FREELLMAPI_KEY=your-freellmapi-key
FREELLMAPI_MODEL=auto:fast

ASSISTANT_NAME=Nixi
USER_NAME=Sir

TTS_ENGINE=edge-tts
TTS_VOICE=en-US-AvaNeural
STT_ENGINE=google
```

---

## ⌨️ Shortcuts & Commands

| Trigger / Shortcut | Action |
|---|---|
| **Hover on Capsule** | Expands the Dynamic Island drawer |
| **`F8`** | Toggle dictation mode (types voice directly into focused window) |
| **`F9`** | Expand / Collapse the drawer |
| **`F10`** | Quick screen vision analysis |
| *"Fill these boxes"* | Auto-detects and populates active form fields (ID, Name, Description) |
| *"Open [app]"* | Launches any Windows desktop application (e.g. `open chrome`, `open notepad`) |
| *"Set timer for 5 minutes"* | Runs countdown timer with auditory chime alert |

---

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
