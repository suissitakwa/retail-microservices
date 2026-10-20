from typing import Annotated

from fastapi import Depends, FastAPI

from recovery_agent.auth import Principal, current_principal

app = FastAPI(title="recovery-agent", version="0.1.0")


@app.get("/health")
def liveness() -> dict[str, str]:
    """Unauthenticated liveness probe for Docker/Kubernetes; not routed through the gateway."""
    return {"status": "UP"}


@app.get("/api/v1/recovery/health")
def authenticated_health(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
    """Proves a gateway-routed request carries a token this service accepts."""
    return {"status": "UP", "subject": principal.email, "roles": sorted(principal.roles)}
