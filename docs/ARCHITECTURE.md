# Architecture
GUI: PyQt6 Dynamic Island -> Bridge signals -> NixiApp orchestrator
LLM: NixiLLMClient (freellmapi/openai/ollama/offline) with vision + tool_loop
Memory: SQLite (facts/tasks/conversations) + KnowledgeStore (FTS5 RAG)
Audio: AudioCapture (VAD) -> STT (whisper/google) -> WakeWord + VoiceGate -> TTS (edge-tts/SAPI with profiles)
Vault: nixi/security/vault.py (Fernet/keyring)
Automation: MacroRecorder + BrowserController (Playwright or vision fallback)
API: ThreadingHTTPServer at /health,/chat,/command,/audit,/timeline
i18n: nixi/i18n en/hi/hinglish
