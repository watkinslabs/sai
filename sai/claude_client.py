"""
Claude API client for SAI
"""

import anthropic
from PyQt6.QtCore import QRunnable, QThreadPool

class AsyncClaudeWorker(QRunnable):
    """Worker for async Claude API calls"""
    
    def __init__(self, client, text, context, custom_prompt, mode, callback):
        super().__init__()
        self.client = client
        self.text = text
        self.context = context
        self.custom_prompt = custom_prompt
        self.mode = mode
        self.callback = callback
    
    def run(self):
        """Execute the API call in background"""
        try:
            response = self.client.get_response_sync(
                self.text, self.context, self.custom_prompt, self.mode
            )
            self.callback(response)
        except Exception as e:
            self.callback(f"Error: {str(e)}")

class ClaudeClient:
    """Optimized Claude API client with caching and async calls"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.response_cache = {}  # Simple LRU cache
        self.max_cache_size = 100
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(3)  # Limit concurrent API calls
    
    def _get_cache_key(self, text: str, context: str, mode: str) -> str:
        """Generate cache key for request"""
        return f"{mode}:{hash(text + context)}"
    
    def get_response_sync(self, text: str, context: str = "", custom_prompt: str = "", mode: str = "default") -> str:
        """Synchronous API call (for worker threads)"""
        try:
            # Check cache first
            cache_key = self._get_cache_key(text, context, mode)
            if cache_key in self.response_cache:
                return self.response_cache[cache_key]
            
            # Prompt templates for different modes (shortened for speed)
            prompts = {
                "default": f"Context: {context}\\nInput: \"{text}\"\\nBrief response (max 30 words):",
                
                "meeting": f"Meeting context: {context}\\nCurrent: \"{text}\"\\nKey point (max 20 words):",
                
                "learning": f"Context: {context}\\nTopic: \"{text}\"\\nQuick insight (max 25 words):",
                
                "summary": f"Context: {context}\\nText: \"{text}\"\\nSummary (max 25 words):",
                
                "custom": custom_prompt.format(text=text, context=context) if custom_prompt else f"Respond to: {text}"
            }
            
            prompt = prompts.get(mode, prompts["default"])

            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,  # Reduced for faster response
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for consistency
            )
            
            response = message.content[0].text if message.content else "No response"
            
            # Cache the response
            if len(self.response_cache) >= self.max_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self.response_cache))
                del self.response_cache[oldest_key]
            
            self.response_cache[cache_key] = response
            return response
            
        except Exception as e:
            return f"API Error: {str(e)}"
    
    def get_response_async(self, text: str, context: str = "", custom_prompt: str = "", mode: str = "default", callback=None):
        """Async API call using thread pool"""
        if not callback:
            return self.get_response_sync(text, context, custom_prompt, mode)
        
        # Check cache first (synchronously)
        cache_key = self._get_cache_key(text, context, mode)
        if cache_key in self.response_cache:
            callback(self.response_cache[cache_key])
            return
        
        # Queue worker for API call
        worker = AsyncClaudeWorker(self, text, context, custom_prompt, mode, callback)
        self.thread_pool.start(worker)