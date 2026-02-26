/**
 * Data management page — cleaning and identification.
 * 数据管理页面 — 数据清洗与辨识。
 */

import { apiPost, fmt, showLoader, showError, parseFloatList } from '../api.js';

export async function render(container) {
    container.innerHTML = `
        <div class="tabs">
            <button class="tab active" data-tab="outlier">异常检测 / Outlier Detection</button>
            <button class="tab" data-tab="ident">系统辨识 / Identification</button>
        </div>
        <div id="tab-outlier">
            <div class="card-grid card-grid-2">
                <div class="card">
                    <div class="card-header"><h3>异常检测参数</h3></div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>检测方法</label>
                            <select id="out-method" class="form-control">
                                <option value="3sigma">3-Sigma (Z-Score)</option>
                                <option value="iqr">IQR</option>
                                <option value="mad">MAD</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>阈值</label>
                            <input id="out-threshold" class="form-control" type="number" value="3.0" step="0.5">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>数据 (逗号分隔)</label>
                        <textarea id="out-data" class="form-control" rows="3" style="font-family:var(--font-mono);font-size:0.8rem">1.0, 1.1, 1.05, 0.98, 5.0, 1.02, 0.99, 1.08, 1.01, 10.0, 1.03</textarea>
                    </div>
                    <button id="out-run" class="btn btn-primary">检测异常 / Detect</button>
                </div>
                <div class="card">
                    <div class="card-header"><h3>检测结果</h3></div>
                    <div id="out-result"><p style="color:var(--text-muted)">输入数据后运行检测</p></div>
                </div>
            </div>
        </div>
        <div id="tab-ident" class="hidden">
            <div class="card">
                <div class="card-header"><h3>ARX 模型辨识</h3></div>
                <div class="form-row">
                    <div class="form-group">
                        <label>自回归阶数 na</label>
                        <input id="arx-na" class="form-control" type="number" value="2">
                    </div>
                    <div class="form-group">
                        <label>外源输入阶数 nb</label>
                        <input id="arx-nb" class="form-control" type="number" value="2">
                    </div>
                </div>
                <div class="form-group">
                    <label>输出 y (逗号分隔)</label>
                    <textarea id="arx-y" class="form-control" rows="2" style="font-family:var(--font-mono);font-size:0.8rem">${
                        Array.from({length:50}, (_,i) => (0.5 + 0.005*i + 0.02*Math.sin(i/3)).toFixed(4)).join(', ')
                    }</textarea>
                </div>
                <div class="form-group">
                    <label>输入 u (逗号分隔)</label>
                    <textarea id="arx-u" class="form-control" rows="2" style="font-family:var(--font-mono);font-size:0.8rem">${
                        Array.from({length:50}, (_,i) => (0.01 + 0.005*Math.sin(i/5)).toFixed(4)).join(', ')
                    }</textarea>
                </div>
                <button id="arx-run" class="btn btn-primary">辨识 / Identify</button>
                <div id="arx-result" style="margin-top:1rem"><p style="color:var(--text-muted)">配置后运行辨识</p></div>
            </div>
        </div>
    `;

    // Tab switching
    container.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-outlier').classList.toggle('hidden', tab.dataset.tab !== 'outlier');
            document.getElementById('tab-ident').classList.toggle('hidden', tab.dataset.tab !== 'ident');
        });
    });

    document.getElementById('out-run').addEventListener('click', runOutlier);
    document.getElementById('arx-run').addEventListener('click', runARX);
}

async function runOutlier() {
    const el = document.getElementById('out-result');
    showLoader(el);

    try {
        const data = parseFloatList(document.getElementById('out-data').value);
        const result = await apiPost('/api/dataclean/outliers', {
            data,
            method: document.getElementById('out-method').value,
            threshold: +document.getElementById('out-threshold').value,
        });

        el.innerHTML = `
            <div class="stat-card" style="margin-bottom:0.75rem">
                <div class="stat-label">检测到异常</div>
                <div class="stat-value ${result.n_outliers > 0 ? 'danger' : 'success'}">${result.n_outliers}</div>
            </div>
            <p><strong>异常索引:</strong> ${result.outlier_indices.length > 0 ? result.outlier_indices.join(', ') : '无'}</p>
            <p><strong>边界:</strong> [${fmt(result.bounds?.lower, 3)}, ${fmt(result.bounds?.upper, 3)}]</p>
        `;
    } catch (err) {
        showError(el, err);
    }
}

async function runARX() {
    const el = document.getElementById('arx-result');
    showLoader(el);

    try {
        const y = document.getElementById('arx-y').value.split(',').map(s => parseFloat(s.trim()));
        const u = document.getElementById('arx-u').value.split(',').map(s => parseFloat(s.trim()));

        const result = await apiPost('/api/identification/arx', {
            y, u,
            na: +document.getElementById('arx-na').value,
            nb: +document.getElementById('arx-nb').value,
        });

        el.innerHTML = `
            <div class="card-grid card-grid-2" style="margin-bottom:0.75rem">
                <div class="stat-card"><div class="stat-label">R²</div><div class="stat-value primary">${fmt(result.r_squared, 4)}</div></div>
                <div class="stat-card"><div class="stat-label">RMSE</div><div class="stat-value info">${fmt(result.rmse, 6)}</div></div>
            </div>
            <p><strong>a 系数:</strong> ${result.a_coefficients.map(v => fmt(v, 6)).join(', ')}</p>
            <p><strong>b 系数:</strong> ${result.b_coefficients.map(v => fmt(v, 6)).join(', ')}</p>
        `;
    } catch (err) {
        showError(el, err);
    }
}
