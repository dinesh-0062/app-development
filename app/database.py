import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger("teachsync")


class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None


db = Database()


async def get_database() -> AsyncIOMotorDatabase:
    return db.db


async def connect_to_mongo():
    logger.info("Connecting to MongoDB Atlas...")
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.db = db.client[settings.DATABASE_NAME]

    # Create indexes for collections
    try:
        # Users indexes
        await db.db.users.create_index("email", unique=True)

        # Classes indexes
        await db.db.classes.create_index([("date", 1), ("start_time", 1)])
        await db.db.classes.create_index("teacher_id")

        # Meetings indexes
        await db.db.meetings.create_index([("start_time", 1)])

        # Chats & Messages indexes
        await db.db.chats.create_index("members")
        await db.db.messages.create_index([("chat_id", 1), ("created_at", -1)])

        # Files indexes
        await db.db.files.create_index([("class_id", 1)])
        await db.db.files.create_index([("uploader_id", 1)])

        # Notifications indexes
        await db.db.notifications.create_index([("user_id", 1), ("created_at", -1)])

        # Call logs indexes
        await db.db.call_logs.create_index([("channel_name", 1)])

        logger.info("Successfully connected to MongoDB and verified indexes.")
    except Exception as e:
        logger.warning(f"Connected to MongoDB, index creation warning: {e}")


async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed.")
