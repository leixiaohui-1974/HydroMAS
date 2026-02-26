/**
 * Control page — PID/MPC control design.
 * 控制页面 — PID/MPC 控制设计。
 */

import { apiPost, apiGet, createLineChart, fmt, showLoader } from '../api.js';

let chart = null;

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-2">
            <div class="card">
                <div class="card-header"><h3>控制器参数 / Controller Setup</h3></div>
                <div class="form-row">
                    <div class="form-group">
                        <label>控制器类型</label>
                        <select id="ctrl-type" class="form-control">
                            <option value="PID">PID</option>
                            <option value="MPC">MPC</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>目标水位 Setpoint (m)</label>
                        <input id="ctrl-sp" class="form-control" type="number" value="1.0" step="0.1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>仿真时长 (s)</label>
                        <input id="ctrl-dur" class="form-control" type="number" value="300">
                    </div>
                    <div class="form-group">
                        <label>初始水位 (m)</label>
                        <input id="ctrl-h0" class="form-control" type="number" value="0.5" step="0.1">
                    </div>
                </div>
                <button id="ctrl-run" class="btn btn-primary" style="margin-top:0.5rem">运行控制 / Run</button>
                <button id="ctrl-compare" class="btn btn-secondary" style="margin-top:0.5rem;margin-left:0.5rem">PID vs MPC 对比</button>
            </div>
            <div class="card">
                <div class="card-header"><h3>闭环响应 / Closed-Loop Response</h3></div>
                <div class="chart-container tall"><canvas id="ctrl-chart"></canvas></div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>性能指标 / Performance</h3></div>
            <div id="ctrl-results"><p style="color:var(--text-muted)">运行控制仿真查看结果</p></div>
        </div>
    `;

    document.getElementById('ctrl-run').addEventListener('click', runControl);
    document.getElementById('ctrl-compare').addEventListener('click', compareControllers);
}

async function runControl() {
    const resultsEl = document.getElementById('ctrl-results');
    showLoader(resultsEl);

    try {
        const data = await apiPost('/api/control/run', {
            setpoint: +document.getElementById('ctrl-sp').value,
            controller_type: document.getElementById('ctrl-type').value,
            duration: +document.getElementById('ctrl-dur').value,
            initial_h: +document.getElementById('ctrl-h0').value,
        });

        drawChart([{ label: document.getElementById('ctrl-type').value, data, color: '#2563eb' }],
                   +document.getElementById('ctrl-sp').value);

        showMetrics(resultsEl, data);
    } catch (err) {
        resultsEl.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

async function compareControllers() {
    const resultsEl = document.getElementById('ctrl-results');
    showLoader(resultsEl);

    const sp = +document.getElementById('ctrl-sp').value;
    const dur = +document.getElementById('ctrl-dur').value;
    const h0 = +document.getElementById('ctrl-h0').value;

    try {
        const [pid, mpc] = await Promise.all([
            apiPost('/api/control/run', { setpoint: sp, controller_type: 'PID', duration: dur, initial_h: h0 }),
            apiPost('/api/control/run', { setpoint: sp, controller_type: 'MPC', duration: dur, initial_h: h0 }),
        ]);

        drawChart([
            { label: 'PID', data: pid, color: '#2563eb' },
            { label: 'MPC', data: mpc, color: '#059669' },
        ], sp);

        resultsEl.innerHTML = `
            <table class="data-table">
                <thead><tr><th>指标</th><th>PID</th><th>MPC</th></tr></thead>
                <tbody>
                    <tr><td>最终水位 (m)</td><td>${fmt(pid.water_level[pid.water_level.length-1])}</td><td>${fmt(mpc.water_level[mpc.water_level.length-1])}</td></tr>
                    <tr><td>最大水位 (m)</td><td>${fmt(Math.max(...pid.water_level))}</td><td>${fmt(Math.max(...mpc.water_level))}</td></tr>
                    <tr><td>求解器</td><td>${pid.metadata?.solver||'N/A'}</td><td>${mpc.metadata?.solver||'N/A'}</td></tr>
                </tbody>
            </table>
        `;
    } catch (err) {
        resultsEl.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

function drawChart(series, setpoint) {
    if (chart) chart.destroy();
    const canvas = document.getElementById('ctrl-chart');
    const first = series[0].data;
    const step = Math.max(1, Math.floor(first.time.length / 150));
    const labels = first.time.filter((_, i) => i % step === 0).map(t => t.toFixed(0));

    const datasets = series.map(s => ({
        label: s.label + ' 水位',
        data: s.data.water_level.filter((_, i) => i % step === 0),
        borderColor: s.color,
        tension: 0.3, pointRadius: 0,
    }));

    // Setpoint line
    datasets.push({
        label: '目标 Setpoint',
        data: labels.map(() => setpoint),
        borderColor: '#dc2626',
        borderDash: [6, 3],
        pointRadius: 0,
    });

    chart = createLineChart(canvas, labels, datasets, {
        scales: {
            y: { title: { display: true, text: '水位 (m)' } },
            x: { title: { display: true, text: '时间 (s)' } },
        },
    });
}

function showMetrics(el, data) {
    const wl = data.water_level;
    el.innerHTML = `
        <div class="card-grid card-grid-4">
            <div class="stat-card"><div class="stat-label">最终水位</div><div class="stat-value primary">${fmt(wl[wl.length-1], 3)}</div></div>
            <div class="stat-card"><div class="stat-label">最大水位</div><div class="stat-value info">${fmt(Math.max(...wl), 3)}</div></div>
            <div class="stat-card"><div class="stat-label">控制器</div><div class="stat-value" style="font-size:1rem">${data.metadata?.solver||'N/A'}</div></div>
            <div class="stat-card"><div class="stat-label">数据点</div><div class="stat-value">${wl.length}</div></div>
        </div>
    `;
}
