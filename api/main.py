import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv(Path(__file__).with_name(".env"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./alumni_connect.db")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-before-production")
if ENVIRONMENT in {"production", "preview"} or os.getenv("VERCEL_ENV"):
    if DATABASE_URL.startswith("sqlite:"):
        raise RuntimeError("DATABASE_URL must point to Neon/PostgreSQL outside local development")
    if JWT_SECRET == "change-this-before-production" or len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must be a unique value of at least 32 characters")
ALGORITHM = "HS256"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
security = HTTPBearer()

def hash_password(password: str) -> str:
    try:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except ValueError as error:
        raise HTTPException(422, "Password must be at most 72 bytes long") from error

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False

class Base(DeclarativeBase): pass
class Alumni(Base):
    __tablename__ = "alumni"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    student_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    degree: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    major: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    batch_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    directory_visible: Mapped[str] = mapped_column(String(20), default="alumni")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("requester_id", "recipient_id", name="uq_connection_direction"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("group_id", "alumni_id", name="uq_group_member"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    alumni_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    details: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(180), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("alumni.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EventRsvp(Base):
    __tablename__ = "event_rsvps"
    __table_args__ = (UniqueConstraint("event_id", "alumni_id", name="uq_event_rsvp"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    alumni_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)

class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    company: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(180), default="")
    employment_type: Mapped[str] = mapped_column(String(60), default="Full-time")
    created_by: Mapped[int] = mapped_column(ForeignKey("alumni.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class OpportunityApplication(Base):
    __tablename__ = "opportunity_applications"
    __table_args__ = (UniqueConstraint("opportunity_id", "alumni_id", name="uq_opportunity_application"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    alumni_id: Mapped[int] = mapped_column(ForeignKey("alumni.id"), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    degree: Optional[str] = None
    batch: Optional[int] = None
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
class ProfileUpdate(BaseModel):
    student_number: Optional[str] = None; degree: Optional[str] = None; major: Optional[str] = None
    batch_year: Optional[int] = None; job_title: Optional[str] = None; company: Optional[str] = None
    location: Optional[str] = None; bio: Optional[str] = None; directory_visible: Optional[str] = None
class MessageIn(BaseModel):
    recipient_id: int; body: str = Field(min_length=1, max_length=2000)
class GroupIn(BaseModel):
    name: str = Field(min_length=3, max_length=120); description: str = Field(default="", max_length=1000)
class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=180); details: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=180); starts_at: datetime
class OpportunityIn(BaseModel):
    title: str = Field(min_length=3, max_length=180); company: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=2000); location: str = Field(default="", max_length=180)
    employment_type: str = Field(default="Full-time", max_length=60)
class ApplicationIn(BaseModel):
    note: str = Field(default="", max_length=2000)

app = FastAPI(title="ISPSC Alumni Connect API")
allowed_origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def public(a: Alumni):
    return {"id":a.id,"name":a.name,"degree":a.degree,"major":a.major,"batch_year":a.batch_year,"job_title":a.job_title,"company":a.company,"location":a.location,"bio":a.bio,"role":a.role,"directory_visible":a.directory_visible}
def private(a: Alumni):
    data = public(a); data.update({"email": a.email, "student_number": a.student_number}); return data
def connection_public(connection: Connection, other: Alumni):
    return {"id": connection.id, "status": connection.status, "created_at": connection.created_at, "alumni": public(other)}
def token_for(a: Alumni):
    exp=datetime.now(timezone.utc)+timedelta(days=7)
    return jwt.encode({"sub":str(a.id),"role":a.role,"exp":exp},JWT_SECRET,algorithm=ALGORITHM)
def current_user(credentials: HTTPAuthorizationCredentials=Depends(security), db: Session=Depends(db_session)):
    try: payload=jwt.decode(credentials.credentials,JWT_SECRET,algorithms=[ALGORITHM]); uid=int(payload.get("sub"))
    except (JWTError, TypeError, ValueError): raise HTTPException(401,"Invalid session")
    user=db.get(Alumni,uid)
    if not user: raise HTTPException(401,"Account not found")
    return user
def admin_only(user: Alumni=Depends(current_user)):
    if user.role != "admin": raise HTTPException(403,"Administrator access required")
    return user

@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session=Depends(db_session)):
    if db.scalar(select(Alumni).where(Alumni.email==data.email)): raise HTTPException(409,"Email is already registered")
    alum=Alumni(name=data.name,email=data.email,password_hash=hash_password(data.password),degree=data.degree,batch_year=data.batch,consent_at=datetime.now(timezone.utc))
    db.add(alum); db.commit(); db.refresh(alum)
    return {"access_token":token_for(alum),"token_type":"bearer","user":private(alum)}
@app.post("/api/auth/login")
def login(data: LoginIn, db: Session=Depends(db_session)):
    alum=db.scalar(select(Alumni).where(Alumni.email==data.email))
    if not alum or not verify_password(data.password,alum.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token_for(alum),"token_type":"bearer","user":private(alum)}
@app.get("/api/me")
def me(user: Alumni=Depends(current_user)): return private(user)
@app.patch("/api/me")
def update_me(data: ProfileUpdate, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(user,k,v)
    db.commit(); db.refresh(user); return private(user)
@app.get("/api/alumni")
def directory(q: str="", batch: Optional[int]=None, db: Session=Depends(db_session), _: Alumni=Depends(current_user)):
    stmt=select(Alumni).where(Alumni.directory_visible != "private")
    if batch: stmt=stmt.where(Alumni.batch_year==batch)
    if q:
        term=f"%{q.lower()}%"
        stmt=stmt.where((Alumni.name.ilike(term)) | (Alumni.degree.ilike(term)) | (Alumni.job_title.ilike(term)) | (Alumni.company.ilike(term)))
    return [public(a) for a in db.scalars(stmt.order_by(Alumni.name).limit(100)).all()]
@app.get("/api/connections")
def connections(db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    rows = db.scalars(select(Connection).where(or_(Connection.requester_id == user.id, Connection.recipient_id == user.id)).order_by(Connection.created_at.desc())).all()
    result = []
    for row in rows:
        other = db.get(Alumni, row.recipient_id if row.requester_id == user.id else row.requester_id)
        if other:
            item = connection_public(row, other)
            item["direction"] = "outgoing" if row.requester_id == user.id else "incoming"
            result.append(item)
    return result
@app.post("/api/connections/{alumni_id}", status_code=status.HTTP_201_CREATED)
def request_connection(alumni_id: int, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    if alumni_id == user.id: raise HTTPException(400, "You cannot connect with your own profile")
    other = db.get(Alumni, alumni_id)
    if not other or other.directory_visible == "private": raise HTTPException(404, "Alumni profile not found")
    existing = db.scalar(select(Connection).where(or_((Connection.requester_id == user.id) & (Connection.recipient_id == alumni_id), (Connection.requester_id == alumni_id) & (Connection.recipient_id == user.id))))
    if existing:
        if existing.requester_id == alumni_id and existing.status == "pending":
            existing.status = "accepted"; db.commit(); db.refresh(existing)
            return connection_public(existing, other)
        raise HTTPException(409, "A connection request already exists")
    row = Connection(requester_id=user.id, recipient_id=alumni_id)
    db.add(row); db.commit(); db.refresh(row)
    return connection_public(row, other)
@app.post("/api/connections/{connection_id}/accept")
def accept_connection(connection_id: int, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = db.get(Connection, connection_id)
    if not row or row.recipient_id != user.id: raise HTTPException(404, "Connection request not found")
    row.status = "accepted"; db.commit(); db.refresh(row)
    other = db.get(Alumni, row.requester_id)
    return connection_public(row, other)

def message_public(row: Message, viewer_id: int, db: Session):
    other = db.get(Alumni, row.recipient_id if row.sender_id == viewer_id else row.sender_id)
    return {"id": row.id, "body": row.body, "created_at": row.created_at, "outgoing": row.sender_id == viewer_id, "other": public(other) if other else None}

@app.get("/api/messages")
def messages(db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    rows = db.scalars(select(Message).where(or_(Message.sender_id == user.id, Message.recipient_id == user.id)).order_by(Message.created_at.desc()).limit(200)).all()
    return [message_public(row, user.id, db) for row in rows]

@app.post("/api/messages", status_code=status.HTTP_201_CREATED)
def send_message(data: MessageIn, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    if data.recipient_id == user.id: raise HTTPException(400, "You cannot send a message to yourself")
    if not db.get(Alumni, data.recipient_id): raise HTTPException(404, "Recipient not found")
    row = Message(sender_id=user.id, recipient_id=data.recipient_id, body=data.body.strip())
    db.add(row); db.commit(); db.refresh(row)
    return message_public(row, user.id, db)

def group_public(row: Group, user_id: int, db: Session):
    members = db.scalars(select(GroupMembership).where(GroupMembership.group_id == row.id)).all()
    return {"id": row.id, "name": row.name, "description": row.description, "created_at": row.created_at, "member_count": len(members), "joined": any(item.alumni_id == user_id for item in members)}

@app.get("/api/groups")
def groups(db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    return [group_public(row, user.id, db) for row in db.scalars(select(Group).order_by(Group.created_at.desc())).all()]

@app.post("/api/groups", status_code=status.HTTP_201_CREATED)
def create_group(data: GroupIn, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    if db.scalar(select(Group).where(Group.name.ilike(data.name.strip()))): raise HTTPException(409, "A group with that name already exists")
    row = Group(name=data.name.strip(), description=data.description.strip(), owner_id=user.id)
    db.add(row); db.flush(); db.add(GroupMembership(group_id=row.id, alumni_id=user.id)); db.commit(); db.refresh(row)
    return group_public(row, user.id, db)

@app.post("/api/groups/{group_id}/join")
def join_group(group_id: int, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = db.get(Group, group_id)
    if not row: raise HTTPException(404, "Group not found")
    if not db.scalar(select(GroupMembership).where(GroupMembership.group_id == group_id, GroupMembership.alumni_id == user.id)):
        db.add(GroupMembership(group_id=group_id, alumni_id=user.id)); db.commit()
    return group_public(row, user.id, db)

def event_public(row: Event, user_id: int, db: Session):
    rsvps = db.scalars(select(EventRsvp).where(EventRsvp.event_id == row.id)).all()
    return {"id": row.id, "title": row.title, "details": row.details, "location": row.location, "starts_at": row.starts_at, "created_at": row.created_at, "rsvp_count": len(rsvps), "rsvped": any(item.alumni_id == user_id for item in rsvps)}

@app.get("/api/events")
def events(db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    return [event_public(row, user.id, db) for row in db.scalars(select(Event).order_by(Event.starts_at.asc())).all()]

@app.post("/api/events", status_code=status.HTTP_201_CREATED)
def create_event(data: EventIn, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = Event(title=data.title.strip(), details=data.details.strip(), location=data.location.strip(), starts_at=data.starts_at, created_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return event_public(row, user.id, db)

@app.post("/api/events/{event_id}/rsvp")
def rsvp_event(event_id: int, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = db.get(Event, event_id)
    if not row: raise HTTPException(404, "Event not found")
    if not db.scalar(select(EventRsvp).where(EventRsvp.event_id == event_id, EventRsvp.alumni_id == user.id)):
        db.add(EventRsvp(event_id=event_id, alumni_id=user.id)); db.commit()
    return event_public(row, user.id, db)

def opportunity_public(row: Opportunity, user_id: int, db: Session):
    applied = db.scalar(select(OpportunityApplication).where(OpportunityApplication.opportunity_id == row.id, OpportunityApplication.alumni_id == user_id)) is not None
    return {"id": row.id, "title": row.title, "company": row.company, "description": row.description, "location": row.location, "employment_type": row.employment_type, "created_at": row.created_at, "applied": applied}

@app.get("/api/opportunities")
def opportunity_list(db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    return [opportunity_public(row, user.id, db) for row in db.scalars(select(Opportunity).order_by(Opportunity.created_at.desc())).all()]

@app.post("/api/opportunities", status_code=status.HTTP_201_CREATED)
def create_opportunity(data: OpportunityIn, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = Opportunity(title=data.title.strip(), company=data.company.strip(), description=data.description.strip(), location=data.location.strip(), employment_type=data.employment_type.strip(), created_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return opportunity_public(row, user.id, db)

@app.post("/api/opportunities/{opportunity_id}/apply")
def apply_opportunity(opportunity_id: int, data: ApplicationIn, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    row = db.get(Opportunity, opportunity_id)
    if not row: raise HTTPException(404, "Opportunity not found")
    if db.scalar(select(OpportunityApplication).where(OpportunityApplication.opportunity_id == opportunity_id, OpportunityApplication.alumni_id == user.id)):
        raise HTTPException(409, "You have already applied for this opportunity")
    db.add(OpportunityApplication(opportunity_id=opportunity_id, alumni_id=user.id, note=data.note.strip()))
    db.commit(); return opportunity_public(row, user.id, db)
@app.get("/api/admin/overview")
def admin_overview(db: Session=Depends(db_session), _: Alumni=Depends(admin_only)):
    people=db.scalars(select(Alumni)).all()
    return {"total_profiles":len(people),"employment_confirmed":sum(bool(x.job_title) for x in people),"recent": [public(x) for x in people[-10:]]}
