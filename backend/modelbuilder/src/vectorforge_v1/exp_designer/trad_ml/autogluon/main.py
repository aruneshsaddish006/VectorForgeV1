from contextlib import asynccontextmanager

from fastapi import FastAPI

from vectorforge_v1.exp_designer.trad_ml.autogluon.api.config import router as config_router
from vectorforge_v1.exp_designer.trad_ml.autogluon.api.runs import router as runs_router
from vectorforge_v1.exp_designer.trad_ml.autogluon.api.workflow import router as workflow_router
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.artifact_forge.api.routes import router as artifact_forge_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ArtifactStore().mark_active_runs_failed("Server restarted; V1 in-memory graph checkpoints cannot resume active runs.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="VectorForge Backend V1", lifespan=lifespan)
    app.include_router(config_router)
    app.include_router(workflow_router)
    app.include_router(runs_router)
    app.include_router(artifact_forge_router)
    return app


app = create_app()
