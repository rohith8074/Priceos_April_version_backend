import os
import json
import re
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

TOOL_LOOP_PATTERNS = [
    "maximum number of tool calls",
    "i've reached the maximum",
    "reached the maximum number of tool calls",
    "tool calls allowed",
]

TOOL_LOOP_FALLBACK = "I hit a processing limit on that request. Could you rephrase or ask a simpler question?"

def get_lyzr_config() -> Tuple[str, str]:
    chat_url = os.environ.get("LYZR_API_URL", "https://agent.api.lyzr.ai/v3/inference/chat")
    api_key = os.environ.get("LYZR_API_KEY", "")
    return chat_url, api_key

def is_tool_loop_error(text: str) -> bool:
    lower_text = text.lower()
    return any(p in lower_text for p in TOOL_LOOP_PATTERNS)

def extract_lyzr_message(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    
    if isinstance(data.get("response"), str):
        return data["response"]
    
    resp_obj = data.get("response", {})
    if isinstance(resp_obj, dict):
        if "message" in resp_obj:
            return str(resp_obj["message"])
        result_obj = resp_obj.get("result", {})
        if isinstance(result_obj, dict):
            if "message" in result_obj: return str(result_obj["message"])
            if "text" in result_obj: return str(result_obj["text"])
            if "answer" in result_obj: return str(result_obj["answer"])
        if "data" in resp_obj:
            return str(resp_obj["data"])
            
    if isinstance(data.get("message"), str):
        return data["message"]
        
    choices = data.get("choices", [])
    if choices and isinstance(choices, list) and isinstance(choices[0].get("message", {}).get("content"), str):
        return choices[0]["message"]["content"]
        
    if isinstance(data.get("result"), str):
        return data["result"]
    if isinstance(data.get("output"), str):
        return data["output"]
        
    return ""

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    cleaned = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'```\s*', '', cleaned, flags=re.IGNORECASE).strip()
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None

class LyzrCallResult:
    def __init__(self, response: str, raw: Any, ok: bool, parsed_json: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        self.response = response
        self.raw = raw
        self.ok = ok
        self.parsed_json = parsed_json
        self.error = error

async def stream_lyzr_agent(
    agent_id: str,
    message: str,
    user_id: str = "priceos-user",
    session_id: Optional[str] = None,
    system_prompt_variables: Optional[Dict[str, Any]] = None,
    filter_variables: Optional[Dict[str, Any]] = None,
    features: Optional[List[Dict[str, Any]]] = None,
    timeout_ms: int = 120_000,
):
    """
    Streams events from Lyzr Agent V3 and yields them for SSE bridging.
    Captures tool_called, tool_output, thinking, and final response events.
    """
    import time
    chat_url, api_key = get_lyzr_config()
    # Use streaming endpoint if available, or just wrap the standard one for now
    # Actually Lyzr V3 uses a WebSocket for events, but we can also use the /stream endpoint
    stream_url = chat_url.replace("/chat", "/stream")
    
    if not session_id:
        session_id = f"session-{int(time.time() * 1000)}"

    payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "message": message,
        "stream": True
    }
    if system_prompt_variables: payload["system_prompt_variables"] = system_prompt_variables
    if filter_variables: payload["filter_variables"] = filter_variables
    if features: payload["features"] = features

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    print(f"\n{'='*60}")
    print(f"🚀 [LYZR STREAM START] Session: {session_id}")
    print(f"   Agent: {agent_id}")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=timeout_ms / 1000.0) as client:
        try:
            async with client.stream("POST", stream_url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    print(f"❌ [LYZR ERROR] {response.status_code}: {err_text.decode()}")
                    yield {"type": "error", "message": f"Lyzr Stream Error {response.status_code}"}
                    return

                full_response = ""
                async for line in response.aiter_lines():
                    if not line.strip(): continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]": break
                        
                        try:
                            # Log raw events for debugging
                            event_type = event.get("type", event.get("event_type", "unknown"))
                            
                            if event_type in ["tool_call", "tool_called", "tool_use"]:
                                tool_name = event.get("tool_name")
                                args = event.get("tool_args") or event.get("arguments") or {}
                                print(f"🛠️  [LYZR TOOL CALLED]: {tool_name} | args: {args}")
                                yield {"type": "agent_event", "payload": {
                                    "event_type": "tool_called",
                                    "tool_name": tool_name,
                                    "arguments": args,
                                    "status": "active",
                                    "timestamp": datetime.utcnow().isoformat()
                                }}
                            
                            elif event_type == "tool_output" or event_type == "tool_response":
                                tool_name = event.get("tool_name")
                                output = event.get("output") or event.get("response") or ""
                                print(f"✅ [LYZR TOOL OUTPUT]: {tool_name} | result: {str(output)[:150]}...")
                                yield {"type": "agent_event", "payload": {
                                    "event_type": "tool_output",
                                    "tool_name": tool_name,
                                    "status": "done",
                                    "tool_output": output,
                                    "timestamp": datetime.utcnow().isoformat()
                                }}

                            elif event_type in ["thinking", "thought", "agent_thinking"]:
                                msg = event.get("message") or event.get("thinking")
                                if msg:
                                    print(f"🧠 [LYZR THINKING]: {msg}")
                                    yield {"type": "thinking", "message": msg}
                                    # Also yield as agent_event for the graph
                                    yield {"type": "agent_event", "payload": {
                                        "event_type": "agent_thinking",
                                        "thinking": msg,
                                        "status": "active",
                                        "timestamp": datetime.utcnow().isoformat()
                                    }}

                            elif event_type == "content":
                                chunk = event.get("content", "")
                                full_response += chunk
                                yield {"type": "content", "content": chunk}
                        
                        except Exception as e:
                            # If it's not a valid JSON event object, it's likely a raw text chunk
                            print(f"📝 [LYZR RAW CHUNK]: {data_str[:50]}...")
                            full_response += data_str
                            yield {"type": "content", "content": data_str}

                print(f"{'='*60}")
                print(f"🏁 [LYZR STREAM COMPLETE] Full Response Length: {len(full_response)}")
                print(f"{'='*60}")
                
                yield {"type": "final_response", "content": full_response}

        except Exception as e:
            print(f"❌ [LYZR CONNECTION ERROR]: {str(e)}")
            yield {"type": "error", "message": str(e)}

async def call_lyzr_agent(
    agent_id: str,
    message: str,
    user_id: str = "priceos-user",
    session_id: Optional[str] = None,
    system_prompt_variables: Optional[Dict[str, Any]] = None,
    filter_variables: Optional[Dict[str, Any]] = None,
    features: Optional[List[Dict[str, Any]]] = None,
    timeout_ms: int = 120_000,
    max_retries: int = 2
) -> LyzrCallResult:
    # Keep the existing non-streaming version for backward compatibility
    # but simplify it to just call and wait
    chat_url, api_key = get_lyzr_config()
    # ... (rest of existing call_lyzr_agent logic if needed, but we'll use stream for chat)
    # Actually, I'll keep it as is but fix the redundant lines
    import time
    if not chat_url: return LyzrCallResult("", None, False, error="LYZR_API_URL not configured")
    if not api_key: return LyzrCallResult("", None, False, error="LYZR_API_KEY not configured")
    if not session_id: session_id = f"session-{int(time.time() * 1000)}"
    payload = {"user_id": user_id, "agent_id": agent_id, "session_id": session_id, "message": message}
    if system_prompt_variables: payload["system_prompt_variables"] = system_prompt_variables
    if filter_variables: payload["filter_variables"] = filter_variables
    if features: payload["features"] = features
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    async with httpx.AsyncClient(timeout=timeout_ms / 1000.0) as client:
        res = await client.post(chat_url, json=payload, headers=headers)
        if res.status_code != 200: return LyzrCallResult("", None, False, error=res.text)
        data = res.json()
        msg = extract_lyzr_message(data)
        return LyzrCallResult(msg, data, True, parsed_json=extract_json(msg))

    return LyzrCallResult("", None, False, error=last_error or "Unknown error")

def get_lyzr_headers() -> Optional[Dict[str, str]]:
    _, api_key = get_lyzr_config()
    if not api_key: return None
    return {"Content-Type": "application/json", "x-api-key": api_key}
