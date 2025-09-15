# gatekeeper/judge.py
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field          #Pydantic v2
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json

__all__ = ["llm_decide"]

# ---- Pydantic schemas Gemini must output ----
class EvidenceItem(BaseModel):
    source: str = Field(..., description="Top-level section (e.g., actions, checks, blockers)")
    path: str = Field(..., description="Dot path into the signals JSON (e.g., actions.latest_run.conclusion)")
    value: Optional[Any] = Field(None, description="Exact value observed at that path")

class JudgeResponse(BaseModel):
    decision: Literal["GO", "NO_GO", "PAUSE"]
    reasons: List[str]
    evidence: List[EvidenceItem]
    policy_violations: List[str]
    confidence: float

SYSTEM = (
    "You are ReleasePolicy Judge v1.0. Decide GO/PAUSE/NO_GO based ONLY on the provided JSON signals. "
    "Do not invent data. If information is insufficient or ambiguous, return PAUSE. "
    "Respond as a structured object that matches the provided schema."
)

# In gatekeeper/judge.py, update USER_TMPL to clarify path style
USER_TMPL = (
    "Signals JSON (do not change values; cite exact fields in evidence):\n"
    "{signals}\n\n"
    "Path rules for evidence:\n"
    "- Use dot paths **rooted at the top-level keys** shown in the JSON.\n"
    "- Examples: actions.latest_run.conclusion ; checks.runs.0.conclusion ; blockers\n"
    "- Use 0-based indexes with dot notation ('.0'), NOT brackets (no '[0]').\n"
    "- To cite that blockers are empty, use path 'blockers' with value [].\n\n"
    "Policy rubric:\n"
    "- Consider CI workflow conclusion, individual check runs, and open blocker issues.\n"
    "- If risk is elevated but not a firm block, choose PAUSE and propose mitigations.\n"
    "- Provide concise reasons and cite at least 2 evidence items.\n"
    "Return ONLY the structured object."
    "Also Act as summarizer at the end to showcase the developer that what is the end result to developer in human language"
)

def llm_decide(
    signals: Dict[str, Any],
    model: str = "gemini-1.5-flash-002",
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """
    Ask Gemini for a structured decision. Returns a dict compatible with JudgeResponse.
    On any model/parse error, returns a safe PAUSE decision.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            # no convert_system_message_to_human (deprecated)
        )
        # Force a Pydantic-typed response (no prose)
        structured_llm = llm.with_structured_output(JudgeResponse)

        # Avoid .format() because of braces in the template; inject signals via replace
        signals_json = json.dumps(signals, ensure_ascii=False, separators=(",", ":"))
        user_msg = USER_TMPL.replace("{signals}", signals_json)

        result: JudgeResponse = structured_llm.invoke(
            [SystemMessage(content=SYSTEM), HumanMessage(content=user_msg)]
        )
        return result.model_dump()  # pydantic v2 dict()
    except Exception as e:
        return {
            "decision": "PAUSE",
            "reasons": [f"Judge error: {type(e).__name__}"],
            "evidence": [],
            "policy_violations": ["STRUCTURED_OUTPUT_ERROR"],
            "confidence": 0.0,
        }
