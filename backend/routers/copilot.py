import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
import models
from database import get_db
from services import copilot

logger = logging.getLogger(__name__)
router = APIRouter()


class CopilotQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    # The recommendation currently on the user's screen, so answers cite the
    # same figures the dashboard is showing. Untrusted display data - it is only
    # ever formatted into the reply, never used to decide what may be disclosed.
    context: dict | None = None


@router.post("/ask")
def ask_copilot(
    payload: CopilotQuestion,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Answer a question about the platform, grounded in live reference data.

    Authenticated, because a grounded answer necessarily repeats landed cost,
    berth economics and lane figures back to the asker.
    """
    ports = db.query(models.Port).all()
    vessels = db.query(models.Vessel).all()

    try:
        result = copilot.ask(
            payload.question,
            ports=ports,
            vessels=vessels,
            context=payload.context,
        )
    except Exception as error:
        logger.exception("Copilot failed")
        raise HTTPException(status_code=500, detail=f"Copilot failed: {error}")

    # Record that the question was asked, not the answer. The question is short
    # and useful for audit; the answer restates priced data already logged
    # elsewhere, and storing it twice widens the exposure for no gain.
    try:
        db.add(models.AuditLog(
            action="COPILOT_QUERY",
            user_email=user.email,
            details=f"[{result.get('topic', 'General')}] {payload.question[:180]}",
        ))
        db.commit()
    except Exception:
        db.rollback()

    return result


@router.get("/suggestions")
def suggested_questions(user: models.User = Depends(auth.get_current_user)):
    """Prompts for the drawer, grouped so the range of coverage is visible."""
    return {
        "groups": [
            {"topic": "This recommendation", "questions": [
                "Why was this vessel class selected?",
                "Why this discharge port?",
                "How is the landed cost built up?",
                "How much is the optimisation saving?",
            ]},
            {"topic": "Method", "questions": [
                "How are the options ranked?",
                "How is the risk index calculated?",
                "How is supply continuity scored?",
                "What is deadfreight?",
            ]},
            {"topic": "Ports and fleet", "questions": [
                "Why is Haldia draft restricted?",
                "How is demurrage calculated?",
                "Which origin lanes are modelled?",
                "What does the plant choice change?",
            ]},
            {"topic": "Model and data", "questions": [
                "How accurate is the forecasting model?",
                "Where does the data come from?",
                "Is any of this real SAIL data?",
                "Who can see this data?",
            ]},
            {"topic": "Scenarios", "questions": [
                "What happens if a cyclone hits?",
                "What if freight rates spike?",
                "What if the primary port is blocked?",
            ]},
        ]
    }
