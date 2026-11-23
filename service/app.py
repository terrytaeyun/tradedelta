"""HTTP entry point for TradeDelta's comparison and question workflows."""

from functools import partial
from os import getenv
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from .assistant import DEFAULT_MODEL, AgentError, answer_question
from .customs import TradeDataError, build_comparison
from .exports import comparison_csv


app = FastAPI(title="TradeDelta", version="0.2.0")


class TradeScope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: Literal["sample", "customs"] = "sample"
    base: str = Field(default="2024", max_length=7)
    target: str = Field(default="2025", max_length=7)
    partners: list[str] = Field(default_factory=list, max_length=3)
    hs: str | None = Field(default=None, max_length=10)


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=600)
    trade: TradeScope | None = None
    use_model: bool = False


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return Path(__file__).with_name("index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {"model_configured": bool(getenv("OPENAI_API_KEY", "").strip()),
            "customs_configured": bool(getenv("KCS_SERVICE_KEY", "").strip()),
            "model": getenv("OPENAI_MODEL") or DEFAULT_MODEL}


@app.post("/api/compare")
def compare_trade(scope: TradeScope):
    try:
        return build_comparison(**scope.model_dump())
    except TradeDataError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/ask")
def ask(request: QuestionRequest):
    get_comparison = partial(compare_trade, request.trade) if request.trade else None
    try:
        result = answer_question(request.question, get_comparison, request.use_model)
    except AgentError as exc:
        raise HTTPException(502, str(exc)) from exc
    comparison = result["comparison"]
    result["comparison_csv"] = comparison_csv(comparison) if comparison is not None else None
    return result
