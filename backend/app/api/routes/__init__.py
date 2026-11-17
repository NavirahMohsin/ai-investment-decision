from app.api.routes.v1 import router as v1_router
from app.api.routes.fundamentals import router as fundamentals_router
from app.api.routes.sectors import router as sectors_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.news_intelligence import router as news_intelligence_router
from app.api.routes.assistant import assistant_router
from app.api.routes.agents import agents_router
from app.api.routes.research import research_router
from app.api.routes.explanations import explanations_router
from app.api.routes.intelligence import router as intelligence_router

__all__ = [
    "v1_router",
    "fundamentals_router",
    "sectors_router",
    "predictions_router",
    "news_intelligence_router",
    "assistant_router",
    "agents_router",
    "research_router",
    "explanations_router",
    "intelligence_router",
]
