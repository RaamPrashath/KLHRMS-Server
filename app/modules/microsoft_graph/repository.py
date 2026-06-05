import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.account import Account
from app.models.employee import Employee
from app.models.employee_group import EmployeeGroup
from app.models.employee_group_membership import EmployeeGroupMembership
from app.models.member import Member
from app.models.microsoft_integration_setting import MicrosoftIntegrationSetting
from app.models.microsoft_sync_run import MicrosoftSyncRun
from app.models.role import Role
from app.models.user import User
from app.integrations.microsoft_graph.schema import MicrosoftUser

logger = logging.getLogger("klhrms.microsoft.graph.repository")


class MicrosoftGraphRepository:
    """Data access for Microsoft Graph integration."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Settings ───────────────────────────────────────────────────────────────

    async def get_settings(self, org_id: str) -> MicrosoftIntegrationSetting | None:
        result = await self._db.execute(
            select(MicrosoftIntegrationSetting).where(
                MicrosoftIntegrationSetting.organization_id == UUID(org_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_settings_presence(self, org_id: str) -> dict | None:
        result = await self._db.execute(
            select(
                MicrosoftIntegrationSetting.is_enabled,
                MicrosoftIntegrationSetting.tenant_id.is_not(None),
                MicrosoftIntegrationSetting.client_id.is_not(None),
                MicrosoftIntegrationSetting.client_secret.is_not(None),
                MicrosoftIntegrationSetting.last_sync_at,
                MicrosoftIntegrationSetting.last_sync_status,
                MicrosoftIntegrationSetting.last_sync_summary,
            ).where(MicrosoftIntegrationSetting.organization_id == UUID(org_id))
        )
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "is_enabled": row[0],
            "has_tenant_id": row[1],
            "has_client_id": row[2],
            "has_client_secret": row[3],
            "last_sync_at": row[4],
            "last_sync_status": row[5],
            "last_sync_summary": row[6],
        }

    async def upsert_settings(
        self,
        org_id: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> MicrosoftIntegrationSetting:
        existing = await self.get_settings(org_id)
        if existing:
            existing.tenant_id = tenant_id
            existing.client_id = client_id
            existing.client_secret = client_secret
            existing.is_enabled = True
            return existing
        setting = MicrosoftIntegrationSetting(
            organization_id=UUID(org_id),
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            is_enabled=True,
        )
        self._db.add(setting)
        await self._db.flush()
        return setting

    async def update_sync_summary(
        self,
        org_id: str,
        status: str,
        summary: dict | None = None,
    ) -> None:
        await self._db.execute(
            update(MicrosoftIntegrationSetting)
            .where(MicrosoftIntegrationSetting.organization_id == UUID(org_id))
            .values(
                last_sync_at=datetime.now(timezone.utc),
                last_sync_status=status,
                last_sync_summary=summary,
            )
        )

    # ── Sync Runs ──────────────────────────────────────────────────────────────

    async def create_sync_run(
        self, org_id: str, triggered_by_member_id: str
    ) -> MicrosoftSyncRun:
        run = MicrosoftSyncRun(
            organization_id=UUID(org_id),
            triggered_by_member_id=triggered_by_member_id,
            status="in_progress",
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def finalize_sync_run(
        self,
        run: MicrosoftSyncRun,
        total_fetched: int = 0,
        created_count: int = 0,
        updated_count: int = 0,
        skipped_count: int = 0,
        failed_count: int = 0,
        errors: list[dict] | None = None,
    ) -> None:
        run.status = "success" if failed_count == 0 else "completed_with_errors"
        run.total_fetched = total_fetched
        run.created_count = created_count
        run.updated_count = updated_count
        run.skipped_count = skipped_count
        run.failed_count = failed_count
        run.errors = errors or []
        run.completed_at = datetime.now(timezone.utc)

    async def get_sync_runs(
        self, org_id: str, limit: int = 20, offset: int = 0
    ) -> list[MicrosoftSyncRun]:
        result = await self._db.execute(
            select(MicrosoftSyncRun)
            .where(MicrosoftSyncRun.organization_id == UUID(org_id))
            .order_by(MicrosoftSyncRun.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_sync_run(
        self, org_id: str, run_id: str
    ) -> MicrosoftSyncRun | None:
        result = await self._db.execute(
            select(MicrosoftSyncRun).where(
                MicrosoftSyncRun.organization_id == UUID(org_id),
                MicrosoftSyncRun.id == UUID(run_id),
            )
        )
        return result.scalar_one_or_none()

    # ── Employees ──────────────────────────────────────────────────────────────

    async def find_employee_by_microsoft_id(
        self, org_id: str, microsoft_id: str
    ) -> Employee | None:
        result = await self._db.execute(
            select(Employee).where(
                Employee.organization_id == UUID(org_id),
                Employee.microsoft_id == microsoft_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_employee_by_email(
        self, org_id: str, email: str
    ) -> Employee | None:
        result = await self._db.execute(
            select(Employee).where(
                Employee.organization_id == UUID(org_id),
                Employee.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_employee(
        self, org_id: str, data: dict
    ) -> tuple[Employee, bool]:
        """Return (employee, was_created)."""
        microsoft_id = data.get("microsoft_id", "")
        existing = await self.find_employee_by_microsoft_id(org_id, microsoft_id)
        if existing:
            for key, value in data.items():
                if key != "microsoft_id" and hasattr(existing, key):
                    setattr(existing, key, value)
            await self._db.flush()
            return existing, False
        emp = Employee(organization_id=UUID(org_id), **data)
        self._db.add(emp)
        await self._db.flush()
        return emp, True

    async def update_employee_profile(
        self, org_id: str, microsoft_id: str, data: dict
    ) -> None:
        """Apply non-null profile fields onto an existing employee row.

        Unlike `upsert_employee`, this only writes the keys provided in `data`
        and skips None values so partial refreshes don't blank out fields.
        """
        employee = await self.find_employee_by_microsoft_id(org_id, microsoft_id)
        if employee is None:
            return
        for key, value in data.items():
            if key == "microsoft_id":
                continue
            if value is None:
                continue
            if hasattr(employee, key):
                setattr(employee, key, value)
        await self._db.flush()

    async def link_employee_to_user(
        self, org_id: str, microsoft_id: str, user_id: str
    ) -> None:
        employee = await self.find_employee_by_microsoft_id(org_id, microsoft_id)
        if employee is None:
            return
        employee.user_id = user_id
        await self._db.flush()

    # ── Auth identities ───────────────────────────────────────────────────────

    async def get_default_member_role(self, org_id: str) -> Role | None:
        result = await self._db.execute(
            select(Role)
            .where(Role.organizationId == str(UUID(org_id)))
            .order_by(Role.name.asc())
        )
        roles = list(result.scalars().all())
        if not roles:
            return None
        employee_role = next((role for role in roles if role.name.lower() == "employee"), None)
        return employee_role or roles[0]

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def update_user_microsoft_image(self, user_id: str, image_url: str) -> None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return

        existing_image = (user.image or "").strip()
        if existing_image and "/microsoft-graph/profile-photos/" not in existing_image:
            return

        if existing_image == image_url:
            return

        user.image = image_url
        user.updatedAt = datetime.now(timezone.utc)
        await self._db.flush()

    async def get_microsoft_account(self, microsoft_id: str) -> Account | None:
        result = await self._db.execute(
            select(Account)
            .options(joinedload(Account.user))
            .where(
                Account.providerId == "microsoft",
                Account.accountId == microsoft_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_user_member_from_graph(
        self,
        org_id: str,
        graph_user: MicrosoftUser,
        default_role_id: str,
    ) -> tuple[User, Member, bool]:
        email = (graph_user.email or graph_user.user_principal_name or "").strip().lower()
        if not email:
            raise ValueError("Microsoft user is missing an email address")

        created = False
        now = datetime.now(timezone.utc)

        account = await self.get_microsoft_account(graph_user.graph_id)
        user = account.user if account and account.user else None

        if user is None:
            user = await self.get_user_by_email(email)

        if user is None:
            user = User(
                email=email,
                name=(graph_user.display_name or email),
                emailVerified=True,
                onboarded=True,
                createdAt=now,
                updatedAt=now,
            )
            self._db.add(user)
            await self._db.flush()
            created = True
        else:
            user_changed = False
            display_name = (graph_user.display_name or "").strip()
            if display_name and not (user.name or "").strip():
                user.name = display_name
                user_changed = True
            if not user.emailVerified:
                user.emailVerified = True
                user_changed = True
            if not user.onboarded:
                user.onboarded = True
                user_changed = True
            if user_changed:
                user.updatedAt = now
                await self._db.flush()

        if account is None:
            account = Account(
                accountId=graph_user.graph_id,
                providerId="microsoft",
                userId=user.id,
                createdAt=now,
                updatedAt=now,
            )
            self._db.add(account)
            await self._db.flush()
            created = True
        elif account.userId != user.id:
            account.userId = user.id
            account.updatedAt = now

        member_result = await self._db.execute(
            select(Member).where(
                Member.organizationId == org_id,
                Member.userId == user.id,
            )
        )
        member = member_result.scalar_one_or_none()

        if member is None:
            member = Member(
                organizationId=org_id,
                userId=user.id,
                roleId=default_role_id,
                status="ACTIVE",
                createdAt=now,
            )
            self._db.add(member)
            await self._db.flush()
            created = True
        else:
            member_changed = False
            if member.roleId is None:
                member.roleId = default_role_id
                member_changed = True
            if member.status != "ACTIVE":
                member.status = "ACTIVE"
                member_changed = True
            if member_changed:
                await self._db.flush()

        return user, member, created

    async def count_employees(self, org_id: str) -> int:
        result = await self._db.execute(
            select(func.count(Employee.id)).where(
                Employee.organization_id == UUID(org_id)
            )
        )
        return result.scalar() or 0

    # ── Employee Manager Relationship ──────────────────────────────────────────

    async def update_employee_manager(
        self, org_id: str, employee_id: UUID, manager_id: UUID | None
    ) -> None:
        await self._db.execute(
            update(Employee)
            .where(
                Employee.organization_id == UUID(org_id),
                Employee.id == employee_id,
            )
            .values(manager_id=manager_id)
        )

    # ── Groups ──────────────────────────────────────────────────────────────────

    async def upsert_group(
        self, org_id: str, microsoft_group_id: str, display_name: str, description: str | None, group_type: str | None
    ) -> EmployeeGroup:
        result = await self._db.execute(
            select(EmployeeGroup).where(
                EmployeeGroup.organization_id == UUID(org_id),
                EmployeeGroup.microsoft_group_id == microsoft_group_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.display_name = display_name
            existing.description = description
            existing.group_type = group_type
            await self._db.flush()
            return existing
        group = EmployeeGroup(
            organization_id=UUID(org_id),
            microsoft_group_id=microsoft_group_id,
            display_name=display_name,
            description=description,
            group_type=group_type,
        )
        self._db.add(group)
        await self._db.flush()
        return group

    async def clear_group_memberships(self, group_id: UUID) -> None:
        await self._db.execute(
            EmployeeGroupMembership.__table__.delete().where(
                EmployeeGroupMembership.group_id == group_id
            )
        )

    async def add_employee_to_group(
        self, group_id: UUID, employee_id: UUID
    ) -> None:
        self._db.add(
            EmployeeGroupMembership(
                group_id=group_id, employee_id=employee_id
            )
        )
