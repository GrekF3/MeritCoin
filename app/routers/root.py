from fastapi import APIRouter
from fastapi import Request

from app.routers.utils import render

router = APIRouter()


@router.get("/landing")
def landing(request: Request):
    return render(request, "index.html", {})


@router.get("/")
def root(request: Request):
    return render(request, "index.html", {})
