"""
Package codebase/app/tools
Export tập trung toàn bộ 15 Agent Tools cho AI Agent.
"""

from app.tools.admin_tools import (
    upload_lab_material,
    codebase_indexer,
    RAG_search,
    UploadLabMaterialInput,
    CodebaseIndexerInput,
    RAGSearchInput,
)

from app.tools.platform_tools import (
    get_user_context,
    create_group_room,
    send_message,
    send_notification,
    GetUserContextInput,
    CreateGroupRoomInput,
    SendMessageInput,
    SendNotificationInput,
)

from app.tools.task_tools import (
    parse_lab_requirements,
    assign_task,
    track_group_progress,
    generate_reflection,
    ParseLabRequirementsInput,
    AssignTaskInput,
    TrackGroupProgressInput,
    GenerateReflectionInput,
)

from app.tools.scheduler_tools import (
    schedule_reminder,
    extend_deadline,
    ScheduleReminderInput,
    ExtendDeadlineInput,
)

from app.tools.troubleshooting_tools import (
    analyze_student_issue,
    fetch_peer_solution,
    AnalyzeStudentIssueInput,
    FetchPeerSolutionInput,
)

ALL_TOOLS = {
    # Admin & Knowledge Tools
    "upload_lab_material": upload_lab_material,
    "codebase_indexer": codebase_indexer,
    "RAG_search": RAG_search,

    # Platform & Context Tools
    "get_user_context": get_user_context,
    "create_group_room": create_group_room,
    "send_message": send_message,
    "send_notification": send_notification,

    # Task Management Tools
    "parse_lab_requirements": parse_lab_requirements,
    "assign_task": assign_task,
    "track_group_progress": track_group_progress,
    "generate_reflection": generate_reflection,

    # Scheduler & Remind Tools
    "schedule_reminder": schedule_reminder,
    "extend_deadline": extend_deadline,

    # Troubleshooting Tools
    "analyze_student_issue": analyze_student_issue,
    "fetch_peer_solution": fetch_peer_solution,
}

# Mapping tên tool với hàm xử lý thực tế
TOOL_FUNCTIONS = ALL_TOOLS

def load_tool_declarations(tools_file) -> list:
    """Đọc khai báo tools từ file YAML."""
    import yaml
    with open(tools_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("tools", [])

def to_openai_tools(declarations: list) -> list:
    """Chuyển đổi các khai báo tools sang định dạng OpenAI Function Calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": decl["name"],
                "description": decl["description"].strip(),
                "parameters": decl["parameters"]
            }
        }
        for decl in declarations
    ]

__all__ = [
    "upload_lab_material",
    "codebase_indexer",
    "RAG_search",
    "get_user_context",
    "create_group_room",
    "send_message",
    "send_notification",
    "parse_lab_requirements",
    "assign_task",
    "track_group_progress",
    "generate_reflection",
    "schedule_reminder",
    "extend_deadline",
    "analyze_student_issue",
    "fetch_peer_solution",
    "ALL_TOOLS",
    "TOOL_FUNCTIONS",
    "load_tool_declarations",
    "to_openai_tools",
]
