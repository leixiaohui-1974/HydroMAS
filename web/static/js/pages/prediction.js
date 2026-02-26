/**
 * Prediction page — forecasting interface.
 * 预测页面 — 预报接口。
 */

import { apiPost, apiGet, createLineChart, fmt, showLoader } from '../api.js';

let chart = null;

export async function render(container) {
    container.innerHTML = `
        <div class="card-grid card-grid-2">
            <div class="card">
                <div class="card-header">
                    <h3>预测参数 / Prediction Setup</h3>
                    <button id="pred-load-sample" class="btn btn-secondary" style="font-size:0.8rem">加载示例数据</button>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>预测模型</label>
                        <select id="pred-model" class="form-control">
                            <option value="linear">线性 Linear</option>
                            <option value="polynomial">多项式 Polynomial</option>
                            <option value="lstm">LSTM (stub)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>预测步数 Horizon</label>
                        <input id="pred-horizon" class="form-control" type="number" value="60">
                    </div>
                </div>
                <div class="form-group">
                    <label>历史数据 (逗号分隔或加载示例)</label>
                    <textarea id="pred-data" class="form-control" rows="4" style="font-family:var(--font-mono);font-size:0.8rem"></textarea>
                </div>
                <button id="pred-run" class="btn btn-primary">运行预测 / Predict</button>
            </div>
            <div class="card">
                <div class="card-header"><h3>预测曲线 / Forecast</h3></div>
                <div class="chart-container tall"><canvas id="pred-chart"></canvas></div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>预测结果 / Results</h3></div>
            <div id="pred-results"><p style="color:var(--text-muted)">选择模型和数据后运行预测</p></div>
        </div>
    `;

    document.getElementById('pred-run').addEventListener('click', runPrediction);
    document.getElementById('pred-load-sample').addEventListener('click', loadSample);

    // Pre-populate with some default data
    const defaultData = Array.from({length: 50}, (_, i) => (0.5 + 0.01 * i + 0.002 * Math.sin(i/5)).toFixed(3));
    document.getElementById('pred-data').value = defaultData.join(', ');
}

async function loadSample() {
    try {
        const data = await apiGet('/api/prediction/sample-data');
        document.getElementById('pred-data').value = data.water_level.slice(0, 100).map(v => v.toFixed(3)).join(', ');
    } catch (err) {
        alert('加载失败: ' + err.message);
    }
}

async function runPrediction() {
    const resultsEl = document.getElementById('pred-results');
    showLoader(resultsEl);

    try {
        const rawData = document.getElementById('pred-data').value.trim();
        const historical = rawData.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));

        const result = await apiPost('/api/prediction/run', {
            historical_data: historical,
            horizon: +document.getElementById('pred-horizon').value,
            model: document.getElementById('pred-model').value,
        });

        // Chart
        if (chart) chart.destroy();
        const canvas = document.getElementById('pred-chart');
        const n = historical.length;
        const labels = Array.from({length: n + result.predictions.length}, (_, i) => i);

        const histDs = labels.map((_, i) => i < n ? historical[i] : null);
        const predDs = labels.map((_, i) => i >= n - 1 ? (i === n - 1 ? historical[n-1] : result.predictions[i - n]) : null);

        chart = createLineChart(canvas, labels, [
            { label: '历史 Historical', data: histDs, borderColor: '#2563eb', tension: 0.3, pointRadius: 0 },
            { label: '预测 Forecast', data: predDs, borderColor: '#d97706', borderDash: [5,3], tension: 0.3, pointRadius: 0 },
        ]);

        resultsEl.innerHTML = `
            <div class="card-grid card-grid-3">
                <div class="stat-card"><div class="stat-label">模型</div><div class="stat-value" style="font-size:1rem">${result.method || 'N/A'}</div></div>
                <div class="stat-card"><div class="stat-label">R²</div><div class="stat-value primary">${fmt(result.r_squared, 4)}</div></div>
                <div class="stat-card"><div class="stat-label">预测均值</div><div class="stat-value info">${fmt(result.predictions.reduce((a,b)=>a+b,0)/result.predictions.length, 3)}</div></div>
            </div>
        `;
    } catch (err) {
        resultsEl.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}
