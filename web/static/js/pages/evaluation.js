/**
 * Evaluation page — performance metrics and WNAL.
 * 评价页面 — 性能指标与 WNAL。
 */

import { apiPost, fmt, showLoader, showError, parseFloatList, escapeHtml } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="tabs">
            <button class="tab active" data-tab="perf">性能评价 / Performance</button>
            <button class="tab" data-tab="wnal">WNAL 评估</button>
        </div>
        <div id="tab-perf">
            <div class="card">
                <div class="card-header"><h3>评价设置</h3></div>
                <div class="form-group">
                    <label>观测值 Observed (逗号分隔)</label>
                    <textarea id="eval-obs" class="form-control" rows="2" style="font-family:var(--font-mono);font-size:0.8rem">${
                        Array.from({length:20}, () => '1.0').join(', ')
                    }</textarea>
                </div>
                <div class="form-group">
                    <label>预测/响应值 Predicted (逗号分隔)</label>
                    <textarea id="eval-pred" class="form-control" rows="2" style="font-family:var(--font-mono);font-size:0.8rem">${
                        [0.0,0.3,0.6,0.85,1.05,1.02,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0].join(', ')
                    }</textarea>
                </div>
                <button id="eval-run" class="btn btn-primary">评价 / Evaluate</button>
                <div id="eval-result" style="margin-top:1rem"></div>
            </div>
        </div>
        <div id="tab-wnal" class="hidden">
            <div class="card">
                <div class="card-header"><h3>WNAL 能力评估</h3></div>
                <div class="form-row">
                    <div class="form-group"><label>传感监测 sensing</label><input id="w-sensing" class="form-control" type="number" value="80" min="0" max="100"></div>
                    <div class="form-group"><label>数据传输 communication</label><input id="w-comm" class="form-control" type="number" value="70" min="0" max="100"></div>
                    <div class="form-group"><label>模型精度 modeling</label><input id="w-model" class="form-control" type="number" value="65" min="0" max="100"></div>
                    <div class="form-group"><label>预报能力 prediction</label><input id="w-pred" class="form-control" type="number" value="60" min="0" max="100"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>控制水平 control</label><input id="w-ctrl" class="form-control" type="number" value="75" min="0" max="100"></div>
                    <div class="form-group"><label>ODD 感知 odd_monitoring</label><input id="w-odd" class="form-control" type="number" value="50" min="0" max="100"></div>
                    <div class="form-group"><label>AI 决策 decision_support</label><input id="w-ai" class="form-control" type="number" value="40" min="0" max="100"></div>
                </div>
                <button id="wnal-run" class="btn btn-primary" style="margin-top:0.5rem">评估 WNAL / Assess</button>
                <div id="wnal-result" style="margin-top:1rem"></div>
            </div>
        </div>
    `;

    // Tab switching
    container.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-perf').classList.toggle('hidden', tab.dataset.tab !== 'perf');
            document.getElementById('tab-wnal').classList.toggle('hidden', tab.dataset.tab !== 'wnal');
        });
    });

    document.getElementById('eval-run').addEventListener('click', runEval);
    document.getElementById('wnal-run').addEventListener('click', runWNAL);
}

async function runEval() {
    const el = document.getElementById('eval-result');
    showLoader(el);

    try {
        const obs = parseFloatList(document.getElementById('eval-obs').value);
        const pred = parseFloatList(document.getElementById('eval-pred').value);

        const result = await apiPost('/api/evaluation/performance', {
            observed: obs, predicted: pred,
            metrics: ['RMSE', 'MAE', 'NSE', 'SETTLING_TIME', 'OVERSHOOT', 'STEADY_STATE_ERROR'],
            time_series: Array.from({length: obs.length}, (_, i) => i),
            setpoint: 1.0,
        });

        let html = '<table class="data-table"><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>';
        for (const [k, v] of Object.entries(result)) {
            html += `<tr><td>${k}</td><td>${fmt(v)}</td></tr>`;
        }
        html += '</tbody></table>';
        el.innerHTML = html;
    } catch (err) {
        showError(el, err);
    }
}

async function runWNAL() {
    const el = document.getElementById('wnal-result');
    showLoader(el);

    try {
        const capabilities = {
            sensing: +document.getElementById('w-sensing').value,
            communication: +document.getElementById('w-comm').value,
            modeling: +document.getElementById('w-model').value,
            prediction: +document.getElementById('w-pred').value,
            control: +document.getElementById('w-ctrl').value,
            odd_monitoring: +document.getElementById('w-odd').value,
            decision_support: +document.getElementById('w-ai').value,
        };

        const result = await apiPost('/api/evaluation/wnal', { capabilities });

        const levelColors = { L0: 'danger', L1: 'warning', L2: 'warning', L3: 'info', L4: 'primary', L5: 'success' };

        el.innerHTML = `
            <div class="card-grid card-grid-3" style="margin-bottom:1rem">
                <div class="stat-card"><div class="stat-label">自主等级</div><div class="stat-value ${levelColors[result.level] || 'primary'}">${result.level}</div></div>
                <div class="stat-card"><div class="stat-label">综合得分</div><div class="stat-value info">${fmt(result.score, 1)}</div></div>
                <div class="stat-card"><div class="stat-label">等级描述</div><div class="stat-value" style="font-size:0.8rem">${escapeHtml(result.level_description)}</div></div>
            </div>
            ${result.recommendations && result.recommendations.length > 0 ? `
                <div class="alert alert-info">
                    <strong>升级建议:</strong>
                    <ul style="margin:0.3rem 0 0 1.2rem">${result.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
                </div>
            ` : ''}
        `;
    } catch (err) {
        showError(el, err);
    }
}
