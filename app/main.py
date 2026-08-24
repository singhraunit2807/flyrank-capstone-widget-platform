from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./capstone.db")
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    widgets: Mapped[list["Widget"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

class Widget(Base):
    __tablename__ = "widgets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), default="Get in touch")
    fields_json: Mapped[str] = mapped_column(Text, default='["name","email","message"]')
    tenant: Mapped[Tenant] = relationship(back_populates="widgets")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="widget", cascade="all, delete-orphan")

class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    widget_id: Mapped[str] = mapped_column(ForeignKey("widgets.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    geo_status: Mapped[str] = mapped_column(String(30), default="unknown")
    side_effect_status: Mapped[str] = mapped_column(String(60), default="not_configured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    widget: Mapped[Widget] = relationship(back_populates="submissions")

Base.metadata.create_all(engine)
app = FastAPI(title="Embeddable Widget & Lead-Capture Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",")], allow_credentials=False, allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"], allow_headers=["Authorization","Content-Type"])
_rate_windows: dict[str, deque[float]] = defaultdict(deque)

def db():
    session = SessionLocal()
    try: yield session
    finally: session.close()

def require_tenant(authorization: Optional[str], session: Session) -> Tenant:
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(401, "Bearer token required")
    tenant = session.scalar(select(Tenant).where(Tenant.token == authorization.split(" ", 1)[1].strip()))
    if not tenant: raise HTTPException(401, "Invalid token")
    return tenant

def rate_limit(ip: str):
    now = time.time(); window = _rate_windows[ip]
    while window and now - window[0] > RATE_LIMIT_WINDOW: window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        retry = max(1, int(RATE_LIMIT_WINDOW - (now - window[0])))
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(retry)})
    window.append(now)

class WidgetIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    title: str = Field(default="Get in touch", max_length=160)
    fields: list[str] = Field(default=["name","email","message"], min_length=1, max_length=10)
class WidgetOut(WidgetIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
class SubmissionIn(BaseModel):
    name: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=320)
    message: str = Field(default="", max_length=5000)
    website: str = Field(default="", max_length=200)

def seed_tenant(session: Session):
    if not session.scalar(select(Tenant)):
        session.add(Tenant(id=str(uuid.uuid4()), name="Demo Tenant", token="demo-token-change-me")); session.commit()

def widget_for_owner(widget_id: str, tenant: Tenant, session: Session) -> Widget:
    widget = session.scalar(select(Widget).where(Widget.id == widget_id, Widget.tenant_id == tenant.id))
    if not widget: raise HTTPException(404, "Widget not found")
    return widget

async def geo_lookup(ip: str) -> tuple[str, str, str]:
    for url in [os.getenv("GEO_PROVIDER_A_URL"), os.getenv("GEO_PROVIDER_B_URL")]:
        if not url: continue
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(url, params={"ip": ip}); r.raise_for_status(); data = r.json()
                return str(data.get("country", "")), str(data.get("city", "")), "provider"
        except Exception: continue
    return "", "", "unavailable"

async def send_side_effects(submission: Submission):
    webhook = os.getenv("WEBHOOK_URL")
    if not webhook: return "not_configured"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(webhook, json={"id":submission.id,"widget_id":submission.widget_id,"name":submission.name,"email":submission.email,"message":submission.message,"country":submission.country,"city":submission.city})
            r.raise_for_status()
        return "webhook_sent"
    except Exception: return "webhook_failed"

@app.on_event("startup")
def startup():
    with SessionLocal() as session: seed_tenant(session)

@app.get("/")
def health(): return {"service":"widget-platform","status":"ok"}

@app.post("/api/widgets", response_model=WidgetOut)
def create_widget(data: WidgetIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant = require_tenant(authorization, session); widget = Widget(id=str(uuid.uuid4()), tenant_id=tenant.id, name=data.name, title=data.title, fields_json=json.dumps(data.fields))
    session.add(widget); session.commit(); session.refresh(widget)
    return WidgetOut(id=widget.id, name=widget.name, title=widget.title, fields=json.loads(widget.fields_json))

@app.get("/api/widgets")
def list_widgets(authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant = require_tenant(authorization, session)
    return [{"id":w.id,"name":w.name,"title":w.title,"fields":json.loads(w.fields_json)} for w in session.scalars(select(Widget).where(Widget.tenant_id == tenant.id)).all()]

@app.patch("/api/widgets/{widget_id}")
def update_widget(widget_id: str, data: WidgetIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant = require_tenant(authorization, session); widget = widget_for_owner(widget_id, tenant, session)
    widget.name, widget.title, widget.fields_json = data.name, data.title, json.dumps(data.fields); session.commit()
    return {"id":widget.id,"name":widget.name,"title":widget.title,"fields":data.fields}

@app.delete("/api/widgets/{widget_id}", status_code=204)
def delete_widget(widget_id: str, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant = require_tenant(authorization, session); session.delete(widget_for_owner(widget_id, tenant, session)); session.commit(); return Response(status_code=204)

@app.get("/api/widgets/{widget_id}/embed")
def embed_snippet(widget_id: str, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant = require_tenant(authorization, session); widget_for_owner(widget_id, tenant, session); base=os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8000")
    return {"script":f'<script src="{base}/widget.js?id={widget_id}"></script>',"widget_id":widget_id}

@app.get("/api/widgets/{widget_id}/submissions")
def owner_submissions(widget_id: str, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant=require_tenant(authorization,session); widget_for_owner(widget_id,tenant,session); rows=session.scalars(select(Submission).where(Submission.widget_id==widget_id).order_by(Submission.created_at.desc())).all()
    return [{"id":x.id,"name":x.name,"email":x.email,"message":x.message,"country":x.country,"city":x.city,"created_at":x.created_at} for x in rows]

@app.post("/api/public/widgets/{widget_id}/submissions")
async def public_submit(widget_id: str, data: SubmissionIn, request: Request, session: Session = Depends(db)):
    if not session.get(Widget, widget_id): raise HTTPException(404,"Widget not found")
    ip=request.client.host if request.client else "unknown"; rate_limit(ip)
    if data.website.strip(): raise HTTPException(400,"Spam check failed")
    if not data.email and not data.message: raise HTTPException(422,"At least email or message is required")
    country,city,geo_status=await geo_lookup(ip)
    submission=Submission(id=str(uuid.uuid4()),widget_id=widget_id,name=data.name,email=data.email,message=data.message,ip=ip,country=country,city=city,geo_status=geo_status)
    session.add(submission); session.commit(); session.refresh(submission); submission.side_effect_status=await send_side_effects(submission); session.commit()
    return {"id":submission.id,"status":"accepted","geo_status":geo_status,"side_effect_status":submission.side_effect_status}

@app.get("/widget.js")
def widget_script(id: str):
    if not id: raise HTTPException(400,"Widget id is required")
    base=os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8000")
    js=f'''(function(){{const id={json.dumps(id)},base={json.dumps(base)};const root=document.currentScript.parentElement||document.body;const box=document.createElement("div");box.style.cssText="font-family:Arial;max-width:420px;padding:16px;border:1px solid #ddd;border-radius:10px";box.innerHTML='<strong>Get in touch</strong><form><input name="name" placeholder="Name" style="display:block;width:100%;margin:8px 0;padding:8px"><input name="email" placeholder="Email" style="display:block;width:100%;margin:8px 0;padding:8px"><textarea name="message" placeholder="Message" style="display:block;width:100%;margin:8px 0;padding:8px"></textarea><input name="website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px"><button>Send</button><span data-status style="margin-left:8px"></span></form>';root.appendChild(box);box.querySelector("form").onsubmit=async(e)=>{{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));const r=await fetch(base+"/api/public/widgets/"+id+"/submissions",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(body)}});box.querySelector("[data-status]").textContent=r.ok?"Thanks!":"Please try again.";}};}})();'''
    return Response(js,media_type="application/javascript")

@app.get("/api/dashboard/summary")
def dashboard_summary(authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant=require_tenant(authorization,session); total=session.scalar(select(func.count(Submission.id)).join(Widget).where(Widget.tenant_id==tenant.id)) or 0; widgets=session.scalar(select(func.count(Widget.id)).where(Widget.tenant_id==tenant.id)) or 0
    return {"widgets":widgets,"submissions":total}

@app.get("/api/dashboard/widgets/{widget_id}")
def widget_stats(widget_id: str, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant=require_tenant(authorization,session); widget_for_owner(widget_id,tenant,session); total=session.scalar(select(func.count(Submission.id)).where(Submission.widget_id==widget_id)) or 0
    return {"widget_id":widget_id,"submissions":total}

@app.get("/api/dashboard/geo")
def geo_stats(authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    tenant=require_tenant(authorization,session); rows=session.execute(select(Submission.country,func.count(Submission.id)).join(Widget).where(Widget.tenant_id==tenant.id).group_by(Submission.country)).all()
    return {"countries":[{"country":country or "unknown","count":count} for country,count in rows]}
