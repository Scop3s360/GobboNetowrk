"""
Research Worker Prompt Builder
================================
Builds the system and user prompts sent to the AI model.

Architectural decisions:

    Dedicated module:
        Prompt logic lives here, not inside the worker.  This enforces the
        single-responsibility principle: the worker orchestrates, the prompt
        builder constructs messages.  It also makes prompts independently
        testable and easy to revise without touching worker logic.

    System prompt is fixed:
        The system prompt is a constant string that establishes the model's
        persona and behavioural constraints.  It is intentionally strict:
          - Answer objectively, not aspirationally.
          - Provide concise, enumerated findings.
          - Include sources when available.
          - Admit uncertainty rather than hallucinate.
        This reflects the GoblinOS guide principle: "agents never perform
        destructive actions automatically" — and, by extension, should never
        invent facts.

    User prompt is dynamic:
        The user prompt is assembled from the ResearchRequest fields.
        Context and constraints are injected when present.  When absent,
        the corresponding sections are omitted so the model is not confused
        by empty headings.

    No f-string injection of raw user input into the system prompt:
        User-controlled text (research_query, context, constraints) is
        placed only in the user-role message, never in the system prompt.
        This prevents prompt injection from escalating into system-level
        instruction override.

    Structured response format:
        The user prompt asks the model to respond in a specific format
        (SUMMARY / FINDINGS / SOURCES / CONFIDENCE) so the parser can
        extract structured data reliably.

    Format contract:
        The expected response format is defined here (as a module-level
        constant) and imported by the parser.  Single source of truth.
"""

from workers.research.models import ResearchRequest

# ---------------------------------------------------------------------------
# Response format specification (shared with parser)
# ---------------------------------------------------------------------------

RESPONSE_SECTIONS = ("SUMMARY", "FINDINGS", "SOURCES", "CONFIDENCE")

SYSTEM_PROMPT = """\
You are a research assistant. Your only job is to answer research queries \
accurately and objectively.

Rules you must follow without exception:
1. Answer only what is asked. Do not volunteer unrelated information.
2. Be concise. Each finding must be a single factual sentence.
3. If you are uncertain about something, say so explicitly. Never invent facts.
4. Always cite sources when you have them. Use the URL or a short citation.
5. Do not express opinions, recommendations, or predictions beyond the evidence.

You must structure every response using EXACTLY these four labelled sections, \
in this order, with no deviation:

SUMMARY:
<A single paragraph summarising the overall answer.>

FINDINGS:
- <Finding 1>
- <Finding 2>
- <More findings as needed>

SOURCES:
- <URL or citation 1>
- <URL or citation 2>
- (Write "No sources available" if none can be cited.)

CONFIDENCE:
<Write exactly one of: high / medium / low>
<Follow it with one sentence explaining your confidence level.>\
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_user_prompt(request: ResearchRequest) -> str:
    """
    Construct the user-role message from a ResearchRequest.

    Args:
        request: The research task to encode into a prompt.

    Returns:
        A formatted string ready to send as the user message.
    """
    parts: list[str] = [f"Research query: {request.research_query}"]

    if request.context:
        parts.append(f"\nContext: {request.context}")

    if request.constraints:
        constraints_text = "\n".join(f"- {c}" for c in request.constraints)
        parts.append(f"\nConstraints:\n{constraints_text}")

    parts.append(
        "\nRespond using the SUMMARY / FINDINGS / SOURCES / CONFIDENCE format."
    )

    return "\n".join(parts)
