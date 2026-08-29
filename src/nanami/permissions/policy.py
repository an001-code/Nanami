"""权限系统：在工具执行前做 allow / deny / ask 裁决。"""
from __future__ import annotations

from typing import Any, Callable

# ask_callback 签名：(tool_name: str, args: dict) -> bool（True=允许）
AskCallback = Callable[[str, dict[str, Any]], bool]


class PermissionPolicy:
    def __init__(
        self,
        default: str = "ask",
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        ask_callback: AskCallback | None = None,
    ) -> None:
        self.default = default
        self.allowlist = set(allowlist or [])
        self.denylist = set(denylist or [])
        self.ask_callback = ask_callback

    def check(self, tool_name: str, args: dict[str, Any] | None = None) -> str:
        """返回 'allow' 或 'deny'。"""
        if tool_name in self.denylist:
            return "deny"
        if tool_name in self.allowlist:
            return "allow"
        if self.default == "allow":
            return "allow"
        if self.default == "deny":
            return "deny"
        # ask：由回调询问用户；无回调时默认拒绝以保证安全
        if self.ask_callback is not None:
            return "allow" if self.ask_callback(tool_name, args or {}) else "deny"
        return "deny"
