from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


class DocumentationState(TypedDict):
    # Input
    org_id: str
    source: Literal["slack", "discord", "github", "cli"]
    channel_id: str
    thread_id: str
    question: str

    # Memory retrieval results
    similar_threads: list[dict]
    existing_docs: list[dict]
    reviewer_feedback_history: list[dict]
    semantic_context: list[dict]

    # Research results
    github_context: list[str]
    slack_context: list[str]

    # Synthesis
    knowledge_package: dict

    # Documentation output
    draft_content: str
    draft_title: str
    doc_type: str
    confidence_score: float

    # Review
    review_result: dict
    review_feedback: str
    rubric_feedback: str
    rubric_evaluations: list

    # HITL
    human_decision: Literal["approve", "reject", "revise", ""]
    human_feedback: str

    # Final
    published_urls: list[dict]
    reply_errors: list[dict]

    # Tracking
    support_thread_id: str
    workflow_id: str
    doc_id: str
    messages: Annotated[list, add_messages]

    # Source reply context (platform-specific identifiers, no tokens)
    source_metadata: dict

    # LangGraph checkpointer thread_id for HITL resume
    graph_thread_id: str

    # Hybrid Deep agents fields
    question_type: str  # "simple", "moderate", "complex"
    research_skill: dict  # Selected research skill
    investigation_plan: list[dict]  # Todo-driven investigation plan
    rubric_status: dict  # Rubric evaluation results
    subagent_results: dict  # Results from subagent execution

    # Conversation context
    message_history: list[dict[str, str]]

    # Trace collection for hill-climbing
    _node_traces: list  # list[NodeTrace] — populated during execution
    _trace_collected: bool

    # Episode + reflection memory
    episode_id: str
    reflection_id: str
    _reflected: bool
