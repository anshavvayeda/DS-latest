"""
Translation Service using OpenRouter

Provides translation capabilities using OpenRouter API.
No Emergent key required.
"""

import os
import json
import hashlib
from typing import Optional, Dict
import logging
import uuid
from dotenv import load_dotenv
from pathlib import Path
import httpx

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
TRANSLATION_MODEL = "google/gemini-2.5-flash-lite"


async def call_openrouter_for_translation(prompt: str, system_message: str, timeout: float = 60.0) -> Optional[str]:
    """Call OpenRouter API for translation."""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not configured for translation")
        return None
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://test-eval-debug.preview.emergentagent.com",
        "X-Title": "StudyBuddy Translation"
    }
    
    payload = {
        "model": TRANSLATION_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.3
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OPENROUTER_BASE_URL, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"OpenRouter translation error: {response.status_code}")
                return None
            
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error(f"Translation API call failed: {e}")
        return None


def get_translation_cache_key(text: str, from_lang: str, to_lang: str, context: str = "") -> str:
    """Generate cache key for translation"""
    key_data = f"{text}:{from_lang}:{to_lang}:{context}"
    return hashlib.md5(key_data.encode()).hexdigest()


async def translate_text(
    text: str,
    from_language: str = "english",
    to_language: str = "gujarati",
    context: str = "general",
    redis_client = None
) -> Optional[str]:
    """
    Translate text using OpenRouter with Redis caching.
    
    Args:
        text: Text to translate
        from_language: Source language (default: english)
        to_language: Target language (default: gujarati)
        context: Context for better translation (e.g., 'education', 'ui', 'button')
        redis_client: Redis client for caching
    
    Returns:
        Translated text or None if translation fails
    """
    if not OPENROUTER_API_KEY:
        logger.error("OpenRouter API key not configured for translation")
        return None
    
    # Check cache first
    cache_key = get_translation_cache_key(text, from_language, to_language, context)
    
    if redis_client:
        try:
            cached = redis_client.get(f"translation:{cache_key}")
            if cached:
                logger.info(f"Translation cache HIT: {cache_key[:8]}")
                return cached
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")
    
    # Translate using OpenRouter
    system_message = f"You are an expert translator specializing in {from_language} to {to_language} translation. Provide accurate, natural translations that preserve meaning and context."
    
    prompt = f"""Translate the following {context} text from {from_language} to {to_language}.

IMPORTANT RULES:
1. Maintain the exact same formatting (line breaks, bullet points, etc.)
2. Keep any HTML tags, markdown syntax, or special characters unchanged
3. Preserve numbers, dates, and proper nouns appropriately
4. Return ONLY the translated text, no explanations

Text to translate:
{text}

Translation:"""
    
    translated = await call_openrouter_for_translation(prompt, system_message)
    
    if translated:
        # Cache the translation (30 days)
        if redis_client:
            try:
                redis_client.setex(f"translation:{cache_key}", 2592000, translated)
                logger.info(f"Translation cached: {cache_key[:8]}")
            except Exception as e:
                logger.warning(f"Failed to cache translation: {e}")
        
        return translated
    
    return None


async def translate_content(
    content: Dict,
    from_language: str = "english",
    to_language: str = "gujarati",
    redis_client = None
) -> Optional[Dict]:
    """
    Translate structured content (like revision notes, flashcards, etc.)
    
    Args:
        content: Dictionary containing content to translate
        from_language: Source language
        to_language: Target language
        redis_client: Redis client for caching
    
    Returns:
        Translated content dictionary or None
    """
    if not content:
        return None
    
    # Generate cache key for entire content
    content_str = json.dumps(content, sort_keys=True)
    cache_key = get_translation_cache_key(content_str, from_language, to_language, "structured")
    
    # Check cache
    if redis_client:
        try:
            cached = redis_client.get(f"translation:{cache_key}")
            if cached:
                logger.info(f"Structured translation cache HIT: {cache_key[:8]}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
    
    # Translate using OpenRouter
    system_message = f"You are an expert translator. Translate structured educational content from {from_language} to {to_language} accurately."
    
    prompt = f"""Translate this structured educational content from {from_language} to {to_language}.

RULES:
1. Maintain the exact same JSON structure
2. Translate all text values (strings, array items)
3. Keep all keys in English (don't translate keys)
4. Preserve all numbers, IDs, and boolean values
5. Return ONLY the translated JSON, no explanations

Content to translate:
{json.dumps(content, indent=2)}

Translated JSON:"""
    
    response = await call_openrouter_for_translation(prompt, system_message, timeout=90.0)
    
    if response:
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                translated_content = json.loads(json_match.group(0))
                
                # Cache the translation
                if redis_client:
                    try:
                        redis_client.setex(f"translation:{cache_key}", 2592000, json.dumps(translated_content))
                        logger.info(f"Structured translation cached: {cache_key[:8]}")
                    except Exception as e:
                        logger.warning(f"Failed to cache: {e}")
                
                return translated_content
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translated JSON: {e}")
    
    return None


async def translate_batch(
    texts: list,
    from_language: str = "english",
    to_language: str = "gujarati",
    context: str = "general",
    redis_client = None
) -> Dict[str, str]:
    """
    Translate multiple texts in a single LLM call for efficiency.
    
    Returns:
        Dictionary mapping original text to translated text
    """
    if not texts or not OPENROUTER_API_KEY:
        return {}
    
    translations = {}
    texts_to_translate = []
    
    # Check cache for each text
    for text in texts:
        cache_key = get_translation_cache_key(text, from_language, to_language, context)
        if redis_client:
            try:
                cached = redis_client.get(f"translation:{cache_key}")
                if cached:
                    translations[text] = cached
                    continue
            except:
                pass
        texts_to_translate.append(text)
    
    # If all cached, return
    if not texts_to_translate:
        return translations
    
    # Translate remaining texts in batch
    system_message = f"You are an expert translator. Translate from {from_language} to {to_language} with high accuracy."
    
    # Create numbered list for batch translation
    numbered_texts = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts_to_translate)])
    
    prompt = f"""Translate these {context} texts from {from_language} to {to_language}.
Return the translations in the same numbered format, one per line.

{numbered_texts}

Translations:"""
    
    response = await call_openrouter_for_translation(prompt, system_message, timeout=90.0)
    
    if response:
        # Parse numbered responses
        lines = response.strip().split('\n')
        import re
        for i, text in enumerate(texts_to_translate):
            if i < len(lines):
                # Remove number prefix if present
                translated = lines[i]
                translated = re.sub(r'^\d+\.\s*', '', translated)
                translations[text] = translated
                
                # Cache individual translation
                if redis_client:
                    try:
                        cache_key = get_translation_cache_key(text, from_language, to_language, context)
                        redis_client.setex(f"translation:{cache_key}", 2592000, translated)
                    except:
                        pass
    
    return translations
