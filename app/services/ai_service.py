import json
import re
import asyncio
from app.config import settings
from app.utils.sanitize import sanitize_error_payload

# Debug print
print(f"🔍 ai_service: AI Provider = {settings.ai_provider}")
print(f"🔍 Groq Model: {settings.groq_model}")
print(f"🔍 OpenAI Model: {settings.openai_model}")
print(f"🔍 AI Timeout: {settings.ai_timeout_seconds}s")

# Initialize the appropriate client
client = None
provider_name = "None"

if settings.USE_GROQ and settings.GROQ_API_KEY:
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        provider_name = "Groq"
        print(f"✅ {provider_name} client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Groq client: {e}")
elif settings.OPENAI_API_KEY and not settings.USE_GROQ:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        provider_name = "OpenAI"
        print(f"✅ {provider_name} client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")
else:
    print("⚠️ No AI provider configured. AI analysis disabled.")


def _safe_parse_json(content: str) -> dict:
    """
    Safely parse JSON from AI response with fallback.
    """
    # Try direct parse first
    try:
        return json.loads(content)
    except Exception:
        pass
    
    # Try to extract JSON from the content using regex
    try:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    
    # Last resort: return empty dict
    return {}


async def _call_ai_with_retry(messages: list, model: str) -> str:
    """
    Call AI with timeout and retry logic.
    """
    last_error = None
    
    for attempt in range(settings.ai_max_retries + 1):
        try:
            print(f"🔍 AI attempt {attempt + 1}/{settings.ai_max_retries + 1}")
            
            if settings.USE_GROQ:
                # Groq - sync wrapped in async
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.chat.completions.create,
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=350,
                        response_format={"type": "json_object"}
                    ),
                    timeout=settings.ai_timeout_seconds
                )
            else:
                # OpenAI - async
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=350,
                        response_format={"type": "json_object"}
                    ),
                    timeout=settings.ai_timeout_seconds
                )
            
            return response.choices[0].message.content
            
        except asyncio.TimeoutError:
            last_error = f"AI request timed out after {settings.ai_timeout_seconds}s"
            print(f"⚠️ {last_error} (attempt {attempt + 1})")
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ AI call failed: {last_error} (attempt {attempt + 1})")
    
    raise Exception(last_error)


async def analyze_error(error_data: dict, log_action=None, db=None) -> dict:
    """
    Analyze an error using AI (Groq or OpenAI)
    
    Args:
        error_data: Dictionary with error details
        log_action: Optional async function to log audit events
        db: Optional database session for audit logging
    """
    
    print(f"🔍 analyze_error: Using provider = {provider_name}")
    
    if client is None:
        return {
            "root_cause": "No AI provider configured. Please set GROQ_API_KEY or OPENAI_API_KEY.",
            "suggested_fix": "Configure an AI provider in your .env file.",
            "fix_explanation": "AI analysis is disabled because no provider was configured.",
            "confidence": 0.0
        }
    
    # Sanitize error data before sending to AI
    sanitized_error = sanitize_error_payload(error_data)
    
    # Build the prompt
    prompt = f"""
You are an expert software engineer and debugger. Analyze this error and provide a fix.

ERROR DETAILS:
Type: {sanitized_error.get('type', 'Unknown')}
Message: {sanitized_error.get('message', 'No message')}
Severity: {sanitized_error.get('severity', 'error')}
Environment: {sanitized_error.get('environment', 'production')}
File: {sanitized_error.get('url', 'Unknown')}

STACK TRACE:
{sanitized_error.get('stack_trace', 'No stack trace available')}

TASK: Provide:
1. Root Cause Analysis: Explain what's causing this error (max 3 sentences)
2. Suggested Fix: Provide the exact code change needed
3. Fix Explanation: Explain why this fix works
4. Confidence Score: 0-100

FORMAT YOUR RESPONSE AS VALID JSON:
{{
    "root_cause": "...",
    "suggested_fix": "...",
    "fix_explanation": "...",
    "confidence": 85
}}
"""
    
    # Select model
    if settings.USE_GROQ:
        model = settings.groq_model
    else:
        model = settings.openai_model
    
    messages = [
        {"role": "system", "content": "You are a debugging expert. Provide precise, actionable fixes in valid JSON format only. Always include root_cause, suggested_fix, fix_explanation, and confidence fields."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        # Call AI with timeout and retry
        content = await _call_ai_with_retry(messages, model)
        result = _safe_parse_json(content)
        
        print(f"✅ {provider_name} analysis complete")
        
        # ✅ Log success if log_action is provided
        if log_action and db:
            await log_action(
                db=db,
                user_id=None,
                project_id=error_data.get('project_id', 0),
                action="ai_analysis_completed",
                details={
                    "error_id": error_data.get('id'),
                    "confidence": result.get("confidence", 50) / 100,
                    "provider": provider_name,
                    "model": model
                }
            )
        
        return {
            "root_cause": result.get("root_cause", "Unable to determine root cause."),
            "suggested_fix": result.get("suggested_fix", "No fix could be generated."),
            "fix_explanation": result.get("fix_explanation", "No explanation provided."),
            "confidence": result.get("confidence", 50) / 100  # 0-100 → 0-1
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ AI analysis error ({provider_name}): {error_msg}")
        
        # ✅ Log failure if log_action is provided
        if log_action and db:
            await log_action(
                db=db,
                user_id=None,
                project_id=error_data.get('project_id', 0),
                action="ai_analysis_failed",
                details={
                    "error_id": error_data.get('id'),
                    "error": error_msg,
                    "provider": provider_name,
                    "model": model
                }
            )
        
        return {
            "root_cause": f"AI analysis failed: {error_msg}",
            "suggested_fix": "Check your AI provider configuration and try again.",
            "fix_explanation": "The AI analysis encountered an error and could not complete.",
            "confidence": 0.0
        }