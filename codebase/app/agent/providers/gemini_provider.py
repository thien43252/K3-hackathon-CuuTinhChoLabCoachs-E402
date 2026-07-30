from __future__ import annotations

import os
from typing import Any
from .base import ModelResponse, ToolCall


class GeminiProvider:
    """Gemini API provider using google-generativeai with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "GEMINI_API_KEY",
        default_model: str = "gemini-2.5-flash",
    ) -> None:
        self.api_key_env = api_key_env
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError(
                "Install live provider dependency first: uv add google-generativeai"
            ) from exc

        # Lấy API key từ biến môi trường (hỗ trợ GEMINI_API_KEY hoặc GOOGLE_API_KEY)
        api_key = os.getenv(self.api_key_env) or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Missing API key env var: {self.api_key_env} or GOOGLE_API_KEY"
            )

        genai.configure(api_key=api_key)

        # Chuyển đổi định dạng message từ OpenAI sang Gemini
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [content]})

        # Chuyển đổi định dạng tools từ OpenAI sang Gemini
        gemini_tools = None
        if tools:
            gemini_tools = []
            for t in tools:
                if t.get("type") == "function":
                    func_decl = t["function"]
                    # Gemini yêu cầu schema phải đúng chuẩn OpenAPI
                    gemini_tools.append(func_decl)

        model_name = model or self.default_model
        
        # Cấu hình tham số sinh văn bản
        generation_config = {
            "temperature": temperature,
        }

        client = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
            tools=gemini_tools if gemini_tools else None,
        )

        resp = client.generate_content(
            contents=contents,
            generation_config=generation_config,
        )

        # Trích xuất text phản hồi
        text = None
        try:
            text = resp.text
        except Exception:
            # Trường hợp resp chỉ chứa tool calls hoặc bị block bởi safety filter
            if resp.candidates and resp.candidates[0].content.parts:
                text = resp.candidates[0].content.parts[0].text

        # Trích xuất tool calls nếu có
        calls: list[ToolCall] = []
        if resp.candidates and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if part.function_call:
                    func_call = part.function_call
                    # Chuyển đổi cấu trúc MapComposite sang Python dict chuẩn
                    args = {k: v for k, v in func_call.args.items()}
                    calls.append(ToolCall(name=func_call.name, args=args))

        return ModelResponse(text=text, tool_calls=calls, raw=resp)
