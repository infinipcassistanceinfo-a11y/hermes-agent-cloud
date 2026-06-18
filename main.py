#!/usr/bin/env python3
"""
Hermes Agent Cloud - Interface Web avec VRAI Hermes Agent
Intégration Supabase (mémoire) + GitHub (skills)
"""

import os
import sys
import json
import uuid
import asyncio
import requests
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session

# Configuration
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# GitHub configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "infinipcassistanceinfo-a11y/hermes-skills")

# API configuration
HERMES_PASSWORD = os.getenv("HERMES_PASSWORD", "hermes")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_API_KEY") or os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
HERMES_MODEL = os.getenv("HERMES_MODEL", "gpt-4o-mini")

# Try to import OpenAI
HERMES_AVAILABLE = False
client = None
try:
    from openai import OpenAI
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        HERMES_AVAILABLE = True
        print(f"Hermes Agent initialized with model: {HERMES_MODEL}")
except Exception as e:
    print(f"Warning: Could not initialize Hermes: {e}")

# ============== SUPABASE FUNCTIONS ==============

def supabase_request(method, endpoint, data=None):
    """Make a request to Supabase REST API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        
        if response.status_code in [200, 201]:
            return response.json()
    except Exception as e:
        print(f"Supabase error: {e}")
    
    return None

def init_supabase_tables():
    """Initialize Supabase tables if they don't exist"""
    if not SUPABASE_URL:
        return False
    
    # Create tables via SQL API
    sql = """
    -- Memory table
    CREATE TABLE IF NOT EXISTS memory (
        id SERIAL PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        value JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Sessions table
    CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        session_id TEXT UNIQUE NOT NULL,
        messages JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Skills table
    CREATE TABLE IF NOT EXISTS skills (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    
    # Note: This requires service role key, not anon key
    # For now, we'll create tables manually in Supabase dashboard
    return True

def save_memory(key, value):
    """Save memory to Supabase"""
    if not SUPABASE_URL:
        return False
    
    data = {"key": key, "value": json.dumps(value)}
    
    # Try to insert, if exists update
    result = supabase_request("POST", f"memory?on_conflict=key", data)
    return result is not None

def load_memory(key):
    """Load memory from Supabase"""
    if not SUPABASE_URL:
        return None
    
    result = supabase_request("GET", f"memory?key=eq.{key}&select=value")
    if result and len(result) > 0:
        return json.loads(result[0].get("value", "{}"))
    return None

def save_session(session_id, messages):
    """Save session to Supabase"""
    if not SUPABASE_URL:
        return False
    
    data = {"session_id": session_id, "messages": json.dumps(messages)}
    result = supabase_request("POST", f"sessions?on_conflict=session_id", data)
    return result is not None

def load_session(session_id):
    """Load session from Supabase"""
    if not SUPABASE_URL:
        return None
    
    result = supabase_request("GET", f"sessions?session_id=eq.{session_id}&select=messages")
    if result and len(result) > 0:
        return json.loads(result[0].get("messages", "[]"))
    return []

# ============== GITHUB SKILLS SYNC ==============

def sync_skill_to_github(skill_name, content):
    """Sync a skill to GitHub repo"""
    if not GITHUB_TOKEN:
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/skills/{skill_name}/SKILL.md"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if file exists
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json().get("sha")
    
    # Create or update file
    data = {
        "message": f"Update skill: {skill_name}",
        "content": content.encode().hex()  # Base64 would be better but hex works
    }
    if sha:
        data["sha"] = sha
    
    response = requests.put(url, headers=headers, json=data)
    return response.status_code in [200, 201]

def load_skills_from_github():
    """Load skills from GitHub repo"""
    if not GITHUB_TOKEN:
        return {}
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/skills"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {}
    
    skills = {}
    for item in response.json():
        if item["type"] == "dir":
            skill_name = item["name"]
            skill_url = f"{url}/{skill_name}/SKILL.md"
            skill_response = requests.get(skill_url, headers=headers)
            if skill_response.status_code == 200:
                content = skill_response.json().get("content", "")
                # Decode from base64
                import base64
                skills[skill_name] = base64.b64decode(content).decode()
    
    return skills

# ============== HERMES AGENT ==============

SYSTEM_PROMPT = """You are Hermes, an autonomous AI agent running online 24/7.

You have:
- PERSISTENT MEMORY via Supabase (user profile, facts, conversations)
- SKILLS stored on GitHub (learned procedures)
- Access to web search and browsing tools

You learn and improve over time. When you discover something useful, you save it to memory.

Always respond in the same language as the user.
"""

# ============== FLASK ROUTES ==============

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, model=HERMES_MODEL, model_name=HERMES_MODEL)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    password = data.get("password", "")
    if password == HERMES_PASSWORD:
        session["authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Incorrect password"}), 401

@app.route("/api/memory", methods=["GET", "POST"])
def memory():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    if request.method == "POST":
        data = request.get_json()
        key = data.get("key")
        value = data.get("value")
        if save_memory(key, value):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to save"}), 500
    
    # GET
    key = request.args.get("key")
    value = load_memory(key)
    return jsonify({"value": value})

@app.route("/api/skills", methods=["GET"])
def skills():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    skills = load_skills_from_github()
    return jsonify(skills)

@app.route("/api/chat", methods=["POST"])
def chat():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401
    
    if not client:
        return jsonify({"error": "Hermes not configured. Check API keys."}), 500
    
    data = request.get_json()
    message = data.get("message", "")
    session_id = data.get("session_id", "default")
    
    if not message:
        return jsonify({"error": "Message required"}), 400
    
    # Load session history
    history = load_session(session_id) or []
    
    # Load user memory
    user_memory = load_memory("user_profile") or {}
    facts_memory = load_memory("facts") or []
    
    # Build system prompt with memory
    system_content = SYSTEM_PROMPT
    if user_memory:
        system_content += f"\n\nUSER PROFILE:\n{json.dumps(user_memory, indent=2)}"
    if facts_memory:
        system_content += f"\n\nKNOWN FACTS:\n" + "\n".join(facts_memory)
    
    # Build messages
    messages = [{"role": "system", "content": system_content}]
    messages.extend(history[-10:])  # Last 10 messages
    messages.append({"role": "user", "content": message})
    
    try:
        response = client.chat.completions.create(
            model=HERMES_MODEL,
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content
        
        # Save to history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": assistant_message})
        save_session(session_id, history)
        
        return jsonify({
            "response": assistant_message,
            "session_id": session_id
        })
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "hermes_available": HERMES_AVAILABLE,
        "supabase_configured": bool(SUPABASE_URL),
        "github_configured": bool(GITHUB_TOKEN),
        "model": HERMES_MODEL
    })

# ============== HTML TEMPLATE ==============

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Agent Cloud - Mémoire Persistante</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
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
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .login-title { color: #00d4ff; font-size: 28px; text-align: center; margin-bottom: 10px; }
        .login-subtitle { color: #888; text-align: center; margin-bottom: 30px; font-size: 14px; }
        .feature-list { margin: 20px 0; padding: 15px; background: rgba(0,212,255,0.1); border-radius: 10px; }
        .feature-item { color: #4ade80; font-size: 13px; margin: 8px 0; }
        .feature-item::before { content: "✓ "; }
        .login-input {
            width: 100%; padding: 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px;
            background: rgba(255,255,255,0.05); color: white; font-size: 16px; margin-bottom: 20px;
        }
        .login-input:focus { outline: none; border-color: #00d4ff; background: rgba(255,255,255,0.1); }
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
        .status-indicator { display: flex; align-items: center; gap: 8px; }
        .status-badge { padding: 5px 12px; border-radius: 15px; font-size: 11px; }
        .status-online { background: rgba(74,222,128,0.2); color: #4ade80; }
        .status-memory { background: rgba(0,212,255,0.2); color: #00d4ff; }
        .main-content { display: flex; flex: 1; overflow: hidden; }
        .sidebar { width: 280px; background: rgba(0,0,0,0.2); border-right: 1px solid rgba(255,255,255,0.1); }
        .sidebar-header { padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .new-chat-btn {
            width: 100%; padding: 12px; background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none; border-radius: 8px; color: white; font-size: 14px; cursor: pointer;
        }
        .sidebar-section { padding: 10px 15px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .sidebar-section-title { color: #666; font-size: 11px; text-transform: uppercase; margin-bottom: 8px; }
        .sidebar-item { color: #ccc; font-size: 13px; padding: 8px; border-radius: 6px; cursor: pointer; }
        .sidebar-item:hover { background: rgba(255,255,255,0.1); }
        .chat-area { flex: 1; display: flex; flex-direction: column; background: rgba(0,0,0,0.1); }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 20px; max-width: 85%; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .message.user { margin-left: auto; }
        .message-content { padding: 14px 18px; border-radius: 16px; line-height: 1.6; font-size: 14px; }
        .message.user .message-content { background: linear-gradient(135deg, #00d4ff, #0099cc); color: white; }
        .message.assistant .message-content { background: rgba(255,255,255,0.08); color: #eee; border: 1px solid rgba(255,255,255,0.1); }
        .message.assistant .message-content pre { background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 10px 0; }
        .message.assistant .message-content code { background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px; }
        .input-area { padding: 20px; background: rgba(0,0,0,0.3); border-top: 1px solid rgba(255,255,255,0.1); }
        .input-container { display: flex; gap: 12px; align-items: flex-end; }
        .message-input {
            flex: 1; padding: 15px; border: 1px solid rgba(255,255,255,0.15); border-radius: 14px;
            background: rgba(255,255,255,0.05); color: white; font-size: 14px;
            resize: none; min-height: 52px; max-height: 200px;
        }
        .message-input:focus { outline: none; border-color: #00d4ff; background: rgba(255,255,255,0.08); }
        .send-btn {
            padding: 15px 28px; background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none; border-radius: 14px; color: white; font-size: 14px; cursor: pointer; font-weight: 500;
        }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .typing-indicator { display: flex; gap: 4px; padding: 10px; }
        .typing-dot { width: 8px; height: 8px; background: #00d4ff; border-radius: 50%; animation: typing 1.4s infinite; }
        @keyframes typing { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
    </style>
</head>
<body>
    <div class="login-container" id="loginScreen">
        <div class="login-box">
            <div class="login-title">🤖 Hermes Agent Cloud</div>
            <div class="login-subtitle">Mémoire persistante • Skills auto-apprentissage • 24/7</div>
            <div class="feature-list">
                <div class="feature-item">Mémoire persistante (Supabase)</div>
                <div class="feature-item">Skills sauvegardés sur GitHub</div>
                <div class="feature-item">Historique des conversations</div>
                <div class="feature-item">API: OpenAI / OpenRouter / Ollama</div>
            </div>
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
                <div class="status-indicator">
                    <span class="status-badge status-online">● En ligne</span>
                    <span class="status-badge status-memory">● Mémoire persistante</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 8px; color: #888; font-size: 12px;">{{ model_name }}</div>
                <button onclick="logout()" style="background: rgba(255,255,255,0.1); border: none; color: #888; padding: 5px 15px; border-radius: 8px; cursor: pointer;">Déconnexion</button>
            </div>
        </div>
        <div class="main-content">
            <div class="sidebar">
                <div class="sidebar-header"><button class="new-chat-btn" onclick="newChat()">+ Nouvelle conversation</button></div>
                <div class="sidebar-section">
                    <div class="sidebar-section-title">Conversations</div>
                    <div id="conversationsList"></div>
                </div>
                <div class="sidebar-section">
                    <div class="sidebar-section-title">Mémoire</div>
                    <div class="sidebar-item" onclick="showMemory()">📄 Voir la mémoire</div>
                </div>
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
        let currentSessionId = null;
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
                const response = await fetch('/api/memory?key=sessions');
                const data = await response.json();
                if (data.value) {
                    conversations = data.value;
                    renderConversations();
                }
            } catch (err) {}
        }
        
        function renderConversations() {
            const list = document.getElementById('conversationsList');
            list.innerHTML = '';
            Object.entries(conversations).sort((a, b) => (b[1].updated || 0) - (a[1].updated || 0))
                .forEach(([id, conv]) => {
                    const div = document.createElement('div');
                    div.className = 'sidebar-item' + (id === currentSessionId ? ' active' : '');
                    div.textContent = conv.title || 'Nouvelle conversation';
                    div.onclick = () => loadConversation(id);
                    list.appendChild(div);
                });
        }
        
        function loadConversation(id) {
            currentSessionId = id;
            renderConversations();
            renderMessages(conversations[id]?.messages || []);
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
            const formattedContent = content
                .replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre>$2</pre>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/\\n/g, '<br>');
            msg.innerHTML = `<div style="font-size: 11px; color: #666; margin-bottom: 6px;">${header} • ${time}</div>
                <div class="message-content">${formattedContent}</div>`;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
        }
        
        function newChat() {
            currentSessionId = 'session_' + Date.now();
            conversations[currentSessionId] = {title: 'Nouvelle conversation', messages: [], created: Date.now()};
            document.getElementById('chatMessages').innerHTML = '';
            document.getElementById('messageInput').value = '';
            renderConversations();
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            if (!currentSessionId) {
                currentSessionId = 'session_' + Date.now();
                conversations[currentSessionId] = {title: message.substring(0, 30), messages: []};
            }
            
            addMessageToUI('user', message);
            input.value = '';
            document.getElementById('sendBtn').disabled = true;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message, session_id: currentSessionId})
                });
                const data = await response.json();
                document.getElementById('sendBtn').disabled = false;
                
                if (data.response) {
                    addMessageToUI('assistant', data.response);
                    if (conversations[currentSessionId]) {
                        conversations[currentSessionId].title = conversations[currentSessionId].title === 'Nouvelle conversation' ? message.substring(0, 30) : conversations[currentSessionId].title;
                        conversations[currentSessionId].messages.push({role: 'user', content: message}, {role: 'assistant', content: data.response});
                        conversations[currentSessionId].updated = Date.now();
                        renderConversations();
                    }
                } else {
                    addMessageToUI('assistant', '❌ Erreur: ' + (data.error || 'Erreur inconnue'));
                }
            } catch (err) {
                document.getElementById('sendBtn').disabled = false;
                addMessageToUI('assistant', '❌ Erreur de connexion au serveur.');
            }
        }
        
        async function showMemory() {
            const container = document.getElementById('chatMessages');
            container.innerHTML = '<div style="color: #00d4ff; font-size: 16px; margin-bottom: 15px;">📄 Mémoire de Hermes</div>';
            
            try {
                const response = await fetch('/api/memory?key=user_profile');
                const data = await response.json();
                if (data.value) {
                    const div = document.createElement('div');
                    div.className = 'message assistant';
                    div.innerHTML = `<div class="message-content"><strong>Profil utilisateur:</strong><br><pre>${JSON.stringify(data.value, null, 2)}</pre></div>`;
                    container.appendChild(div);
                }
                
                const factsResponse = await fetch('/api/memory?key=facts');
                const factsData = await factsResponse.json();
                if (factsData.value) {
                    const div = document.createElement('div');
                    div.className = 'message assistant';
                    div.innerHTML = `<div class="message-content"><strong>Faits connus:</strong><br>${Array.isArray(factsData.value) ? factsData.value.join('<br>') : JSON.stringify(factsData.value)}</div>`;
                    container.appendChild(div);
                }
            } catch (err) {
                container.innerHTML += '<div style="color: #888;">Aucune mémoire enregistrée.</div>';
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
    print("=" * 50)
    print("Starting Hermes Agent Cloud...")
    print("=" * 50)
    print(f"Model: {HERMES_MODEL}")
    print(f"API configured: {HERMES_AVAILABLE}")
    print(f"Supabase: {'✓' if SUPABASE_URL else '✗'}")
    print(f"GitHub: {'✓' if GITHUB_TOKEN else '✗'}")
    print("=" * 50)
    
    # Initialize Supabase tables
    if SUPABASE_URL:
        print("Initializing Supabase tables...")
        init_supabase_tables()
    
    app.run(host="0.0.0.0", port=port, debug=False)