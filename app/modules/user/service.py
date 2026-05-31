import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.member import Member
from app.shared.utils.password import hash_password

logger = logging.getLogger("klhrms.user.service")


async def set_password(
    member_id: str,
    organization_id: str,
    new_password: str,
    db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(Member).where(
            Member.id == member_id,
            Member.organizationId == organization_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return {"success": False, "message": "Member not found"}

    hashed = hash_password(new_password)

    acct_result = await db.execute(
        select(Account).where(
            Account.userId == member.userId,
            Account.providerId == "credential",
        )
    )
    account = acct_result.scalar_one_or_none()

    if account:
        account.password = hashed
    else:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        account = Account(
            accountId=member.userId,
            providerId="credential",
            userId=member.userId,
            password=hashed,
            createdAt=now,
            updatedAt=now,
        )
        db.add(account)

    await db.commit()
    return {"success": True, "message": "Password updated successfully"}
