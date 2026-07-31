"""
Package codebase/app/tools
Export tập trung Agent Tools cho AI Agent.
"""

from app.tools.knowledge_tools import (
    get_lab_content,
)

from app.tools.platform_tools import (
    create_group_room,
    CreateGroupRoomInput,
)

from app.tools.task_tools import (
    generate_group_plan,
    get_group_plan,
    track_group_progress,
    update_group_progress,
    list_members,
    GenerateGroupPlanInput,
    GetGroupPlanInput,
    TrackGroupProgressInput,
    UpdateGroupProgressInput,
)

from app.tools.troubleshooting_tools import (
    analyze_student_issue,
    AnalyzeStudentIssueInput,
)

ALL_TOOLS = {
    # Knowledge & Content Tools
    "get_lab_content": get_lab_content,

    # Platform & Context Tools
    "create_group_room": create_group_room,

    # Task Management Tools
    "generate_group_plan": generate_group_plan,
    "get_group_plan": get_group_plan,
    "track_group_progress": track_group_progress,
    "update_group_progress": update_group_progress,
    "list_members": list_members,

    # Troubleshooting Tools
    "analyze_student_issue": analyze_student_issue,
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
    "get_lab_content",
    "create_group_room",
    "generate_group_plan",
    "get_group_plan",
    "track_group_progress",
    "update_group_progress",
    "list_members",
    "analyze_student_issue",
    "ALL_TOOLS",
    "TOOL_FUNCTIONS",
    "load_tool_declarations",
    "to_openai_tools",
]
