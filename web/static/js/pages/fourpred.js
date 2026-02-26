/**
 * 四预 System page — Forecast→Warning→Rehearsal→Plan.
 * 四预系统页面 — 预报→预警→预演→预案。
 */

import { apiPost, createLineChart, fmt, showLoader, showError, parseFloatList, escapeHtml } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="alert alert-info">
            四预闭环系统: <strong>预报 Forecast</strong> → <strong>预警 Warning</strong> → <strong>预演 Rehearsal</strong> → <strong>预案 Plan</strong>
        </div>
        <div class="card-grid card-grid-2">
            <div class="card">
                <div class="card-header"><h3>四预参数 / Parameters</h3></div>
                <div class="form-group">
                    <label>水位数据 (逗号分隔)</label>
                    <textarea id="fp-data" class="form-control" rows="3" style="font-family:var(--font-mono);font-size:0.8rem">${
                        Array.from({length:50}, (_,i) => (0.5 + 0.02*i + 0.1*Math.sin(i/3)).toFixed(3)).join(', ')
                    }</textarea>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>风险阈值 Risk Threshold</label>
                        <input id="fp-threshold" class="form-control" type="number" value="0.7" step="0.05" min="0" max="1">
                    </div>
                </div>
                <button id="fp-run" class="btn btn-primary">运行四预闭环 / Run Loop</button>
            </div>
            <div class="card">
                <div class="card-header"><h3>执行步骤 / Steps</h3></div>
                <div id="fp-steps" style="padding:0.5rem">
                    <div class="step-item pending">① 预报 Forecast</div>
                    <div class="step-item pending">② 预警 Warning</div>
                    <div class="step-item pending">③ 预演 Rehearsal</div>
                    <div class="step-item pending">④ 预案 Plan</div>
                </div>
            </div>
        </div>
        <div class="card" style="margin-top:1rem">
            <div class="card-header"><h3>四预结果 / Results</h3></div>
            <div id="fp-results"><p style="color:var(--text-muted)">配置参数后运行四预闭环</p></div>
        </div>
    `;

    // Add step styles
    const style = document.createElement('style');
    style.textContent = `
        .step-item { padding: 0.5rem 0.75rem; margin: 0.3rem 0; border-radius: var(--radius); font-size: 0.9rem; }
        .step-item.pending { background: var(--bg); color: var(--text-muted); }
        .step-item.done { background: var(--success-light); color: var(--success); }
        .step-item.active { background: var(--primary-100); color: var(--primary); }
        .step-item.skipped { background: var(--bg); color: var(--text-muted); text-decoration: line-through; }
    `;
    container.appendChild(style);

    document.getElementById('fp-run').addEventListener('click', runFourPred);
}

async function runFourPred() {
    const resultsEl = document.getElementById('fp-results');
    showLoader(resultsEl);

    try {
        const rawData = document.getElementById('fp-data').value.trim();
        const waterData = parseFloatList(rawData);

        const result = await apiPost('/api/skills/four-prediction', {
            water_level_data: waterData,
            risk_threshold: +document.getElementById('fp-threshold').value,
        });

        // Update steps
        const stepsEl = document.getElementById('fp-steps');
        const completed = result.steps_completed || [];
        const stepNames = ['forecast', 'warning', 'rehearsal', 'plan'];
        const stepLabels = ['① 预报 Forecast', '② 预警 Warning', '③ 预演 Rehearsal', '④ 预案 Plan'];

        stepsEl.innerHTML = stepNames.map((name, i) => {
            const cls = completed.includes(name) ? 'done' : 'skipped';
            return `<div class="step-item ${cls}">${stepLabels[i]} ${cls === 'done' ? '✓' : '—'}</div>`;
        }).join('');

        // Results
        const data = result.data || {};
        let html = `<div class="alert ${result.success ? 'alert-success' : 'alert-warning'}">${result.success ? '四预闭环完成' : '部分完成'} (${fmt(result.execution_time, 2)}s)</div>`;

        if (data.forecast) {
            html += `<h4 style="margin:0.75rem 0 0.5rem">预报结果</h4>`;
            html += `<div class="result-block">${escapeHtml(JSON.stringify(data.forecast, null, 2).substring(0, 500))}</div>`;
        }
        if (data.warning) {
            const risk = data.warning.risk_level || 'N/A';
            html += `<h4 style="margin:0.75rem 0 0.5rem">预警结果 — 风险等级: <span class="zone-badge ${risk === 'high' ? 'zone-mrc' : risk === 'medium' ? 'zone-extended' : 'zone-normal'}">${escapeHtml(risk)}</span></h4>`;
        }
        if (data.rehearsal) {
            html += `<h4 style="margin:0.75rem 0 0.5rem">预演结果</h4>`;
            html += `<div class="result-block">${escapeHtml(JSON.stringify(data.rehearsal, null, 2).substring(0, 500))}</div>`;
        }
        if (data.plan) {
            html += `<h4 style="margin:0.75rem 0 0.5rem">预案结果</h4>`;
            html += `<div class="result-block">${escapeHtml(JSON.stringify(data.plan, null, 2).substring(0, 500))}</div>`;
        }

        resultsEl.innerHTML = html;
    } catch (err) {
        showError(resultsEl, err);
    }
}
