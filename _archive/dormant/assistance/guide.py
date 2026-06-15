import os
import json
import time
import requests
import traceback

from core.diagnostics.ide_bridge import IDEBridge

class EliteLocalGuide:
    """
    A lightweight, read-only daemon that connects to a local LLM (like Ollama) 
    to provide system-aware guidance without burning cloud tokens.
    """
    def __init__(self, brain_dir: str, model: str = "llama3"):
        self.brain_dir = brain_dir
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.ide_bridge = IDEBridge(brain_dir)
        
        self.system_prompt = (
            "You are the Elite Helpdesk Guide, a highly intelligent local AI daemon. "
            "Your job is to assist the user in navigating the Elite Reasoning System architecture. "
            "You are READ-ONLY. You cannot execute code. You answer questions concisely. "
            "Whenever asked about the system state, refer to the SYSTEM METRICS provided in your context."
        )
        self.chat_history = []

    def ping_ollama(self) -> bool:
        """Check if the local Ollama instance is running."""
        try:
            response = requests.get("http://localhost:11434/", timeout=2)
            return response.status_code == 200
        except:
            return False

    def get_system_metrics(self) -> str:
        """Fetch real-time liveness data from the IDE Bridge."""
        try:
            status = self.ide_bridge.get_system_status()
            return json.dumps(status, indent=2)
        except Exception as e:
            return f"Metrics unavailable: {str(e)}"

    def chat(self, user_input: str) -> str:
        if not self.ping_ollama():
            metrics = self.get_system_metrics()
            return (
                f"⚠️ [LOCAL DAEMON MOCK] Ollama is not running on localhost:11434.\n"
                f"I am currently running in mock mode.\n\n"
                f"You asked: {user_input}\n\n"
                f"=== CURRENT SYSTEM METRICS ===\n{metrics}\n=============================="
            )

        metrics = self.get_system_metrics()
        
        # Inject context
        context_prompt = (
            f"{self.system_prompt}\n\n"
            f"=== CURRENT SYSTEM METRICS ===\n{metrics}\n==============================\n\n"
        )

        messages = [{"role": "system", "content": context_prompt}] + self.chat_history + [{"role": "user", "content": user_input}]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            response_json = response.json()
            reply = response_json.get("message", {}).get("content", "Error parsing response.")
            
            self.chat_history.append({"role": "user", "content": user_input})
            self.chat_history.append({"role": "assistant", "content": reply})
            
            return reply
        except Exception as e:
            return f"❌ [LOCAL DAEMON ERROR] Failed to query local model: {str(e)}"

    def interactive_loop(self):
        """Run an interactive console session for the guide."""
        print("🤖 ELITE LOCAL GUIDE INITIALIZING...")
        if self.ping_ollama():
            print(f"✅ Connected to local provider (Ollama) using model '{self.model}'.")
        else:
            print("⚠️  Ollama not detected. Falling back to MOCK mode.")
            
        print("Type 'exit' or 'quit' to terminate the session.\n")
        
        while True:
            try:
                user_input = input("👤 You: ").strip()
                if user_input.lower() in ['exit', 'quit', 'back']:
                    print("🤖 Guide terminating. Goodbye!")
                    break
                if not user_input:
                    continue
                
                print("🤖 Guide: ", end="", flush=True)
                reply = self.chat(user_input)
                print(reply + "\n")
                
            except KeyboardInterrupt:
                print("\n🤖 Guide terminating due to interrupt.")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {traceback.format_exc()}")
                break
