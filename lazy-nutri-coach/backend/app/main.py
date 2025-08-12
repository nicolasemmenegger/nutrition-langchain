from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db.database import init_db
from .api import auth, foods, advice, recipes, progress

app = FastAPI(title=settings.app_name)

# CORS configuration
if getattr(settings, "cors_allow_all", False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # cannot use credentials with wildcard origins
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Allow common local dev ports for the frontend (5173 default, 5174 fallback)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_origin,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

init_db()

app.include_router(auth.router)
app.include_router(foods.router)
app.include_router(advice.router)
app.include_router(recipes.router)
app.include_router(progress.router)

@app.get("/health")
def health():
    return {"status":"ok"}
