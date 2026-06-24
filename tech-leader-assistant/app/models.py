from sqlalchemy import Column, Integer, String, DateTime, JSON, MetaData
from app.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)
    project_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, index=True)
    data = Column(JSON)
