/**
 * Simulation page — tank simulation interface.
 * 仿真页面 — 水箱仿真接口。
 */

import { apiPost, apiGet, createLineChart, fmt, showLoader, showError, safeMax, escapeHtml } from '../api.js';

let chart = null;

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-2">
            <div class="card">
                <div class="card-header"><h3>仿真参数 / Simulation Parameters</h3></div>
                <div class="form-row">
                    <div class="form-group">
                        <label>仿真时长 Duration (s)</label>
                        <input id="sim-duration" class="form-control" type="number" value="300">
                    </div>
                    <div class="form-group">
                        <label>时间步长 dt (s)</label>
                        <input id="sim-dt" class="form-control" type="number" value="1.0" step="0.1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>初始水位 Initial h (m)</label>
                        <input id="sim-h0" class="form-control" type="number" value="0.5" step="0.1">
                    </div>
                    <div class="form-group">
                        <label>求解器 Solver</label>
                        <select id="sim-solver" class="form-control">
                            <option value="euler">Euler (一阶)</option>
                            <option value="rk4">RK4 (四阶 Runge-Kutta)</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>入流量分段 Q_in Profile (JSON [[t, q], ...])</label>
                    <input id="sim-qin" class="form-control" value='[[0, 0.01], [100, 0.03], [200, 0.01]]'>
                </div>
                <button id="sim-run-btn" class="btn btn-primary" style="margin-top:0.5rem">
                    运行仿真 / Run Simulation
                </button>
            </div>
            <div class="card">
                <div class="card-header"><h3>水位曲线 / Water Level</h3></div>
                <div class="chart-container tall"><canvas id="sim-chart"></canvas></div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>仿真结果 / Results</h3></div>
            <div id="sim-results"><p style="color:var(--text-muted)">请配置参数后点击运行 / Configure and click Run</p></div>
        </div>
    `;

    document.getElementById('sim-run-btn').addEventListener('click', runSimulation);
}

async function runSimulation() {
    const resultsEl = document.getElementById('sim-results');
    showLoader(resultsEl);

    try {
        const qin = JSON.parse(document.getElementById('sim-qin').value);
        const data = await apiPost('/api/simulation/run', {
            duration: +document.getElementById('sim-duration').value,
            dt: +document.getElementById('sim-dt').value,
            initial_h: +document.getElementById('sim-h0').value,
            q_in_profile: qin,
            solver: document.getElementById('sim-solver').value,
        });

        // Chart
        if (chart) chart.destroy();
        const canvas = document.getElementById('sim-chart');
        const step = Math.max(1, Math.floor(data.time.length / 150));
        const labels = data.time.filter((_, i) => i % step === 0).map(t => t.toFixed(0));

        chart = createLineChart(canvas, labels, [
            {
                label: '水位 (m)',
                data: data.water_level.filter((_, i) => i % step === 0),
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37,99,235,0.1)',
                fill: true, tension: 0.3, pointRadius: 0,
            },
            {
                label: '出流量 (m³/s)',
                data: data.outflow.filter((_, i) => i % step === 0),
                borderColor: '#059669',
                tension: 0.3, pointRadius: 0,
                yAxisID: 'y1',
            },
        ], {
            scales: {
                y: { title: { display: true, text: '水位 (m)' }, grid: { color: '#e2e8f0' } },
                y1: { position: 'right', title: { display: true, text: '出流量 (m³/s)' }, grid: { display: false } },
                x: { title: { display: true, text: '时间 (s)' }, grid: { display: false } },
            },
        });

        // Results table
        const meta = data.metadata || {};
        resultsEl.innerHTML = `
            <div class="card-grid card-grid-4">
                <div class="stat-card"><div class="stat-label">最高水位</div><div class="stat-value primary">${fmt(safeMax(data.water_level), 3)}</div></div>
                <div class="stat-card"><div class="stat-label">最终水位</div><div class="stat-value info">${fmt(data.water_level[data.water_level.length - 1], 3)}</div></div>
                <div class="stat-card"><div class="stat-label">数据点数</div><div class="stat-value">${data.time.length}</div></div>
                <div class="stat-card"><div class="stat-label">求解器</div><div class="stat-value" style="font-size:1rem">${meta.solver || 'N/A'}</div></div>
            </div>
        `;
    } catch (err) {
        showError(resultsEl, err);
    }
}
