# app/api/ai.py
"""
AI-powered analysis API endpoints.
Provides LLM-based trend insights, incident summarization, and remediation suggestions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app import auth_utils
from app.services.llm_service import LLMService, get_llm_manager
from app.api.dashboard import get_historical_trends, get_log_context, get_alerts
from app.rate_limiter import limiter
from app.audit import audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])


class ProviderSwitchRequest(BaseModel):
    provider: str


class AIResponse(BaseModel):
    content: str
    provider: str
    cached: bool = False


@router.get("/insights", response_model=AIResponse)
@limiter.limit("10/minute")
async def get_ai_insights(
    request: Request,
    background_tasks: BackgroundTasks,
    interval: str = "h",
    user: dict = Depends(auth_utils.get_current_user)
):
    """
    Generate AI-powered insights for historical trend data.
    Analyzes anomaly patterns and provides actionable recommendations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get historical trend data
        from fastapi import Response
        response = Response()
        trends = await get_historical_trends(response, interval, user)
        
        if not trends or len(trends) < 2:
            return AIResponse(
                content="Insufficient data to generate insights. Need at least 2 data points.",
                provider="none",
                cached=False
            )
        
        # Generate insights
        service = LLMService()
        content, provider = await service.generate_trend_insights(trends)
        
        # Audit log the AI query
        client_ip = request.client.host if request.client else "unknown"
        background_tasks.add_task(
            audit.log, user.get("username"), audit.ACTION_AI_QUERY, 
            "insights", client_ip, "success"
        )
        
        return AIResponse(
            content=content,
            provider=provider,
            cached=False  # Cache status is internal
        )
        
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate insights: {str(e)}"
        )


@router.get("/summarize/{alert_id}", response_model=AIResponse)
@limiter.limit("10/minute")
async def get_incident_summary(
    alert_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    user: dict = Depends(auth_utils.get_current_user)
):
    """
    Generate an executive summary for a specific alert/incident.
    Provides context and severity assessment.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get alert details
        from sqlalchemy import create_engine, text
        from app.config import settings
        
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT a.id, a.status, a.rule_name, a.rule_description, 
                       a.mitre_tactic, a.mitre_technique, 
                       l.timestamp, l.content, l.risk_score, l.threat_intel, l.id as log_id
                FROM alerts a JOIN logs l ON a.log_id = l.id
                WHERE a.id = :alert_id
            """), {"alert_id": alert_id}).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            alert = dict(result._mapping)
        
        # Get surrounding context logs
        if alert.get('timestamp'):
            context_logs = await get_log_context(
                str(alert['timestamp']), 
                user
            )
        else:
            context_logs = []
        
        # Generate summary
        service = LLMService()
        content, provider = await service.summarize_incident(alert, context_logs)
        
        return AIResponse(
            content=content,
            provider=provider,
            cached=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating incident summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.get("/remediation/{alert_id}", response_model=AIResponse)
@limiter.limit("10/minute")
async def get_remediation_suggestions(
    alert_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    user: dict = Depends(auth_utils.get_current_user)
):
    """
    Generate AI-powered remediation suggestions for an alert.
    Provides immediate actions, investigation steps, and long-term recommendations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        from sqlalchemy import create_engine, text
        from app.config import settings
        import json
        
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT a.id, a.status, a.rule_name, a.rule_description, 
                       a.mitre_tactic, a.mitre_technique, 
                       l.timestamp, l.content, l.risk_score, l.threat_intel, l.id as log_id
                FROM alerts a JOIN logs l ON a.log_id = l.id
                WHERE a.id = :alert_id
            """), {"alert_id": alert_id}).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            alert = dict(result._mapping)
        
        # Parse threat intel if available
        threat_intel = None
        if alert.get('threat_intel'):
            try:
                threat_intel = json.loads(alert['threat_intel']) if isinstance(alert['threat_intel'], str) else alert['threat_intel']
            except:
                pass
        
        # Generate remediation suggestions
        service = LLMService()
        content, provider = await service.suggest_remediation(alert, threat_intel)
        
        return AIResponse(
            content=content,
            provider=provider,
            cached=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating remediation suggestions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate remediation: {str(e)}"
        )


@router.get("/providers/status")
async def get_providers_status(
    user: dict = Depends(auth_utils.get_current_user)
):
    """
    Get status of all LLM providers.
    Shows which providers are available, rate-limited, or not configured.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    manager = get_llm_manager()
    return manager.get_status()


@router.post("/providers/switch")
async def switch_provider(
    request: ProviderSwitchRequest,
    user: dict = Depends(auth_utils.get_current_user)
):
    """
    Manually switch to a specific LLM provider.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    manager = get_llm_manager()
    
    valid_providers = ["gemini", "groq", "mistral", "openrouter", "together", "ollama"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        )
    
    success = manager.switch_provider(request.provider)
    
    if success:
        return {
            "message": f"Switched to {request.provider}",
            "current_provider": request.provider
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot switch to {request.provider}. Provider may not be configured."
        )
