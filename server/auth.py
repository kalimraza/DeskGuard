# server/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Validates agent API keys from Authorization: Bearer <key> header.
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

import database


def verify_agent(
    authorization: str = Header(...),
    db: Session = Depends(database.get_db)
) -> database.Machine:
    """FastAPI dependency — validates agent Bearer token, returns Machine row."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    api_key = authorization.removeprefix("Bearer ").strip()
    machine = db.query(database.Machine).filter_by(api_key=api_key, active=True).first()

    if not machine:
        raise HTTPException(status_code=403, detail="Unknown or inactive machine API key")

    return machine
