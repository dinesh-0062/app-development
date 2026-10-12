import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import db
from app.services.fcm_service import send_fcm_notification

logger = logging.getLogger("teachsync.scheduler")

scheduler = AsyncIOScheduler()


async def check_and_send_class_reminders():
    """
    Runs every minute to check classes scheduled in 30 minutes and 5 minutes.
    Sends FCM & in-app notifications.
    """
    if db.db is None:
        return

    try:
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        # Find today's classes
        classes = await db.db.classes.find({"date": today_str}).to_list(100)

        for cls in classes:
            class_id = str(cls["_id"])
            start_time_str = cls.get("start_time")  # e.g. "15:00"
            if not start_time_str:
                continue

            try:
                hour, minute = map(int, start_time_str.split(":"))
                class_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                diff = (class_dt - now).total_seconds() / 60.0  # in minutes

                # Check for 30-min reminder (diff between 29 and 31 minutes)
                if 29.0 <= diff <= 31.0:
                    await send_reminder_for_class(cls, 30)
                # Check for 5-min reminder (diff between 4 and 6 minutes)
                elif 4.0 <= diff <= 6.0:
                    await send_reminder_for_class(cls, 5)
            except Exception as e:
                logger.error(f"Error calculating class time reminder: {e}")

    except Exception as e:
        logger.error(f"Error in class reminder scheduler job: {e}")


async def send_reminder_for_class(cls: dict, minutes_left: int):
    topic = cls.get("topic", "Class")
    teacher = cls.get("teacher_name", "Teacher")
    title = f"Class Reminder ({minutes_left}m)"
    body = f"'{topic}' by {teacher} starts in {minutes_left} minutes!"

    # Get target users (all users or specific attendees)
    attendees = cls.get("attendees", [])
    if not attendees or "everyone" in attendees:
        users = await db.db.users.find({"is_active": True}).to_list(100)
    else:
        from bson import ObjectId
        obj_ids = [ObjectId(uid) for uid in attendees if ObjectId.is_valid(uid)]
        users = await db.db.users.find({"_id": {"$in": obj_ids}}).to_list(100)

    for u in users:
        uid = str(u["_id"])
        # Save in-app notification
        notif_doc = {
            "user_id": uid,
            "title": title,
            "body": body,
            "type": "class_reminder",
            "data": {"class_id": str(cls["_id"])},
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.db.notifications.insert_one(notif_doc)

        # Send FCM push if token available
        fcm_token = u.get("fcm_token")
        if fcm_token:
            await send_fcm_notification(fcm_token, title, body, {"class_id": str(cls["_id"])})


def start_scheduler():
    scheduler.add_job(check_and_send_class_reminders, 'interval', minutes=1)
    scheduler.start()
    logger.info("Class reminder scheduler started.")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Class reminder scheduler stopped.")
