"""
Reminder API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.reminders.reminders import Reminder, ReminderManager
from ..dependencies import get_reminder_manager
from api.models.reminder import ReminderRead, ReminderList


router = APIRouter(
    prefix="/reminders",
    tags=["reminders"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=ReminderList)
async def get_reminders(
    chat_id: Optional[int] = Query(None, description="Filter by chat ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    reminder_manager: ReminderManager = Depends(get_reminder_manager)
):
    """
    Get all reminders, optionally filtered by chat_id or user_id.
    """
    try:
        # Load reminders from database using existing manager
        reminders = reminder_manager.load_reminders(chat_id)

        # Filter by user_id if provided
        if user_id:
            reminders = [r for r in reminders if r.user_id == user_id]

        # Convert to Pydantic models and return
        reminder_models = [
            ReminderRead(
                reminder_id=r.reminder_id,
                task=r.task,
                frequency=r.frequency,
                delay=r.delay,
                date_modifier=r.date_modifier,
                next_execution=r.next_execution,
                user_id=r.user_id,
                chat_id=r.chat_id,
                user_mention_md=r.user_mention_md
            ) for r in reminders
        ]
        return ReminderList(items=reminder_models, count=len(reminder_models))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reminders: {str(e)}")


@router.get("/{reminder_id}", response_model=ReminderRead)
async def get_reminder(
    reminder_id: int,
    reminder_manager: ReminderManager = Depends(get_reminder_manager)
):
    """
    Get a specific reminder by ID.
    """
    try:
        reminders = reminder_manager.load_reminders()
        reminder = next((r for r in reminders if r.reminder_id == reminder_id), None)

        if not reminder:
            raise HTTPException(status_code=404, detail=f"Reminder with ID {reminder_id} not found")

        return ReminderRead(
            reminder_id=reminder.reminder_id,
            task=reminder.task,
            frequency=reminder.frequency,
            delay=reminder.delay,
            date_modifier=reminder.date_modifier,
            next_execution=reminder.next_execution,
            user_id=reminder.user_id,
            chat_id=reminder.chat_id,
            user_mention_md=reminder.user_mention_md
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reminder: {str(e)}")