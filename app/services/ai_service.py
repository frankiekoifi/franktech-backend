import json
from app.config import settings

# Debug print
print(f"🔍 ai_service: AI Provider = {settings.ai_provider}")

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

async def analyze_error(error_data: dict) -> dict:
    """
    Analyze an error using AI (Groq or OpenAI)
    """
    
    print(f"🔍 analyze_error: Using provider = {provider_name}")
    
    if client is None:
        return {
            "root_cause": "No AI provider configured. Please set GROQ_API_KEY or OPENAI_API_KEY.",
            "suggested_fix": "Configure an AI provider in your .env file.",
            "fix_explanation": "AI analysis is disabled because no provider was configured.",
            "confidence": 0.0
        }
    
    # Build the prompt
    prompt = f"""
You are an expert software engineer and debugger. Analyze this error and provide a fix.

ERROR DETAILS:
Type: {error_data.get('type', 'Unknown')}
Message: {error_data.get('message', 'No message')}
Severity: {error_data.get('severity', 'error')}
Environment: {error_data.get('environment', 'production')}
File: {error_data.get('url', 'Unknown')}

STACK TRACE:
{error_data.get('stack_trace', 'No stack trace available')}

TASK: Provide:
1. Root Cause Analysis: Explain what's causing this error (max 3 sentences)
2. Suggested Fix: Provide the exact code change needed
3. Confidence Score: 0-100

FORMAT YOUR RESPONSE AS JSON:
{{
    "root_cause": "...",
    "suggested_fix": "...",
    "confidence": 85
}}
"""
    
    try:
        # Use the appropriate client
        if settings.USE_GROQ:
            print("🔍 Using Groq for analysis...")
            # Groq uses synchronous calls
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a debugging expert. Provide precise, actionable fixes in valid JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            print("✅ Groq analysis complete")
        else:
            print("🔍 Using OpenAI for analysis...")
            # OpenAI (async)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a debugging expert. Provide precise, actionable fixes in valid JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            print("✅ OpenAI analysis complete")
        
        return {
            "root_cause": result.get("root_cause", "No root cause provided"),
            "suggested_fix": result.get("suggested_fix", "No fix provided"),
            "fix_explanation": result.get("fix_explanation", ""),
            "confidence": result.get("confidence", 50) / 100
        }
        
    except Exception as e:
        print(f"❌ AI analysis error ({provider_name}): {e}")
        return {
            "root_cause": f"AI analysis failed: {str(e)}",
            "suggested_fix": "Check your AI provider configuration",
            "fix_explanation": "",
            "confidence": 0.0
        }