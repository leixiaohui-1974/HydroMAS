/**
 * Dashboard page — system overview.
 * 仪表盘页面 — 系统总览。
 */

import { apiGet, apiPost, createLineChart, fmt } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-4" id="stats-row"></div>
        <div class="card-grid card-grid-2" style="margin-top:1rem">
            <div class="card">
                <div class="card-header"><h3>水位仿真预览 / Water Level Preview</h3></div>
                <div class="chart-container"><canvas id="dash-sim-chart"></canvas></div>
            </div>
            <div class="card">
                <div class="card-header"><h3>ODD 安全状态 / ODD Safety</h3></div>
                <div id="dash-odd-status" style="padding:1rem">
                    <div class="loader"><div class="spinner"></div></div>
                </div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>系统架构概览 / Architecture Overview</h3></div>
            <div class="card-grid card-grid-4" id="layer-status"></div>
        </div>
    `;

    // Load system status
    loadStats();
    loadSimPreview();
    loadODDStatus();
}

async function loadStats() {
    const row = document.getElementById('stats-row');
    try {
        const status = await apiGet('/api/system/status');
        row.innerHTML = `
            <div class="stat-card">
                <div class="stat-label">系统状态</div>
                <div class="stat-value success">${status.status === 'online' ? '在线' : '离线'}</div>
                <div class="stat-change">5 layers operational</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">ODD 维度</div>
                <div class="stat-value primary">${status.odd_dimensions}</div>
                <div class="stat-change">dimensions monitored</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">版本</div>
                <div class="stat-value info">v${status.version}</div>
                <div class="stat-change">HydroOS-Agent</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">架构层数</div>
                <div class="stat-value primary">5</div>
                <div class="stat-change">L0 Core → L4 Agents</div>
            </div>
        `;
        // Layer status
        const layerEl = document.getElementById('layer-status');
        if (layerEl) {
            layerEl.innerHTML = Object.entries(status.layers).map(([k, v]) =>
                `<div class="stat-card"><div class="stat-label">${k}</div><div class="stat-value success" style="font-size:0.95rem">${v}</div></div>`
            ).join('');
        }
    } catch {
        row.innerHTML = '<div class="alert alert-warning">无法加载系统状态</div>';
    }
}

async function loadSimPreview() {
    try {
        const sim = await apiPost('/api/simulation/run', {
            duration: 200, dt: 1.0, initial_h: 0.5,
            q_in_profile: [[0, 0.01], [60, 0.03], [120, 0.01]],
        });
        const canvas = document.getElementById('dash-sim-chart');
        if (canvas) {
            const step = Math.max(1, Math.floor(sim.time.length / 100));
            const labels = sim.time.filter((_, i) => i % step === 0).map(t => t.toFixed(0));
            const wl = sim.water_level.filter((_, i) => i % step === 0);
            createLineChart(canvas, labels, [{
                label: '水位 Water Level (m)',
                data: wl,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37,99,235,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
            }]);
        }
    } catch { /* silent */ }
}

async function loadODDStatus() {
    const el = document.getElementById('dash-odd-status');
    try {
        const result = await apiPost('/api/odd/check', {
            state: { water_level: 1.0, inflow_rate: 0.02 },
        });
        const zoneClass = { normal: 'zone-normal', extended: 'zone-extended', mrc: 'zone-mrc' };
        const zoneLabel = { normal: '正常域', extended: '扩展域', mrc: '最小风险' };
        el.innerHTML = `
            <div style="text-align:center;padding:1rem 0">
                <span class="zone-badge ${zoneClass[result.zone] || 'zone-normal'}" style="font-size:1rem;padding:0.4rem 1.2rem">
                    ${zoneLabel[result.zone] || result.zone}
                </span>
                <p style="color:var(--text-secondary);margin-top:0.75rem;font-size:0.85rem">
                    违规维度: ${result.violations ? result.violations.length : 0} / ${result.checked_dimensions || 6}
                </p>
            </div>
            <table class="data-table" style="margin-top:0.5rem">
                <thead><tr><th>维度</th><th>状态</th></tr></thead>
                <tbody>
                    ${(result.dimension_results || []).map(d =>
                        `<tr><td>${d.dimension}</td><td><span class="zone-badge ${zoneClass[d.zone] || ''}">${d.zone}</span></td></tr>`
                    ).join('')}
                </tbody>
            </table>
        `;
    } catch {
        el.innerHTML = '<div class="alert alert-info">ODD 状态加载失败</div>';
    }
}
