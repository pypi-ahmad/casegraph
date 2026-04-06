"""Local assignee registry derived from the existing auth environment setup."""

from __future__ import annotations

import os

from casegraph_agent_sdk.work_management import AssigneeReference


class LocalAssigneeRegistry:
    def list_assignees(self) -> list[AssigneeReference]:
        assignees: list[AssigneeReference] = []
        for index in range(1, 11):
            email = os.getenv(f"AUTH_USER_{index}_EMAIL")
            password_hash = os.getenv(f"AUTH_USER_{index}_PASSWORD_HASH")
            if not email or not password_hash:
                continue
            display_name = os.getenv(f"AUTH_USER_{index}_NAME") or f"User {index}"
            role = os.getenv(f"AUTH_USER_{index}_ROLE") or "member"
            if role not in {"admin", "member"}:
                role = "member"
            assignees.append(
                AssigneeReference(
                    user_id=f"local-{index}",
                    display_name=display_name,
                    email=email,
                    role=role,
                )
            )
        return assignees

    def get_assignee(self, user_id: str) -> AssigneeReference | None:
        for assignee in self.list_assignees():
            if assignee.user_id == user_id:
                return assignee
        return None