/**
 * ODD Monitoring page — safety boundary monitoring.
 * ODD 监测页面 — 安全边界监控。
 */

import { apiPost, apiGet, fmt, showLoader, showError, escapeHtml } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-2">
            <div class="card">
                <div class="card-header"><h3>状态检查 / State Check</h3></div>
                <div class="form-row">
                    <div class="form-group">
                        <label>水位 water_level (m)</label>
                        <input id="odd-wl" class="form-control" type="number" value="1.0" step="0.1">
                    </div>
                    <div class="form-group">
                        <label>入流量 inflow_rate (m³/s)</label>
                        <input id="odd-qin" class="form-control" type="number" value="0.02" step="0.005">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>出流量 outflow_rate</label>
                        <input id="odd-qout" class="form-control" type="number" value="0.01" step="0.005">
                    </div>
                    <div class="form-group">
                        <label>温度 temperature (°C)</label>
                        <input id="odd-temp" class="form-control" type="number" value="20" step="1">
                    </div>
                </div>
                <button id="odd-check" class="btn btn-primary" style="margin-top:0.5rem">检查 ODD / Check</button>
            </div>
            <div class="card">
                <div class="card-header"><h3>ODD 状态 / Status</h3></div>
                <div id="odd-result" style="padding:0.5rem">
                    <p style="color:var(--text-muted)">输入状态后检查 ODD</p>
                </div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>ODD 维度规格 / Dimension Specs</h3></div>
            <div id="odd-specs"><div class="loader"><div class="spinner"></div></div></div>
        </div>
    `;

    document.getElementById('odd-check').addEventListener('click', checkODD);
    loadSpecs();
}

async function checkODD() {
    const resultEl = document.getElementById('odd-result');
    showLoader(resultEl);

    try {
        const state = {
            water_level: +document.getElementById('odd-wl').value,
            inflow_rate: +document.getElementById('odd-qin').value,
            outflow_rate: +document.getElementById('odd-qout').value,
            temperature: +document.getElementById('odd-temp').value,
        };

        const result = await apiPost('/api/odd/check', { state });

        const zoneClass = { normal: 'zone-normal', extended: 'zone-extended', mrc: 'zone-mrc' };
        const zoneLabel = { normal: '正常域 Normal', extended: '扩展域 Extended', mrc: '最小风险 MRC' };

        let html = `
            <div style="text-align:center;margin-bottom:1rem">
                <span class="zone-badge ${zoneClass[result.zone]}" style="font-size:1.1rem;padding:0.5rem 1.5rem">
                    ${escapeHtml(zoneLabel[result.zone] || result.zone)}
                </span>
            </div>
        `;

        if (result.dimension_results) {
            html += `<table class="data-table">
                <thead><tr><th>维度</th><th>值</th><th>范围</th><th>状态</th></tr></thead>
                <tbody>`;
            for (const d of result.dimension_results) {
                html += `<tr>
                    <td>${escapeHtml(d.dimension)}</td>
                    <td>${d.value !== undefined ? fmt(d.value, 3) : '—'}</td>
                    <td>${d.min !== undefined ? fmt(d.min,2) + ' ~ ' + fmt(d.max,2) : '—'}</td>
                    <td><span class="zone-badge ${zoneClass[d.zone] || ''}">${escapeHtml(d.zone)}</span></td>
                </tr>`;
            }
            html += '</tbody></table>';
        }

        if (result.violations && result.violations.length > 0) {
            html += `<div class="alert alert-danger" style="margin-top:0.75rem">
                <strong>违规:</strong> ${escapeHtml(result.violations.map(v => v.dimension || v).join(', '))}
            </div>`;
        }

        resultEl.innerHTML = html;
    } catch (err) {
        showError(resultEl, err);
    }
}

async function loadSpecs() {
    const el = document.getElementById('odd-specs');
    try {
        const specs = await apiGet('/api/odd/specs');
        el.innerHTML = `
            <table class="data-table">
                <thead><tr><th>维度名称</th><th>下限</th><th>上限</th><th>单位</th><th>裕度</th></tr></thead>
                <tbody>
                    ${specs.dimensions.map(d => `
                        <tr>
                            <td>${escapeHtml(d.name)}</td>
                            <td>${fmt(d.min_value, 2)}</td>
                            <td>${fmt(d.max_value, 2)}</td>
                            <td>${escapeHtml(d.unit)}</td>
                            <td>${fmt(d.warning_margin || 0.1, 2)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch {
        el.innerHTML = '<div class="alert alert-warning">无法加载 ODD 规格</div>';
    }
}
