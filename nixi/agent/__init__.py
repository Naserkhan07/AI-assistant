"""
Nixi Autonomous AI Agent Architecture
Pillars:
1. Desktop & OS Agency (Computer-Use)
2. Web & Browser Agency (Agent-Reach + Exa)
3. Developer & Code Agency (Self-Healing Runner & Scaffolder)
4. ReAct Reasoning Loop (Goal Decomposition)
5. Persistent Long-Term Memory (SQLite & RAG)
6. Proactive Background Daemons (Battery, Clipboard, Schedule)
7. Multi-Modal Vision Co-Pilot (Live Screen Awareness)
"""
from .memory import AgentMemory
from .tools_registry import AgentToolsRegistry
from .react_planner import ReActPlanner, is_complex_agent_goal
from .background_daemons import BatteryGuardianDaemon, ClipboardWatcherDaemon, DailyBriefingDaemon
from .vision_copilot import VisionCopilot

__all__ = [
    "AgentMemory",
    "AgentToolsRegistry",
    "ReActPlanner",
    "is_complex_agent_goal",
    "BatteryGuardianDaemon",
    "ClipboardWatcherDaemon",
    "DailyBriefingDaemon",
    "VisionCopilot",
]
