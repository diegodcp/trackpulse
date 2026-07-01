from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..replay.controller import (
    FixtureReplayController,
    ReplayCoordinateBounds,
    ReplayFixtureSummary,
    ReplayLocationPoint,
    ReplayStateSnapshot,
)
from ..settings import get_app_settings

router = APIRouter(prefix="/api/v1/replay", tags=["replay"])


class ReplayFixturesResponse(BaseModel):
    fixtures: list[ReplayFixtureSummary]


class ReplayStartRequest(BaseModel):
    fixture_id: str = Field(default="bahrain-2023-race")
    speed_multiplier: int = Field(default=1)


class ReplayStateResponse(BaseModel):
    fixture_id: str
    status: str
    speed_multiplier: int
    cursor: int
    total_points: int
    progress_pct: float
    replay_time: str | None
    active_location: ReplayLocationPoint | None
    coordinate_bounds: ReplayCoordinateBounds | None
    timeline_points: list[ReplayLocationPoint]


def _controller(request: Request) -> FixtureReplayController:
    controller = getattr(request.app.state, "replay_controller", None)
    if controller is None:
        controller = FixtureReplayController(get_app_settings(request))
        request.app.state.replay_controller = controller
    return controller


def _state_payload(snapshot: ReplayStateSnapshot) -> ReplayStateResponse:
    return ReplayStateResponse(
        fixture_id=snapshot.fixture_id,
        status=snapshot.status,
        speed_multiplier=snapshot.speed_multiplier,
        cursor=snapshot.cursor,
        total_points=snapshot.total_points,
        progress_pct=snapshot.progress_pct,
        replay_time=snapshot.replay_time,
        active_location=snapshot.active_location,
        coordinate_bounds=snapshot.coordinate_bounds,
        timeline_points=snapshot.timeline_points,
    )


@router.get("/fixtures", response_model=ReplayFixturesResponse)
async def list_replay_fixtures(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayFixturesResponse:
    return ReplayFixturesResponse(fixtures=controller.list_fixtures())


@router.post("/start", response_model=ReplayStateResponse)
async def start_replay(
    body: ReplayStartRequest,
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    try:
        snapshot = await controller.start(
            fixture_id=body.fixture_id,
            speed_multiplier=body.speed_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _state_payload(snapshot)


@router.post("/stop", response_model=ReplayStateResponse)
async def stop_replay(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    return _state_payload(await controller.stop())


@router.get("/state", response_model=ReplayStateResponse)
async def replay_state(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    return _state_payload(controller.snapshot())