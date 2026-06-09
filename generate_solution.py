"""Generate lab_solution.md for the multi-agent codelab.

The script runs the completed lab stages once, captures terminal output,
records Mermaid diagrams, and stores the Stage 5 registry/test evidence.
It intentionally does not print or copy secrets from .env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
SOLUTION = ROOT / "lab_solution.md"
PYTHON = sys.executable


def write(text: str = "") -> None:
    with SOLUTION.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text)
        if text and not text.endswith("\n"):
            f.write("\n")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_command(
    label: str,
    args: list[str],
    timeout: int = 180,
    input_text: str | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    write(f"### {label}")
    write()
    write("```powershell")
    write(" ".join(args))
    write("```")
    write()

    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            env=command_env(),
            input=input_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        output = completed.stdout or ""
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + f"\n[TIMEOUT after {timeout}s]\n"
        return_code = -1

    elapsed = time.perf_counter() - start
    write(f"- Return code: `{return_code}`")
    write(f"- Duration: `{elapsed:.2f}s`")
    write()
    write("```text")
    write(output.strip() or "(no output)")
    write("```")
    write()
    return {"return_code": return_code, "duration": elapsed, "output": output}


def http_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return None


def start_service(module: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [PYTHON, "-m", module],
        cwd=ROOT,
        env=command_env(),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def wait_for_url(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if http_json(url, timeout=2.0) is not None:
            return True
        time.sleep(1)
    return False


def registered_agent_names() -> set[str]:
    data = http_json("http://localhost:10000/agents")
    if not data:
        return set()
    return {agent.get("agent_name", "") for agent in data.get("agents", [])}


def run_stage5() -> None:
    write("## Stage 5 - Distributed A2A System")
    write()
    write("### Registry Snapshot")
    write()

    required = {"tax-agent", "compliance-agent", "law-agent", "customer-agent"}
    managed: list[tuple[str, subprocess.Popen[str]]] = []
    using_existing = required.issubset(registered_agent_names())

    if using_existing:
        write("Registry already had all required agents. This run reused the existing VS Code terminal services.")
    else:
        write("Starting temporary Stage 5 services for this solution run.")
        services = [
            ("registry", "registry", "http://localhost:10000/health"),
            ("tax-agent", "tax_agent", "http://localhost:10102/.well-known/agent.json"),
            ("compliance-agent", "compliance_agent", "http://localhost:10103/.well-known/agent.json"),
            ("law-agent", "law_agent", "http://localhost:10101/.well-known/agent.json"),
            ("customer-agent", "customer_agent", "http://localhost:10100/.well-known/agent.json"),
        ]
        for name, module, health_url in services:
            proc = start_service(module)
            managed.append((name, proc))
            wait_for_url(health_url, timeout=35.0)
            time.sleep(1)

    snapshot = http_json("http://localhost:10000/agents")
    write("```json")
    write(json.dumps(snapshot, ensure_ascii=False, indent=2) if snapshot else "Registry unavailable")
    write("```")
    write()

    write("### End-to-End Test and Latency")
    write()
    result = run_command(
        "Stage 5 test_client.py",
        [PYTHON, "test_client.py"],
        timeout=240,
    )
    write(f"Measured client-side latency: `{result['duration']:.2f}s`")
    write()

    write("### Service Logs Captured In This Run")
    write()
    if managed:
        for name, proc in reversed(managed):
            proc.terminate()
        for name, proc in managed:
            try:
                output, _ = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                output, _ = proc.communicate(timeout=10)
            write(f"#### {name}")
            write()
            write("```text")
            write((output or "").strip() or "(no captured service log)")
            write("```")
            write()
    else:
        write(
            "Services were already running in external VS Code terminals, so this script could not capture "
            "their stdout. The file still records the Registry snapshot and `test_client.py` output above."
        )
        write()


def write_static_sections() -> None:
    SOLUTION.write_text("", encoding="utf-8", newline="\n")
    write("# SOLUTION - Batch02 Day9 Multi-Agent MCP/A2A Lab")
    write()
    write(f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`")
    write(f"- Project root: `{ROOT}`")
    write("- LLM config: uses `OPENAI_API_KEY` / `OPENAI_MODEL` through `common/llm.py`; API key is not recorded here.")
    write()

    write("## Graphs")
    write()
    write("### Stage 4 Exercise Graph")
    write()
    write("```mermaid")
    write("flowchart TD")
    write("    START --> law_agent")
    write("    law_agent --> check_routing")
    write("    check_routing --> tax_agent")
    write("    check_routing --> compliance_agent")
    write("    check_routing --> privacy_agent")
    write("    check_routing --> aggregate_results")
    write("    tax_agent --> aggregate_results")
    write("    compliance_agent --> aggregate_results")
    write("    privacy_agent --> aggregate_results")
    write("    aggregate_results --> END")
    write("```")
    write()
    write("### Stage 4 Demo Graph")
    write()
    write("```mermaid")
    write("flowchart TD")
    write("    START --> analyze_law")
    write("    analyze_law --> check_routing")
    write("    check_routing --> call_tax_specialist")
    write("    check_routing --> call_compliance_specialist")
    write("    check_routing --> call_privacy_specialist")
    write("    check_routing --> aggregate")
    write("    call_tax_specialist --> aggregate")
    write("    call_compliance_specialist --> aggregate")
    write("    call_privacy_specialist --> aggregate")
    write("    aggregate --> END")
    write("```")
    write()
    write("### Stage 5 A2A Sequence")
    write()
    write("```mermaid")
    write("sequenceDiagram")
    write("    participant User")
    write("    participant Customer as Customer Agent :10100")
    write("    participant Registry as Registry :10000")
    write("    participant Law as Law Agent :10101")
    write("    participant Tax as Tax Agent :10102")
    write("    participant Compliance as Compliance Agent :10103")
    write("    User->>Customer: Send legal question")
    write("    Customer->>Registry: discover legal_question")
    write("    Registry-->>Customer: Law Agent endpoint")
    write("    Customer->>Law: Delegate via A2A")
    write("    Law->>Registry: discover tax_question")
    write("    Registry-->>Law: Tax Agent endpoint")
    write("    Law->>Registry: discover compliance_question")
    write("    Registry-->>Law: Compliance Agent endpoint")
    write("    par Parallel delegation")
    write("        Law->>Tax: A2A tax analysis")
    write("        Tax-->>Law: tax_result")
    write("    and")
    write("        Law->>Compliance: A2A compliance analysis")
    write("        Compliance-->>Law: compliance_result")
    write("    end")
    write("    Law-->>Customer: aggregated legal answer")
    write("    Customer-->>User: final response")
    write("```")
    write()

    write("## Written Answers")
    write()
    write("### Stage 1")
    write("- `get_llm()` creates a `ChatOpenAI` client configured by environment variables.")
    write("- Messages are a list of `SystemMessage` plus `HumanMessage`.")
    write("- `SystemMessage` sets role/instructions; `HumanMessage` contains the user question.")
    write("- Temperature control was added in `common/llm.py` with `temperature=0.3`.")
    write()
    write("### Stage 2")
    write("- `@tool` wraps Python functions so the LLM can request them through tool calling.")
    write("- `LEGAL_KNOWLEDGE` is a list of dictionaries containing `id`, `keywords`, and `text`.")
    write("- Tools are bound through `llm.bind_tools(tools)` and executed manually from `response.tool_calls`.")
    write("- Added `labor_law` and `check_statute_of_limitations`.")
    write()
    write("### Stage 3")
    write("- `create_react_agent()` replaces the manual tool loop from Stage 2.")
    write("- The agent can Think, Act, Observe repeatedly until it has enough context.")
    write("- Added `search_case_law` and tested a breach-of-contract question.")
    write("- Enabled verbose/debug reasoning with `VERBOSE = True` and `debug=VERBOSE` because this LangGraph version exposes `debug`, not `verbose`.")
    write()
    write("### Stage 4")
    write("- `StateGraph` defines shared state and graph nodes.")
    write("- `Send()` dispatches specialist agents in parallel.")
    write("- Added `privacy_agent`, privacy routing, graph node/edge, and aggregation.")
    write()
    write("### Stage 5")
    write("- Registry is needed so agents discover capabilities dynamically instead of hardcoding URLs.")
    write("- Depth guards prevent infinite delegation loops.")
    write("- A2A provides a common agent communication contract over HTTP; REST/gRPC alone do not define agent cards, task semantics, or delegation flow.")
    write("- Tax Agent behavior was modified to answer concisely under 120 words with bullet points.")
    write()
    write("### Latency Improvement Proposal")
    write("- Keep specialist prompts short and enforce short outputs.")
    write("- Cache Registry discovery results for `tax_question`, `compliance_question`, and `legal_question`.")
    write("- Use a faster model for specialist agents.")
    write("- Preserve LangGraph parallel delegation with `Send()`.")
    write()


def main() -> None:
    write_static_sections()

    write("## Captured Runs")
    write()
    run_command("Syntax check", [PYTHON, "-m", "py_compile", "common/llm.py", "exercises/exercise_2_tools.py", "stages/stage_3_single_agent/main.py", "exercises/exercise_4_multiagent.py", "stages/stage_4_milti_agent/main.py", "tax_agent/graph.py"], timeout=60)
    run_command("Stage 1 - Direct LLM", [PYTHON, "stages/stage_1_direct_llm/main.py"], timeout=120)
    run_command(
        "Stage 2 - Exercise Tools",
        [PYTHON, "exercises/exercise_2_tools.py"],
        timeout=120,
        input_text="Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?\n",
    )
    run_command("Stage 3 - ReAct Agent", [PYTHON, "stages/stage_3_single_agent/main.py"], timeout=180)
    run_command("Stage 4 - Exercise Multi-Agent", [PYTHON, "exercises/exercise_4_multiagent.py"], timeout=240)
    run_command("Stage 4 - Demo Multi-Agent", [PYTHON, "stages/stage_4_milti_agent/main.py"], timeout=240)
    run_stage5()
    write("## Completion Checklist")
    write()
    write("- [x] Stage 1 answer and run captured")
    write("- [x] Stage 2 tools/knowledge-base answer and run captured")
    write("- [x] Stage 3 ReAct/case-law answer and run captured")
    write("- [x] Stage 4 privacy multi-agent graph and run captured")
    write("- [x] Stage 5 Registry snapshot, sequence diagram, E2E test, and latency captured")
    write("- [x] Tax Agent behavior update recorded")


if __name__ == "__main__":
    main()
