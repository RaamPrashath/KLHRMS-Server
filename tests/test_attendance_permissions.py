from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.shared.deps.attendance_permissions import require_attendance_permission
from app.shared.deps.organization_member import MemberContext


def _ctx(permissions: dict) -> MemberContext:
    role = SimpleNamespace(permissions=permissions)
    member = SimpleNamespace(role=role)
    return MemberContext(
        organization=SimpleNamespace(),
        member=member,
        role=role,
    )


def test_require_attendance_permission_accepts_timesheet_self_scope():
    dependency = require_attendance_permission("delete", module="timesheet")

    access = dependency(
        _ctx(
            {
                "attendance": {"delete": "none"},
                "timesheet": {"delete": "self"},
            }
        )
    )

    assert access.permission_module == "timesheet"
    assert access.permission_action == "delete"
    assert access.permission_scope == "self"


def test_require_attendance_permission_treats_none_scope_as_no_permission():
    dependency = require_attendance_permission("delete")

    with pytest.raises(HTTPException) as exc_info:
        dependency(_ctx({"attendance": {"delete": "none"}}))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "No attendance.delete permission"
