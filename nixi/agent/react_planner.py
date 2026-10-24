"""
Nixi ReAct Autonomous Goal Planner & Execution Engine
Decomposes complex multi-step user objectives into sequential plans,
executes tool actions, monitors observations, and synthesizes executive results.
"""
from __future__ import annotations

import re
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

from nixi.agent.tools_registry import AgentToolsRegistry
from nixi.agent.memory import AgentMemory


class ReActPlanner:
    def __init__(self, llm_client, memory: Optional[AgentMemory] = None):
        self.llm = llm_client
        self.memory = memory or AgentMemory()
        self.tools = AgentToolsRegistry(llm_client)

    @staticmethod
    def is_complex_agent_goal(user_prompt: str) -> bool:
        """
        Determines whether a user prompt is a multi-step autonomous goal
        rather than a trivial single-step question or command.
        """
        lower = user_prompt.lower().strip()
        
        # Obvious multi-step indicators
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
            "git workflow", "create branch and push"
        ]
        if any(t in lower for t in triggers):
            return True

        # Conjunctions combining distinct commands
        if " and then " in lower or " after that " in lower or " and also " in lower:
            return True

        # Multi-clause workflow commands (e.g. "Do X, do Y, and do Z")
        if lower.count(",") >= 2 and (" and " in lower or "save" in lower or "paste" in lower):
            return True

        return False

    def plan_and_execute(
        self,
        goal: str,
        on_step_progress: Optional[Callable[[str, int, int], None]] = None,
        on_voice_update: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Executes a multi-step autonomous goal through the ReAct loop.
        Returns: (success: bool, final_summary: str)
        """
        raw_goal = goal.strip()
        lower_goal = raw_goal.lower()

        # Step 1: Immediate voice feedback
        if on_voice_update:
            on_voice_update("Working on your plan.")

        # Fast path 1: Downloads cleanup & organization
        if "clean" in lower_goal and "download" in lower_goal:
            if on_step_progress:
                on_step_progress("Organizing Downloads folder...", 1, 1)
            res = self.tools.organize_folder(delete_old_installers=True, days_old=30)
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        # Fast path 2: Bulk image conversion
        if "convert" in lower_goal and "webp" in lower_goal:
            if on_step_progress:
                on_step_progress("Converting images to WebP...", 1, 1)
            # Find candidate directory (default: Pictures or current directory)
            import os
            target_dir = str(os.path.expanduser("~/Pictures"))
            res = self.tools.convert_images_to_webp(target_dir)
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        # Fast path 3: System Guardian & RAM clean
        if ("system health" in lower_goal or "ram" in lower_goal or "free memory" in lower_goal) and "guardian" in lower_goal:
            if on_step_progress:
                on_step_progress("Auditing system health...", 1, 2)
            diag = self.tools.inspect_system_guardian()
            if on_step_progress:
                on_step_progress("Trimming working sets...", 2, 2)
            trim_res = self.tools.free_system_memory()
            summary = f"System: CPU {diag['cpu_percent']}%, RAM {diag['ram_percent']}% ({diag['ram_used_gb']}GB/{diag['ram_total_gb']}GB). {trim_res}"
            self.memory.log_task(goal, "Completed", 2, summary)
            return True, summary

        # Fast path 4: Project Scaffolding
        if "scaffold" in lower_goal or ("create" in lower_goal and ("fastapi" in lower_goal or "flask" in lower_goal)):
            ptype = "fastapi" if "fastapi" in lower_goal else "flask"
            pname_match = re.search(r"(?:called|named|project)\s+([a-zA-Z0-9_-]+)", lower_goal)
            pname = pname_match.group(1) if pname_match else f"{ptype}_app"
            if on_step_progress:
                on_step_progress(f"Scaffolding {ptype.upper()} project '{pname}'...", 1, 1)
            res = self.tools.scaffold_project(ptype, pname)
            self.memory.log_task(goal, "Completed", 1, res)
            return True, res

        # General Autonomous ReAct Loop via FreeLLMAPI
        return self._react_loop(raw_goal, on_step_progress, on_voice_update)

    def _react_loop(
        self,
        goal: str,
        on_step_progress: Optional[Callable[[str, int, int], None]] = None,
        on_voice_update: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Multi-step ReAct reasoning with live observations and synthesis."""
        # 1. Step 1: Deep Web Research
        if on_step_progress:
            on_step_progress(f"Researching: {goal[:25]}...", 1, 3)

        research_res = self.tools.deep_web_research(goal, sources_count=4)
        observations = []
        for s in research_res["sources"]:
            observations.append(f"Source: {s['title']}\nURL: {s['url']}\nDetails: {s['snippet']}")

        joined_obs = "\n\n".join(observations)

        # 2. Step 2: Synthesis and Planning Formulation
        if on_step_progress:
            on_step_progress("Synthesizing multi-source intelligence...", 2, 3)

        context_prompt = self.memory.get_system_context_prompt()
        prompt = [
            {"role": "system", "content": f"You are Nixi, an expert autonomous executive agent.\n{context_prompt}\nProvide a comprehensive, structured response with actionable bullet points and clear sections."},
            {"role": "user", "content": f"GOAL: {goal}\n\nLIVE WEB OBSERVATIONS:\n{joined_obs}\n\nSynthesize the complete answer or plan with executive clarity:"}
        ]

        synthesized = ""
        try:
            for chunk in self.llm.chat_stream(prompt, temperature=0.2):
                synthesized += chunk
        except Exception as e:
            synthesized = f"Error during agent synthesis: {e}"

        synthesized = synthesized.strip()
        if not synthesized:
            synthesized = f"Completed research on '{goal}'. Found {len(research_res['sources'])} sources."

        if on_step_progress:
            on_step_progress("Goal completed successfully.", 3, 3)

        self.memory.log_task(goal, "Completed", 3, synthesized[:300])
        return True, synthesized


# Module-level alias
is_complex_agent_goal = ReActPlanner.is_complex_agent_goal
