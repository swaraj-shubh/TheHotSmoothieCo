"""Create (or promote) a SUPER_ADMIN. Run once per environment:

    python -m scripts.create_admin admin@thehotsmoothie.co "Full Name"

The password is read from the ADMIN_PASSWORD env var or prompted for, never passed as an argument
(it would end up in shell history).
"""

import asyncio
import getpass
import os
import sys

import app.models  # noqa: F401  (register every model before using any)
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.users import repository
from app.users.models import RoleName, User


async def main(email: str, full_name: str) -> None:
    async with SessionLocal() as db:
        roles = await repository.get_roles(db, [RoleName.SUPER_ADMIN])
        user = await repository.get_by_email(db, email)
        if user:
            user.roles = list({*user.roles, *roles})
            print(f"Promoted existing user {email} to SUPER_ADMIN")
        else:
            password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (min 12 chars): ")
            if len(password) < 12:
                sys.exit("Admin password must be at least 12 characters")
            db.add(
                User(
                    email=email.lower(),
                    full_name=full_name,
                    password_hash=hash_password(password),
                    roles=roles,
                )
            )
            print(f"Created SUPER_ADMIN {email}")
        await db.commit()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
