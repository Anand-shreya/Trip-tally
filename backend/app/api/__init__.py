from fastapi import APIRouter

from app.api import ai, chatgpt, expenses, itinerary, locations, places, summaries, trips

api_router = APIRouter()
api_router.include_router(ai.router)
api_router.include_router(chatgpt.router)
api_router.include_router(locations.router)
api_router.include_router(trips.router)
api_router.include_router(places.router)
api_router.include_router(itinerary.router)
api_router.include_router(expenses.router)
api_router.include_router(summaries.router)
