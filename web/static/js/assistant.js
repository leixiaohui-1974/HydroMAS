/**
 * AI Assistant chat panel logic.
 * 智能助手聊天面板逻辑。
 */

import { apiPost, apiGet } from './api.js';

let currentRole = 'admin';

export function initAssistant(role) {
    currentRole = role;
    loadQuickActions(role);
    bindChatEvents();
}

async function loadQuickActions(role) {
    const container = document.getElementById('quick-actions');
    try {
        const data = await apiGet(`/api/assistant/quick-actions/${role}`);
        container.innerHTML = data.actions.map(a =>
            `<button class="quick-action-btn" data-msg="${a.message}">${a.label}</button>`
        ).join('');
        container.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => sendMessage(btn.dataset.msg));
        });
    } catch {
        container.innerHTML = '';
    }
}

function bindChatEvents() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');

    sendBtn.addEventListener('click', () => {
        const msg = input.value.trim();
        if (msg) { sendMessage(msg); input.value = ''; }
    });

    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const msg = input.value.trim();
            if (msg) { sendMessage(msg); input.value = ''; }
        }
    });
}

async function sendMessage(text) {
    const messages = document.getElementById('chat-messages');

    // Add user message
    const userEl = document.createElement('div');
    userEl.className = 'chat-msg user';
    userEl.innerHTML = `<p>${escapeHtml(text)}</p>`;
    messages.appendChild(userEl);
    messages.scrollTop = messages.scrollHeight;

    // Loading indicator
    const loadingEl = document.createElement('div');
    loadingEl.className = 'chat-msg assistant';
    loadingEl.innerHTML = '<p><em>分析中 / Analyzing...</em></p>';
    messages.appendChild(loadingEl);
    messages.scrollTop = messages.scrollHeight;

    try {
        const resp = await apiPost('/api/assistant/chat', {
            message: text,
            role: currentRole,
        });

        loadingEl.remove();

        const assistantEl = document.createElement('div');
        assistantEl.className = 'chat-msg assistant';

        const intent = resp.intent || {};
        const result = resp.result || {};

        let html = '';
        if (intent.route_type && intent.target) {
            html += `<div class="intent-tag">${intent.route_type}: ${intent.display_name || intent.target}</div>`;
        }

        if (result.status === 'completed' && result.data) {
            html += `<p>已完成分析，以下是结果：</p>`;
            html += `<div class="result-block">${escapeHtml(JSON.stringify(result.data, null, 2)).substring(0, 2000)}</div>`;
            if (result.execution_time) {
                html += `<p style="color:var(--text-muted);font-size:0.75rem;margin-top:0.3rem">执行时间: ${result.execution_time.toFixed(2)}s</p>`;
            }
        } else if (result.status === 'delegated') {
            html += `<p>${result.message || '正在处理复杂请求...'}</p>`;
        } else if (result.error) {
            html += `<p style="color:var(--danger)">错误: ${escapeHtml(result.error)}</p>`;
        } else {
            html += `<p>${escapeHtml(JSON.stringify(result, null, 2).substring(0, 1000))}</p>`;
        }

        assistantEl.innerHTML = html;
        messages.appendChild(assistantEl);
    } catch (err) {
        loadingEl.remove();
        const errEl = document.createElement('div');
        errEl.className = 'chat-msg assistant';
        errEl.innerHTML = `<p style="color:var(--danger)">请求失败: ${escapeHtml(err.message)}</p>`;
        messages.appendChild(errEl);
    }

    messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
