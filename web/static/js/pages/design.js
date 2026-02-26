/**
 * Design page — sensitivity analysis & tank sizing.
 * 设计页面 — 敏感性分析与水箱尺寸优化。
 */

import { apiPost, createLineChart, fmt, showLoader, showError, escapeHtml } from '../api.js';

let chart = null;

export async function render(container) {
    container.innerHTML = `
        <div class="tabs">
            <button class="tab active" data-tab="sensitivity">敏感性分析 / Sensitivity</button>
            <button class="tab" data-tab="sizing">水箱设计 / Tank Sizing</button>
        </div>
        <div id="tab-sensitivity">
            <div class="card-grid card-grid-2">
                <div class="card">
                    <div class="card-header"><h3>敏感性参数</h3></div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>分析方法</label>
                            <select id="sens-method" class="form-control">
                                <option value="OAT">OAT (单因素)</option>
                                <option value="Morris">Morris (基本效应)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>水平数 n_levels</label>
                            <input id="sens-levels" class="form-control" type="number" value="10">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>参数范围 (JSON)</label>
                        <textarea id="sens-ranges" class="form-control" rows="3" style="font-family:var(--font-mono);font-size:0.8rem">{"area": [0.5, 2.0], "cd": [0.3, 0.9], "outlet_area": [0.005, 0.02]}</textarea>
                    </div>
                    <button id="sens-run" class="btn btn-primary">运行分析 / Run</button>
                </div>
                <div class="card">
                    <div class="card-header"><h3>敏感性排名 / Ranking</h3></div>
                    <div id="sens-result"><p style="color:var(--text-muted)">配置后运行分析</p></div>
                </div>
            </div>
        </div>
        <div id="tab-sizing" class="hidden">
            <div class="card-grid card-grid-2">
                <div class="card">
                    <div class="card-header"><h3>设计参数</h3></div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>峰值需求 (m³/s)</label>
                            <input id="size-demand" class="form-control" type="number" value="0.03" step="0.005">
                        </div>
                        <div class="form-group">
                            <label>持续时间 (h)</label>
                            <input id="size-hours" class="form-control" type="number" value="4" step="0.5">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>安全系数</label>
                        <input id="size-safety" class="form-control" type="number" value="1.2" step="0.1">
                    </div>
                    <button id="size-run" class="btn btn-primary">计算尺寸 / Calculate</button>
                </div>
                <div class="card">
                    <div class="card-header"><h3>设计结果</h3></div>
                    <div id="size-result"><p style="color:var(--text-muted)">配置后计算</p></div>
                </div>
            </div>
        </div>
    `;

    // Tab switching
    container.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-sensitivity').classList.toggle('hidden', tab.dataset.tab !== 'sensitivity');
            document.getElementById('tab-sizing').classList.toggle('hidden', tab.dataset.tab !== 'sizing');
        });
    });

    document.getElementById('sens-run').addEventListener('click', runSensitivity);
    document.getElementById('size-run').addEventListener('click', runSizing);
}

async function runSensitivity() {
    const el = document.getElementById('sens-result');
    showLoader(el);

    try {
        const ranges = JSON.parse(document.getElementById('sens-ranges').value);
        const baseParams = {};
        for (const [k, [lo, hi]] of Object.entries(ranges)) {
            baseParams[k] = (lo + hi) / 2;
        }

        const result = await apiPost('/api/design/sensitivity', {
            base_params: baseParams,
            param_ranges: ranges,
            method: document.getElementById('sens-method').value,
            n_levels: +document.getElementById('sens-levels').value,
        });

        let html = '<table class="data-table"><thead><tr><th>排名</th><th>参数</th><th>敏感性指标</th></tr></thead><tbody>';
        const ranking = result.ranking || [];
        ranking.forEach((name, i) => {
            const p = result.parameters[name] || {};
            const idx = p.sensitivity_index !== undefined ? fmt(p.sensitivity_index, 4) : fmt(p.mu_star, 4);
            html += `<tr><td>${i + 1}</td><td>${escapeHtml(name)}</td><td>${idx}</td></tr>`;
        });
        html += '</tbody></table>';
        html += `<p style="color:var(--text-secondary);margin-top:0.5rem;font-size:0.8rem">方法: ${escapeHtml(result.method)}</p>`;

        el.innerHTML = html;
    } catch (err) {
        showError(el, err);
    }
}

async function runSizing() {
    const el = document.getElementById('size-result');
    showLoader(el);

    try {
        const result = await apiPost('/api/design/sizing', {
            demand_peak: +document.getElementById('size-demand').value,
            duration_hours: +document.getElementById('size-hours').value,
            safety_factor: +document.getElementById('size-safety').value,
        });

        el.innerHTML = `
            <div class="card-grid card-grid-2" style="margin-bottom:0.75rem">
                <div class="stat-card"><div class="stat-label">所需容积</div><div class="stat-value primary">${fmt(result.required_volume, 2)} m³</div></div>
                <div class="stat-card"><div class="stat-label">建议面积</div><div class="stat-value info">${fmt(result.recommended_area, 2)} m²</div></div>
            </div>
            <div class="result-block">${escapeHtml(JSON.stringify(result, null, 2))}</div>
        `;
    } catch (err) {
        showError(el, err);
    }
}
