# app/db_models.py
from sqlalchemy import (Column, Integer, String, DateTime, Float, Boolean, JSON, LargeBinary, ForeignKeyConstraint, PrimaryKeyConstraint)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String)
    content = Column(String, nullable=False)
    predicted_label = Column(Integer)
    final_label = Column(Integer)
    is_reviewed = Column(Boolean, default=False, nullable=False)
    risk_score = Column(Float)
    sequence_risk = Column(Float)
    verdict = Column(String)
    explanation = Column(String)
    threat_intel = Column(JSON)
    __table_args__ = (
        PrimaryKeyConstraint('id', 'timestamp'),
    )

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    log_id = Column(Integer)
    log_timestamp = Column(DateTime(timezone=True))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    rule_name = Column(String)
    status = Column(String, default='New', nullable=False)
    mitre_tactic = Column(String)
    mitre_technique = Column(String)
    rule_description = Column(String)
    __table_args__ = (
        ForeignKeyConstraint(['log_id', 'log_timestamp'],
                             ['logs.id', 'logs.timestamp']),
    )

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String)
    role = Column(String, default="analyst")

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    username = Column(String)
    action = Column(String)
    resource = Column(String)
    ip_address = Column(String)
    result = Column(String)
    details = Column(String)

class ModelMetric(Base):
    __tablename__ = 'model_metrics'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    model_type = Column(String)
    version = Column(String)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)

class Cluster(Base):
    __tablename__ = 'cluster'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(String, unique=True, index=True)
    name = Column(String)
    status = Column(String, default='pending')
    log_count = Column(Integer)
    representative_log = Column(String)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    centroid = Column(LargeBinary)
    is_noise = Column(Boolean, default=False)
    confidence = Column(Float)
    predicted_label = Column(Integer)

class LogCluster(Base):
    __tablename__ = 'logCluster'
    log_id = Column(Integer, primary_key=True)
    cluster_id = Column(String, index=True)

class Playbook(Base):
    __tablename__ = 'playbooks'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # We will store the trigger logic and actions as flexible JSON
    trigger_conditions = Column(JSON, nullable=False)
    actions = Column(JSON, nullable=False)

class Honeytoken(Base):
    __tablename__ = 'honeytokens'
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False) # AWS_KEY, DB_CREDS, etc.
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String)
    trigger_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


# --- Phase 5: SOC Features ---

class Case(Base):
    """Investigation case for grouping related alerts"""
    __tablename__ = 'cases'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(String, default='Open')  # Open, In Progress, Resolved, Closed
    priority = Column(String, default='Medium')  # Low, Medium, High, Critical
    assigned_to = Column(Integer)  # User ID
    created_by = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CaseAlert(Base):
    """Links alerts to investigation cases"""
    __tablename__ = 'case_alerts'
    case_id = Column(Integer, primary_key=True)
    alert_id = Column(Integer, primary_key=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class AlertNote(Base):
    """Analyst notes on alerts"""
    __tablename__ = 'alert_notes'
    id = Column(Integer, primary_key=True)
    alert_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer)
    username = Column(String)
    note = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlaybookExecution(Base):
    """Logs of playbook executions"""
    __tablename__ = 'playbook_executions'
    id = Column(Integer, primary_key=True)
    playbook_id = Column(Integer, nullable=False, index=True)
    playbook_name = Column(String)
    triggered_by_log_id = Column(Integer)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    actions_executed = Column(JSON)
    status = Column(String, default='success')  # success, failed, partial
    error_message = Column(String)