"""
react_orchestrator.py
ReAct (Reason + Act) Orchestrator — the core Agentic AI loop.

The LLM autonomously:
  1. THINKS about what to do next given current observations
  2. ACTS by calling a tool from the registry
  3. OBSERVES the result
  4. Repeats until it reaches a final ANSWER

This replaces the hardcoded pipeline with an LLM-driven decision loop
that can adapt its strategy based on what data is available.
"""

import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from agents.agent_memory import AgentMemory, record_decision
from agents.tool_registry import ToolRegistry, build_default_registry

MAX_ITERATIONS = 12  # safety cap on the ReAct loop

# Model fallback chain — tries each in order when quota is exhausted.
# We prioritize Gemma 3 models here because Google's free tier currently provides
# massive limits for them (30 RPM, 14.4k RPD) compared to Gemini Flash (5-10 RPM, 20 RPD).
GEMINI_MODEL_CHAIN = ["gemma-3-27b-it", "gemma-3-12b-it", "gemma-3-4b-it", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def _get_llm_client():
    """Return (client_type, client) — supports Gemini (AIza*) and Claude (sk-ant*)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key.startswith("AIza"):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            return "gemini", client
        except ImportError:
            return None, None
    elif api_key.startswith("sk-ant"):
        try:
            import anthropic
            return "claude", anthropic.Anthropic(api_key=api_key)
        except ImportError:
            return None, None
    return None, None


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """Return True if the error is a daily quota limit (not a per-minute RPM limit)."""
    msg = str(exc)
    return (
        "GenerateRequestsPerDay" in msg
        or "PerDayPer" in msg
        or "daily" in msg.lower()
    )


def _extract_retry_delay(exc: Exception) -> float:
    """Pull the retryDelay seconds out of a Gemini 429 exception, default 5s."""
    try:
        msg = str(exc)
        import re
        m = re.search(r"retry[_\s]delay[^0-9]*(\d+)", msg, re.IGNORECASE)
        if m:
            return min(float(m.group(1)), 60.0)  # cap at 60s
    except Exception:
        pass
    return 5.0


def _call_llm(client_type: str, client, system: str, messages: list[dict],
              _exhausted: set | None = None) -> str:
    """
    Call the LLM with automatic model fallback for Gemini quota errors.
    - Daily quota exhausted: immediately tries next model (no point waiting).
    - Per-minute (RPM) quota: waits the retry delay then tries next model.
    - _exhausted: optional set of model names already known to be daily-exhausted
      (shared across calls in a session to avoid redundant retries).
    Raises only when all models are exhausted.
    """
    import time

    if _exhausted is None:
        _exhausted = set()

    if client_type == "gemini":
        from google.genai import types
        contents = []
        for i, m in enumerate(messages):
            role = "user" if m["role"] == "user" else "model"
            text_content = m["content"]
            if i == 0 and system:
                text_content = f"{system}\n\n{text_content}"
            contents.append(types.Content(role=role, parts=[types.Part(text=text_content)]))

        last_exc = None
        for model_name in GEMINI_MODEL_CHAIN:
            if model_name in _exhausted:
                continue  # skip models we already know are daily-exhausted
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        max_output_tokens=1024,
                    ),
                )
                return resp.text
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    if _is_daily_quota_exhausted(e):
                        _exhausted.add(model_name)
                        print(f"[ReActOrchestrator] {model_name} daily quota exhausted — trying next model")
                    else:
                        delay = _extract_retry_delay(e)
                        print(f"[ReActOrchestrator] {model_name} RPM limit — waiting {delay:.0f}s then trying next model")
                        time.sleep(delay)
                    continue
                raise  # non-quota error — propagate immediately

        raise RuntimeError(f"All Gemini models exhausted. Last error: {last_exc}")

    elif client_type == "claude":
        resp = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return resp.content[0].text

    raise RuntimeError("No LLM client available")


SYSTEM_PROMPT = """You are an autonomous credit assessment agent. You reason step-by-step and use tools to evaluate borrowers.

You operate in a ReAct loop:
- THOUGHT: reason about what you know and what you need to do next
- ACTION: call exactly one tool with JSON arguments
- OBSERVATION: you will receive the tool result
- Repeat until you have enough information to give a FINAL ANSWER

Available tools:
{tools}

Rules:
- Always start by fetching borrower data
- For thin-file borrowers (no bank data), rely heavily on alternative scores
- Always check fairness before finalizing a decision
- If bias is detected, escalate APPROVE decisions to ESCALATE
- If confidence (composite_score/1000) < 0.70, escalate APPROVE to ESCALATE
- Generate an explanation report as the last step
- Output FINAL_ANSWER as a JSON object when done

Format your response as:
THOUGHT: <your reasoning>
ACTION: <tool_name>
ARGS: <json object of arguments>

Or when done:
THOUGHT: <final reasoning>
FINAL_ANSWER: <json object with all results>
"""


def _parse_llm_response(text: str) -> dict:
    """Parse THOUGHT/ACTION/ARGS or FINAL_ANSWER from LLM output."""
    lines = text.strip().split("\n")
    result = {"thought": "", "action": None, "args": {}, "final_answer": None}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("THOUGHT:"):
            result["thought"] = line[len("THOUGHT:"):].strip()
        elif line.startswith("ACTION:"):
            result["action"] = line[len("ACTION:"):].strip()
        elif line.startswith("ARGS:"):
            # Collect multi-line JSON
            json_str = line[len("ARGS:"):].strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith(("THOUGHT:", "ACTION:", "FINAL_ANSWER:")):
                json_str += "\n" + lines[j]
                j += 1
            try:
                result["args"] = json.loads(json_str)
            except json.JSONDecodeError:
                result["args"] = {}
            i = j
            continue
        elif line.startswith("FINAL_ANSWER:"):
            json_str = line[len("FINAL_ANSWER:"):].strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("THOUGHT:"):
                json_str += "\n" + lines[j]
                j += 1
            try:
                result["final_answer"] = json.loads(json_str)
            except json.JSONDecodeError:
                result["final_answer"] = {"raw": json_str}
            i = j
            continue
        i += 1

    return result


def _fallback_pipeline(borrower_id: str, registry: ToolRegistry, memory: AgentMemory) -> dict:
    """
    Deterministic fallback pipeline used when LLM is unavailable.
    Mirrors the original OrchestratorAgent logic but routes through the tool registry
    and records every step in AgentMemory.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor

    start = time.time()

    memory.add_thought("ReActOrchestrator", "LLM unavailable — running deterministic fallback pipeline")

    # Step 1: Fetch data
    memory.add_thought("ReActOrchestrator", f"Fetching data for {borrower_id}")
    data = registry.call("fetch_borrower_data", borrower_id=borrower_id)
    memory.add_action("ReActOrchestrator", "fetch_borrower_data", {"borrower_id": borrower_id}, f"completeness={data['data_completeness']:.0%}")
    memory.add_observation("borrower_data", data)

    # Step 2: Score in parallel
    memory.add_thought("ReActOrchestrator", "Running financial and alternative scoring in parallel")
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_fin = ex.submit(registry.call, "compute_financial_score", bank_data=data["bank_data"], profile=data["profile"])
        f_alt = ex.submit(registry.call, "compute_alternative_score",
                          utility_data=data["utility_data"],
                          mobile_data=data["mobile_data"],
                          has_bank_data=data["bank_data"] is not None)
        fin = f_fin.result()
        alt = f_alt.result()

    memory.add_action("ReActOrchestrator", "compute_financial_score", {}, f"score={fin['financial_score']}")
    memory.add_action("ReActOrchestrator", "compute_alternative_score", {}, f"score={alt['alternative_score']}")
    memory.add_observation("financial_result", fin)
    memory.add_observation("alternative_result", alt)

    # Step 3: Risk decision
    memory.add_thought("ReActOrchestrator", "Computing composite risk decision")
    risk = registry.call("make_risk_decision",
                         financial_score=fin["financial_score"],
                         alternative_score=alt["alternative_score"],
                         is_underbanked=fin["is_underbanked"])
    memory.add_action("ReActOrchestrator", "make_risk_decision", {}, f"decision={risk['decision']} score={risk['composite_score']}")
    memory.add_observation("risk_result", risk)

    # Step 4: Fairness + Explanation in parallel
    memory.add_thought("ReActOrchestrator", "Running fairness check and generating explanation in parallel")
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_fair = ex.submit(registry.call, "check_fairness",
                           decision=risk["decision"],
                           composite_score=risk["composite_score"],
                           profile=data["profile"])
        f_exp = ex.submit(registry.call, "generate_explanation",
                          borrower_name=data["name"],
                          composite_score=risk["composite_score"],
                          financial_score=fin["financial_score"],
                          alternative_score=alt["alternative_score"],
                          decision=risk["decision"],
                          risk_tier=risk["risk_tier"],
                          is_underbanked=fin["is_underbanked"],
                          shap_summary=fin.get("shap_summary", {}),
                          features=fin.get("features", {}))
        fairness = f_fair.result()
        explanation = f_exp.result()

    memory.add_action("ReActOrchestrator", "check_fairness", {}, f"bias_detected={fairness['bias_detected']}")
    memory.add_action("ReActOrchestrator", "generate_explanation", {}, f"report_len={len(explanation.get('report',''))}")
    memory.add_observation("fairness_result", fairness)
    memory.add_observation("explanation_result", explanation)

    # Step 5: Override logic
    final_decision = risk["decision"]
    confidence = risk["confidence"]
    override_reason = None

    if fairness["bias_detected"] and final_decision == "APPROVE":
        final_decision = "ESCALATE"
        override_reason = f"Bias detected — escalating APPROVE→ESCALATE"
        memory.add_thought("ReActOrchestrator", override_reason)
    elif confidence < 0.70 and final_decision == "APPROVE":
        final_decision = "ESCALATE"
        override_reason = f"Low confidence ({confidence:.2f}) — escalating APPROVE→ESCALATE"
        memory.add_thought("ReActOrchestrator", override_reason)

    processing_ms = int((time.time() - start) * 1000)

    # Build agent_pipeline for UI compatibility
    agent_pipeline = [
        {"agent": "DataCollectionAgent", "status": "done",
         "output": f"Completeness: {data['data_completeness']:.0%} | Sources: {sum(data['sources_available'].values())}/3"},
        {"agent": "FinancialScoringAgent", "status": "done",
         "output": f"Financial score: {fin['financial_score']}"},
        {"agent": "AlternativeDataAgent", "status": "done",
         "output": f"Alternative score: {alt['alternative_score']}"},
        {"agent": "RiskDecisionAgent", "status": "done",
         "output": f"Decision: {risk['decision']} | Score: {risk['composite_score']} | {risk['risk_tier']}"},
        {"agent": "ExplainabilityAgent", "status": "done",
         "output": f"Report generated ({len(explanation.get('report', ''))} chars)"},
        {"agent": "BiasFairnessAgent", "status": "done",
         "output": f"Bias detected: {fairness['bias_detected']}"},
    ]
    if override_reason:
        agent_pipeline.append({
            "agent": "ReActOrchestrator",
            "status": "override",
            "output": override_reason,
        })

    record_decision(borrower_id, final_decision, risk["composite_score"],
                    memory.get_context_summary())

    return {
        "borrower_id": borrower_id,
        "borrower_name": data["name"],
        "scenario": data["scenario"],
        "composite_score": risk["composite_score"],
        "risk_tier": risk["risk_tier"],
        "decision": final_decision,
        "credit_limit": risk["credit_limit"],
        "interest_rate_range": risk["interest_rate_range"],
        "financial_score": fin["financial_score"],
        "alternative_score": alt["alternative_score"],
        "is_underbanked": fin["is_underbanked"],
        "key_strengths": explanation.get("key_strengths", []),
        "key_concerns": explanation.get("key_concerns", []),
        "report": explanation.get("report", ""),
        "bias_detected": fairness["bias_detected"],
        "fairness_metrics": fairness["fairness_metrics"],
        "processing_time_ms": processing_ms,
        "data_completeness": data["data_completeness"],
        "shap_summary": explanation.get("shap_summary", fin.get("shap_summary", {})),
        "score_breakdown": risk.get("score_breakdown", {}),
        "alternative_signals": alt.get("signals", {}),
        "agent_pipeline": agent_pipeline,
        "confidence": confidence,
        "reasoning_trace": memory.to_trace(),
        "agentic_mode": "fallback_pipeline",
    }


class ReActOrchestrator:
    """
    Agentic orchestrator using the ReAct (Reason + Act) loop.

    The LLM autonomously decides which tools to call and in what order,
    adapting its strategy based on what data is available for each borrower.
    Falls back to a deterministic pipeline if the LLM is unavailable.
    """

    def __init__(self):
        self.registry = build_default_registry()
        self.client_type, self.client = _get_llm_client()

    def run(self, borrower_id: str) -> dict:
        memory = AgentMemory()

        if self.client is None:
            return _fallback_pipeline(borrower_id, self.registry, memory)

        return self._react_loop(borrower_id, memory)

    def _react_loop(self, borrower_id: str, memory: AgentMemory) -> dict:
        """Run the LLM-driven ReAct loop."""
        import time
        start = time.time()

        tools_desc = json.dumps(self.registry.list_tools(), indent=2)
        system = SYSTEM_PROMPT.format(tools=tools_desc)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Assess creditworthiness for borrower_id='{borrower_id}'.\n"
                    f"Use the available tools to gather data, score, check fairness, "
                    f"and produce a final credit decision with explanation.\n"
                    f"Return FINAL_ANSWER as a JSON object with keys: "
                    f"decision, composite_score, risk_tier, credit_limit, interest_rate_range, "
                    f"financial_score, alternative_score, is_underbanked, bias_detected, "
                    f"key_strengths, key_concerns, report, confidence, reasoning_summary."
                ),
            }
        ]

        observations: dict = {}
        iterations = 0
        _exhausted_models: set = set()  # track daily-exhausted models across the loop

        while iterations < MAX_ITERATIONS:
            iterations += 1

            try:
                llm_text = _call_llm(self.client_type, self.client, system, messages,
                                     _exhausted=_exhausted_models)
            except Exception as e:
                memory.add_thought("ReActOrchestrator", f"LLM error: {e} — switching to fallback")
                return _fallback_pipeline(borrower_id, self.registry, memory)

            parsed = _parse_llm_response(llm_text)
            memory.add_thought("ReActOrchestrator", parsed["thought"])

            # ── FINAL ANSWER ──────────────────────────────────────────────────
            if parsed["final_answer"] is not None:
                fa = parsed["final_answer"]
                processing_ms = int((time.time() - start) * 1000)

                # Merge LLM answer with any richer data we collected in observations
                data = observations.get("borrower_data", {})
                fin = observations.get("financial_result", {})
                alt = observations.get("alternative_result", {})
                risk = observations.get("risk_result", {})
                fairness = observations.get("fairness_result", {})
                explanation = observations.get("explanation_result", {})

                agent_pipeline = _build_pipeline_from_memory(memory)

                record_decision(
                    borrower_id,
                    fa.get("decision", risk.get("decision", "UNKNOWN")),
                    fa.get("composite_score", risk.get("composite_score", 0)),
                    parsed["thought"],
                )

                ks = fa.get("key_strengths", explanation.get("key_strengths", []))
                kc = fa.get("key_concerns", explanation.get("key_concerns", []))
                if isinstance(ks, str): ks = [ks]
                if isinstance(kc, str): kc = [kc]

                return {
                    "borrower_id": borrower_id,
                    "borrower_name": data.get("name", fa.get("borrower_name", borrower_id)),
                    "scenario": data.get("scenario", ""),
                    "composite_score": fa.get("composite_score", risk.get("composite_score", 0)),
                    "risk_tier": fa.get("risk_tier", risk.get("risk_tier", "")),
                    "decision": fa.get("decision", risk.get("decision", "UNKNOWN")),
                    "credit_limit": fa.get("credit_limit", risk.get("credit_limit", 0)),
                    "interest_rate_range": fa.get("interest_rate_range", risk.get("interest_rate_range", "N/A")),
                    "financial_score": fa.get("financial_score", fin.get("financial_score", 0)),
                    "alternative_score": fa.get("alternative_score", alt.get("alternative_score", 0)),
                    "is_underbanked": fa.get("is_underbanked", fin.get("is_underbanked", False)),
                    "key_strengths": ks,
                    "key_concerns": kc,
                    "report": fa.get("report", explanation.get("report", "")),
                    "bias_detected": fa.get("bias_detected", fairness.get("bias_detected", False)),
                    "fairness_metrics": fairness.get("fairness_metrics", {}),
                    "processing_time_ms": processing_ms,
                    "data_completeness": data.get("data_completeness", 1.0),
                    "shap_summary": explanation.get("shap_summary", fin.get("shap_summary", {})),
                    "score_breakdown": risk.get("score_breakdown", {}),
                    "alternative_signals": alt.get("signals", {}),
                    "agent_pipeline": agent_pipeline,
                    "confidence": fa.get("confidence", risk.get("confidence", 0.5)),
                    "reasoning_trace": memory.to_trace(),
                    "agentic_mode": "react_llm",
                    "reasoning_summary": fa.get("reasoning_summary", parsed["thought"]),
                }

            # ── TOOL CALL ─────────────────────────────────────────────────────
            tool_name = parsed.get("action")
            tool_args = parsed.get("args", {})

            if not tool_name:
                # LLM gave unexpected output — append and retry
                messages.append({"role": "assistant", "content": llm_text})
                messages.append({
                    "role": "user",
                    "content": "Please continue. Use THOUGHT/ACTION/ARGS format or provide FINAL_ANSWER.",
                })
                continue

            try:
                tool_result = self.registry.call(tool_name, **tool_args)
                obs_str = json.dumps(tool_result, default=str)[:2000]  # cap size
                memory.add_action("ReActOrchestrator", tool_name, tool_args, obs_str[:200])

                # Store rich observations for final answer assembly
                obs_key_map = {
                    "fetch_borrower_data": "borrower_data",
                    "compute_financial_score": "financial_result",
                    "compute_alternative_score": "alternative_result",
                    "make_risk_decision": "risk_result",
                    "check_fairness": "fairness_result",
                    "generate_explanation": "explanation_result",
                }
                if tool_name in obs_key_map:
                    observations[obs_key_map[tool_name]] = tool_result

            except Exception as e:
                obs_str = f"ERROR: {e}"
                memory.add_thought("ReActOrchestrator", f"Tool {tool_name} failed: {e}")

            messages.append({"role": "assistant", "content": llm_text})
            messages.append({
                "role": "user",
                "content": f"OBSERVATION: {obs_str}\n\nContinue your assessment.",
            })

        # Max iterations reached — fall back
        memory.add_thought("ReActOrchestrator", "Max iterations reached — running fallback pipeline")
        return _fallback_pipeline(borrower_id, self.registry, memory)


def _build_pipeline_from_memory(memory: AgentMemory) -> list[dict]:
    """Convert memory action trace into agent_pipeline format for UI."""
    pipeline = []
    tool_to_agent = {
        "fetch_borrower_data": "DataCollectionAgent",
        "compute_financial_score": "FinancialScoringAgent",
        "compute_alternative_score": "AlternativeDataAgent",
        "make_risk_decision": "RiskDecisionAgent",
        "generate_explanation": "ExplainabilityAgent",
        "check_fairness": "BiasFairnessAgent",
    }
    seen = set()
    for step in memory.steps:
        if step["type"] == "action":
            agent_name = tool_to_agent.get(step["tool"], step["tool"])
            if agent_name not in seen:
                seen.add(agent_name)
                pipeline.append({
                    "agent": agent_name,
                    "status": "done",
                    "output": str(step["result"])[:120],
                })
        elif step["type"] == "thought" and "override" in step["content"].lower():
            pipeline.append({
                "agent": "ReActOrchestrator",
                "status": "override",
                "output": step["content"],
            })
    return pipeline
