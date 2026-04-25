import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Load .env from the backend root directory
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
from app.models import (
    Organization, User, Listing, InventoryMaster, Reservation, 
    MarketEvent, PricingRule, BenchmarkData, AirbticsCache, EngineRun, Insight,
    CompetitorListing, CompetitorPerformance, CompetitorReview
)
from app.models.chat_message import ChatMessage
from app.models.detector import Detector
from app.models.guest_summary import GuestSummary
from app.models.hostaway_conversation import HostawayConversation
from app.models.market_template import MarketTemplate
from app.models.property_group import PropertyGroup
from app.models.source import Source
from app.models.source_run import SourceRun
from app.models.ops_ticket import OpsTicket
from app.models.comms_policy import CommsPolicy
from app.models.guest_thread import GuestThread

async def init_db():
    client = AsyncIOMotorClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    # Use DATABASE_NAME (set to 'priceos' in .env), fallback to MONGODB_DB, then 'priceos'
    db_name = os.environ.get("DATABASE_NAME") or os.environ.get("MONGODB_DB") or "priceos"
    db = client.get_database(db_name)
    print(f"[db] Connected to database: {db_name}")
    
    await init_beanie(
        database=db,
        document_models=[
            Organization,
            User,
            Listing,
            InventoryMaster,
            Reservation,
            MarketEvent,
            PricingRule,
            BenchmarkData,
            AirbticsCache,
            EngineRun,
            Insight,
            ChatMessage,
            Detector,
            GuestSummary,
            HostawayConversation,
            MarketTemplate,
            PropertyGroup,
            Source,
            SourceRun,
            OpsTicket,
            CommsPolicy,
            GuestThread,
            CompetitorListing,
            CompetitorPerformance,
            CompetitorReview,
        ]
    )
