try:
    from .audio_capture import AudioCapture
    from .stt import SpeechTranscriber
    from .tts import NixiTTS
    from .wake_word import WakeWordDetector
except ImportError:
    AudioCapture=SpeechTranscriber=NixiTTS=WakeWordDetector=None
