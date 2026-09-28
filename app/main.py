from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import admin, assessments, auth, coins, member, rewards, root


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.mount("/static", StaticFiles(directory="app/static"), name="static")
    application.include_router(root.router)
    application.include_router(auth.router)
    application.include_router(member.router)
    application.include_router(coins.router)
    application.include_router(assessments.router)
    application.include_router(rewards.router)
    application.include_router(admin.router)

    @application.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        return PlainTextResponse("Доступ запрещён", status_code=403)

    return application


app = create_app()
