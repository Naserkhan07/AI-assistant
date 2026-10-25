"""Nixi Agent Package — lazy, headless-safe."""
from .memory import AgentMemory as AgentMemory

try:
    from .tools_registry import AgentToolsRegistry as AgentToolsRegistry
except ImportError:
    AgentToolsRegistry = None  # type: ignore
try:
    from .react_planner import ReActPlanner as ReActPlanner, is_complex_agent_goal as is_complex_agent_goal
except ImportError:
    ReActPlanner = None  # type: ignore
    is_complex_agent_goal = lambda x: False  # type: ignore
try:
    from .background_daemons import BatteryGuardianDaemon as BatteryGuardianDaemon, ClipboardWatcherDaemon as ClipboardWatcherDaemon, DailyBriefingDaemon as DailyBriefingDaemon
except ImportError:
    BatteryGuardianDaemon = ClipboardWatcherDaemon = DailyBriefingDaemon = None  # type: ignore
try:
    from .vision_copilot import VisionCopilot as VisionCopilot
except ImportError:
    VisionCopilot = None  # type: ignore
try:
    from .knowledge import KnowledgeStore as KnowledgeStore
except ImportError:
    KnowledgeStore = None  # type: ignore
