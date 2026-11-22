import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Keep the static storefront reachable if a cloud environment variable was not
# saved correctly. It exposes a safe health message instead of an opaque boot
# loop, without disclosing a secret value.
startup_issue: str | None = None
client = None
db = None
ensure_indexes = None

try:
    from lib.db import client, db, ensure_indexes
    from routers import admin, auth, community, files, orders, packages, roblox, settings, topups
except KeyError as exc:
    startup_issue = f"Pengaturan server `{exc.args[0]}` belum tersedia."
except RuntimeError as exc:
    startup_issue = str(exc)
except Exception as exc:
    logging.getLogger(__name__).exception("Application setup failed")
    startup_issue = f"Aplikasi belum dapat dimulai ({type(exc).__name__})."

# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    if startup_issue is not None or ensure_indexes is None:
        yield
        return

    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    yield
    app.state.index_task.cancel()  # stop a build still running before its client closes
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    if client is not None:
        client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

if startup_issue is None:
    api_router.include_router(auth.router)
    api_router.include_router(community.router)
    api_router.include_router(roblox.router)
    api_router.include_router(packages.router)
    api_router.include_router(orders.router)
    api_router.include_router(topups.router)
    api_router.include_router(settings.router)
    api_router.include_router(files.router)
    api_router.include_router(admin.router)


@api_router.get("/")
async def root():
    if startup_issue is not None:
        return {"message": startup_issue, "status": "configuration_required"}
    return {"message": "Dea Store API siap melayani"}


@api_router.get("/health")
async def health():
    """Non-secret deployment diagnosis and database reachability check."""
    if startup_issue is not None:
        return JSONResponse(
            {"status": "configuration_required", "message": startup_issue},
            status_code=503,
        )

    try:
        await db.command("ping", maxTimeMS=3000)
    except Exception:
        return JSONResponse(
            {
                "status": "database_unavailable",
                "message": "Database belum bisa dihubungi. Periksa MONGO_URL dan akses jaringan Atlas.",
            },
            status_code=503,
        )
    return {"status": "ok", "message": "Dea Store dan database siap"}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In production the same service serves the built Vite app and the API. Keeping
# both behind one origin lets the session cookie work without cross-site fetches.
STATIC_DIR = ROOT_DIR / "static"
if STATIC_DIR.is_dir():
    @app.get("/{requested_path:path}", include_in_schema=False)
    async def serve_frontend(requested_path: str):
        if requested_path == "api" or requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint tidak ditemukan")

        static_root = STATIC_DIR.resolve()
        requested_file = (static_root / requested_path).resolve()
        if requested_file.is_relative_to(static_root) and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(static_root / "index.html")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
