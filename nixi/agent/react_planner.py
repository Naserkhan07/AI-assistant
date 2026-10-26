"""ReAct planner — goal decomposition with correct callback contract."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from nixi.agent.tools_registry import AgentToolsRegistry
from nixi.agent.memory import AgentMemory


class ReActPlanner:
    def __init__(self, llm_client=None, memory: AgentMemory | None = None):
        self.llm = llm_client
        self.memory = memory or AgentMemory()
        self.tools = AgentToolsRegistry(llm_client)
        self.permissions = None
        self.undo_manager = None

    def _authorize_change(self, action: str, args: dict) -> tuple[bool, str]:
        if self.permissions is None:
            return True, ""
        from nixi.security.permissions import RiskLevel
        decision = self.permissions.authorize(action, RiskLevel.HIGH, args)
        return decision.allowed, decision.reason

    @staticmethod
    def is_complex_agent_goal(prompt: str) -> bool:
        lower = prompt.lower().strip()
        triggers = [
            "plan a ", "plan the ", "trip to", "itinerary",
            "clean up my downloads", "clean downloads", "organize my downloads",
            "convert all", "bulk convert",
            "open notepad", "paste the latest clipboard", "paste clipboard",
            "format it into", "save it to my desktop", "meeting_notes",
            "scaffold a ", "create a new fastapi", "create a new flask",
            "research and summarize", "deep research", "compare prices",
            "check system health and", "inspect memory and", "kill rogue",
            "self-healing", "write a script that", "write code that",
            "git workflow", "create branch and push",
        ]
        if any(t in lower for t in triggers):
            return True
        if " and then " in lower or " after that " in lower or " and also " in lower:
            return True
        if lower.count(",") >= 2 and (" and " in lower or "save" in lower or "paste" in lower):
            return True
        return False

    def plan_and_execute(
        self,
        goal: str,
        on_step_progress: Callable[[int, int, str], None] | None = None,
        on_voice_update: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Execute a multi-step goal. Returns (success, summary).
        Callback contract: on_step_progress(current, total, label) — matches main.py.
        """
        raw_goal = goal.strip()
        lower_goal = raw_goal.lower()

        if on_voice_update:
            on_voice_update("Working on your plan.")

        # Fast path 1: Downloads cleanup
        if "clean" in lower_goal and "download" in lower_goal:
            allowed, reason = self._authorize_change("organize_folder", {"folder": "Downloads", "delete": False})
            if not allowed:
                return False, f"Not run: {reason}"
            if on_step_progress:
                on_step_progress(1, 1, "Organizing Downloads folder (undoable; no deletions)...")
            res = self.tools.organize_folder(
                delete_old_installers=False, undo_manager=self.undo_manager
            )
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        # Fast path 2: Bulk image conversion
        if "convert" in lower_goal and "webp" in lower_goal:
            allowed, reason = self._authorize_change("convert_images_to_webp", {"folder": "Pictures", "delete_original": False})
            if not allowed:
                return False, f"Not run: {reason}"
            if on_step_progress:
                on_step_progress(1, 1, "Converting images to WebP...")
            import os
            target_dir = str(Path.home() / "Pictures")
            res = self.tools.convert_images_to_webp(target_dir)
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        # Fast path 3: System health & RAM
        if (("system health" in lower_goal or "ram" in lower_goal or "free memory" in lower_goal)
                and "guardian" in lower_goal):
            if on_step_progress:
                on_step_progress(1, 2, "Auditing system health...")
            diag = self.tools.inspect_system_guardian()
            if on_step_progress:
                on_step_progress(2, 2, "Trimming working sets...")
            trim_res = self.tools.free_system_memory()
            summary = f"System: CPU {diag['cpu_percent']}%, RAM {diag['ram_percent']}% ({diag['ram_used_gb']}GB/{diag['ram_total_gb']}GB). {trim_res}"
            self.memory.log_task(goal, "Completed", 2, summary)
            return True, summary

        # Fast path 4: Scaffolding
        if "scaffold" in lower_goal or ("create" in lower_goal and ("fastapi" in lower_goal or "flask" in lower_goal)):
            allowed, reason = self._authorize_change("scaffold_project", {"goal": raw_goal})
            if not allowed:
                return False, f"Not run: {reason}"
            ptype = "fastapi" if "fastapi" in lower_goal else "flask"
            m = re.search(r"(?:called|named|project)\s+([a-zA-Z0-9_-]+)", lower_goal)
            pname = m.group(1) if m else f"{ptype}_app"
            if on_step_progress:
                on_step_progress(1, 1, f"Scaffolding {ptype.upper()} project '{pname}'...")
            res = self.tools.scaffold_project(ptype, pname)
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        return self._react_loop(raw_goal, on_step_progress, on_voice_update)

    def _react_loop(
        self,
        goal: str,
        on_step_progress: Callable[[int, int, str], None] | None = None,
        on_voice_update: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        if on_step_progress:
            on_step_progress(1, 3, f"Researching: {goal[:25]}...")

        research_res = self.tools.deep_web_research(goal, sources_count=4)
        observations: list[str] = []
        for s in research_res.get("sources", []):
            observations.append(f"Source: {s['title']}\nURL: {s['url']}\nDetails: {s['snippet']}")
        joined_obs = "\n\n".join(observations) if observations else "No web sources available."

        if on_step_progress:
            on_step_progress(2, 3, "Synthesizing multi-source intelligence...")

        context_prompt = self.memory.get_system_context_prompt()
        prompt = [
            {"role": "system", "content": f"You are Nixi, an expert autonomous agent.\n{context_prompt}\nProvide a comprehensive, structured response."},
            {"role": "user", "content": f"GOAL: {goal}\n\nLIVE WEB OBSERVATIONS:\n{joined_obs}\n\nSynthesize the complete answer:"},
        ]
        synthesized = ""
        try:
            for chunk in self.llm.chat_stream(prompt, temperature=0.2):
                synthesized += chunk
        except Exception as exc:
            synthesized = f"Error during synthesis: {exc}"
        synthesized = synthesized.strip() or f"Completed research on '{goal}'. Found {len(research_res.get('sources',[]))} sources."

        if on_step_progress:
            on_step_progress(3, 3, "Goal completed successfully.")

        self.memory.log_task(goal, "Completed", 3, synthesized[:300])
        return True, synthesized


is_complex_agent_goal = ReActPlanner.is_complex_agent_goal
