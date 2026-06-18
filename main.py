#!/usr/bin/env python3
"""
Hermes Agent Cloud - Interface Web avec VRAI Hermes Agent
"""

import os
import sys
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session

# Configuration
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

HERMES_PASSWORD = os.getenv("HERMES_PASSWORD", "hermes")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_API_KEY") or os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
HERMES_MODEL = os.getenv("HERMES_MODEL", "gpt-4o-mini")

# Memory
MEMORY_FILE = DATA_DIR / "memory.json"

def load_memory():
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except:
        pass
    return {"conversations": {}, "user_profile": {}, "facts": []}

def save_memory(memory):
    try:
        MEMORY_FILE.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving memory: {e}")

MEMORY = load_memory()

# Try to import Hermes Agent
HERMES_AVAILABLE = False
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_API_KEY else None
    HERMES_AVAILABLE = client is not None
    print(f"Hermes Agent initialized with model: {HERMES_MODEL}")
except Exception as e:
    print(f"Warning: Could not initialize Hermes: {e}")
    client = None

# System prompt for Hermes
SYSTEM_PROMPT = """You are Hermes, an autonomous AI agent running online 24/7.
You are helpful, analytical, and direct.
You have access to tools and can help with various tasks.
Always respond in the same language as the user.
You have persistent memory across sessions.
"""

# Routes
@app.route("/")
def index():
    if session.get("authenticated"):
        return render_template_string(HTML_TEMPLATE, model=HERMES_MODEL, model_name=HERMES_MODEL)
    return render_template_string(HTML_TEMPLATE, model=HERMES_MODEL, model_name=HERMES_MODEL)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    password = data.get("password", "")
    if password == HERMES_PASSWORD:
        session["authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Incorrect password"}), 401

@app.route("/api/conversations")
def get_conversations():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    return jsonify(MEMORY.get("conversations", {}))

@app.route("/api/conversation/<conv_id>")
def get_conversation(conv_id):
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    convs = MEMORY.get("conversations", {})
    if conv_id in convs:
        return jsonify(convs[conv_id])
    return jsonify({"error": "Not found"}), 404

@app.route("/api/chat", methods=["POST"])
def chat():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    if not client:
        return jsonify({"error": "Hermes not configured. Set OPENAI_API_KEY or OLLAMA_API_KEY."}), 500
    
    data = request.get_json()
    message = data.get("message", "")
    conv_id = data.get("conversation_id")
    
    if not message:
        return jsonify({"error": "Message required"}), 400
    
    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Load conversation history
    if conv_id and conv_id in MEMORY.get("conversations", {}):
        conv = MEMORY["conversations"][conv_id]
        for msg in conv.get("messages", [])[-10:]:  # Last 10 messages
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": message})
    
    try:
        # Call OpenAI-compatible API
        response = client.chat.completions.create(
            model=HERMES_MODEL,
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content
        
        # Save conversation
        if conv_id:
            if "conversations" not in MEMORY:
                MEMORY["conversations"] = {}
            if conv_id not in MEMORY["conversations"]:
                MEMORY["conversations"][conv_id] = {
                    "title": message[:50],
                    "created": datetime.now().isoformat(),
                    "messages": []
                }
            
            MEMORY["conversations"][conv_id]["messages"].append(
                {"role": "user", "content": message}
            )
            MEMORY["conversations"][conv_id]["messages"].append(
                {"role": "assistant", "content": assistant_message}
            )
            MEMORY["conversations"][conv_id]["updated"] = datetime.now().isoformat()
            
            # Keep only last 50 messages
            if len(MEMORY["conversations"][conv_id]["messages"]) > 50:
                MEMORY["conversations"][conv_id]["messages"] = MEMORY["conversations"][conv_id]["messages"][-50:]
            
            save_memory(MEMORY)
        
        return jsonify({
            "response": assistant_message,
            "conversation_id": conv_id
        })
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "hermes_available": HERMES_AVAILABLE,
        "model": HERMES_MODEL
    })

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Agent - Interface Web</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .login-box {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .login-title { color: #00d4ff; font-size: 28px; text-align: center; margin-bottom: 10px; }
        .login-subtitle { color: #888; text-align: center; margin-bottom: 30px; font-size: 14px; }
        .login-input {
            width: 100%; padding: 15px; border: none; border-radius: 10px;
            background: rgba(255,255,255,0.1); color: white; font-size: 16px; margin-bottom: 20px;
        }
        .login-input:focus { outline: none; background: rgba(255,255,255,0.2); }
        .login-button {
            width: 100%; padding: 15px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #00d4ff, #0099cc); color: white;
            font-size: 16px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
        }
        .login-button:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,212,255,0.4); }
        .error-message { color: #ff4444; text-align: center; margin-top: 10px; font-size: 14px; }
        .desktop { display: none; flex-direction: column; height: 100vh; }
        .desktop.active { display: flex; }
        .top-bar {
            background: rgba(0,0,0,0.3); padding: 10px 20px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .hermes-logo { color: #00d4ff; font-size: 20px; font-weight: bold; }
        .status-indicator { display: flex; align-items: center; gap: 5px; color: #4ade80; font-size: 12px; }
        .status-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .main-content { display: flex; flex: 1; overflow: hidden; }
        .sidebar { width: 260px; background: rgba(0,0,0,0.2); border-right: 1px solid rgba(255,255,255,0.1); }
        .sidebar-header { padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .new-chat-btn {
            width: 100%; padding: 12px; background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none; border-radius: 8px; color: white; font-size: 14px; cursor: pointer;
        }
        .conversations-list { flex: 1; overflow-y: auto; padding: 10px; }
        .conv-item {
            padding: 10px; border-radius: 8px; cursor: pointer; margin-bottom: 5px;
            color: #ccc; font-size: 13px; transition: background 0.2s;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .conv-item:hover { background: rgba(255,255,255,0.1); }
        .conv-item.active { background: rgba(0,212,255,0.2); color: #00d4ff; }
        .chat-area { flex: 1; display: flex; flex-direction: column; background: rgba(0,0,0,0.1); }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 20px; max-width: 80%; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .message.user { margin-left: auto; }
        .message-content { padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 14px; }
        .message.user .message-content { background: linear-gradient(135deg, #00d4ff, #0099cc); color: white; }
        .message.assistant .message-content { background: rgba(255,255,255,0.1); color: #eee; }
        .message.assistant .message-content pre { background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0; }
        .input-area { padding: 20px; background: rgba(0,0,0,0.3); border-top: 1px solid rgba(255,255,255,0.1); }
        .input-container { display: flex; gap: 10px; align-items: flex-end; }
        .message-input {
            flex: 1; padding: 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 12px;
            background: rgba(255,255,255,0.1); color: white; font-size: 14px;
            resize: none; min-height: 50px; max-height: 200px;
        }
        .message-input:focus { outline: none; border-color: #00d4ff; background: rgba(255,255,255,0.15); }
        .send-btn {
            padding: 15px 25px; background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none; border-radius: 12px; color: white; font-size: 14px; cursor: pointer;
        }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
    </style>
</head>
<body>
    <div class="login-container" id="loginScreen">
        <div class="login-box">
            <div class="login-title">🤖 Hermes Agent</div>
            <div class="login-subtitle">Interface Web - Accès 24/7</div>
            <form id="loginForm">
                <input type="password" class="login-input" id="passwordInput" placeholder="Mot de passe" required>
                <button type="submit" class="login-button">Se connecter</button>
            </form>
            <div class="error-message" id="errorMsg"></div>
        </div>
    </div>
    <div class="desktop" id="desktop">
        <div class="top-bar">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div class="hermes-logo">🤖 Hermes Agent</div>
                <div class="status-indicator"><div class="status-dot"></div><span>En ligne</span></div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 5px; color: #888; font-size: 12px;">{{ model_name }}</div>
                <button onclick="logout()" style="background: rgba(255,255,255,0.1); border: none; color: #888; padding: 5px 15px; border-radius: 5px; cursor: pointer;">Déconnexion</button>
            </div>
        </div>
        <div class="main-content">
            <div class="sidebar">
                <div class="sidebar-header"><button class="new-chat-btn" onclick="newChat()">+ Nouvelle conversation</button></div>
                <div class="conversations-list" id="conversationsList"></div>
            </div>
            <div class="chat-area">
                <div class="chat-messages" id="chatMessages"></div>
                <div class="input-area">
                    <div class="input-container">
                        <textarea class="message-input" id="messageInput" placeholder="Envoyer un message à Hermes..." rows="1"></textarea>
                        <button class="send-btn" id="sendBtn" onclick="sendMessage()">Envoyer</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        let currentConvId = null;
        let conversations = {};
        
        document.addEventListener('DOMContentLoaded', () => {
            if (sessionStorage.getItem('hermes_auth') === 'true') {
                showDesktop();
                loadConversations();
            }
        });
        
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const password = document.getElementById('passwordInput').value;
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password})
                });
                const data = await response.json();
                if (data.success) {
                    sessionStorage.setItem('hermes_auth', 'true');
                    showDesktop();
                    loadConversations();
                } else {
                    document.getElementById('errorMsg').textContent = 'Mot de passe incorrect';
                }
            } catch (err) {
                document.getElementById('errorMsg').textContent = 'Erreur de connexion';
            }
        });
        
        function showDesktop() {
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('desktop').classList.add('active');
        }
        
        function logout() { sessionStorage.removeItem('hermes_auth'); location.reload(); }
        
        async function loadConversations() {
            try {
                const response = await fetch('/api/conversations');
                conversations = await response.json();
                renderConversations();
            } catch (err) {}
        }
        
        function renderConversations() {
            const list = document.getElementById('conversationsList');
            list.innerHTML = '';
            Object.entries(conversations).sort((a, b) => (b[1].updated || 0) - (a[1].updated || 0))
                .forEach(([id, conv]) => {
                    const div = document.createElement('div');
                    div.className = 'conv-item' + (id === currentConvId ? ' active' : '');
                    div.textContent = conv.title || 'Nouvelle conversation';
                    div.onclick = () => loadConversation(id);
                    list.appendChild(div);
                });
        }
        
        async function loadConversation(id) {
            currentConvId = id;
            renderConversations();
            try {
                const response = await fetch(`/api/conversation/${id}`);
                const data = await response.json();
                renderMessages(data.messages || []);
            } catch (err) {}
        }
        
        function renderMessages(messages) {
            const container = document.getElementById('chatMessages');
            container.innerHTML = '';
            messages.forEach(msg => addMessageToUI(msg.role, msg.content));
            container.scrollTop = container.scrollHeight;
        }
        
        function addMessageToUI(role, content) {
            const container = document.getElementById('chatMessages');
            const msg = document.createElement('div');
            msg.className = `message ${role}`;
            const time = new Date().toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
            const header = role === 'user' ? '👤 Vous' : '🤖 Hermes';
            const formattedContent = content.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre>$2</pre>')
                .replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\\n/g, '<br>');
            msg.innerHTML = `<div style="font-size: 11px; color: #666; margin-bottom: 5px;">${header} • ${time}</div>
                <div class="message-content">${formattedContent}</div>`;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
        }
        
        function newChat() {
            currentConvId = null;
            document.getElementById('chatMessages').innerHTML = '';
            document.getElementById('messageInput').value = '';
            renderConversations();
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            if (!currentConvId) {
                currentConvId = 'conv_' + Date.now();
                conversations[currentConvId] = {title: message.substring(0, 30), messages: []};
            }
            
            addMessageToUI('user', message);
            input.value = '';
            document.getElementById('sendBtn').disabled = true;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message, conversation_id: currentConvId})
                });
                const data = await response.json();
                document.getElementById('sendBtn').disabled = false;
                
                if (data.response) {
                    addMessageToUI('assistant', data.response);
                    if (conversations[currentConvId]) {
                        conversations[currentConvId].updated = Date.now();
                        conversations[currentConvId].messages.push({role: 'user', content: message}, {role: 'assistant', content: data.response});
                        renderConversations();
                    }
                }
            } catch (err) {
                document.getElementById('sendBtn').disabled = false;
                addMessageToUI('assistant', '❌ Erreur de connexion. Veuillez réessayer.');
            }
        }
        
        document.getElementById('messageInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"Starting Hermes Agent on port {port}...")
    print(f"Model: {HERMES_MODEL}")
    print(f"API configured: {HERMES_AVAILABLE}")
    app.run(host="0.0.0.0", port=port, debug=False)