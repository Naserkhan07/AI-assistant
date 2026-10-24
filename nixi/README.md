# ✨ Nixi — AI Desktop Assistant

An ultra-sleek, lightweight Windows AI assistant inspired by **HeyNixi**. Unlike large windowed assistants with bulky avatars, Nixi lives as a **minimal, translucent floating pill at the top of your screen**.

---

## 🌟 Key Features

| Feature | Description |
|---|---|
| **Minimal Floating Pill** | Stays quietly pinned at the top-center of your screen. Draggable, translucent dark glassmorphism. |
| **Pulsing State Orb** | Visual feedback orb: **Cyan** (Ready), **Violet** (Listening), **Amber** (Dictating), **Pink** (Thinking), **Green** (Speaking). Reacts to voice volume. |
| **Universal App Dictation** | Speak, and Nixi types your words directly into any focused app (Notepad, Word, Discord, Browser, VS Code, etc.). |
| **Screen Reading & Vision** | Click the eye icon (`👁️`) or press `F10` to capture your screen and have FreeLLMAPI vision analyze what's visible. |
| **Slide-Down Chat Drawer** | Press `F9` or click `💬` to expand the conversation drawer with message history, quick chips, and Markdown support. |
| **Voice App Launcher** | Say *"open chrome"*, *"launch notepad"*, *"start calculator"*, or *"open vs code"* to immediately launch desktop apps. |
| **Timers & Reminders** | Say *"set timer for 5 minutes"* or *"remind me in 30 seconds"*. Nixi plays a triple chime and alerts you when time is up. |
| **FreeLLMAPI Integration** | Connects to your local FreeLLMAPI gateway (`http://127.0.0.1:3001/v1`) using free high-performance AI models. |
| **Fast Local TTS & STT** | Windows SAPI5 voice output + local Whisper transcription with zero latency. |

---

## ⌨️ Global Shortcuts

- **`F8`**: Toggle Dictation Mode (types your speech into the active application)
- **`F9`**: Open / Close Chat Drawer
- **`F10`**: Instant Screen Vision Capture & Analysis

---

## 🚀 How to Launch

Simply run the startup script:

```powershell
.\start-nixi.ps1
```

Or run directly with Python:

```powershell
.\app\.venv\Scripts\python.exe nixi\main.py
```
