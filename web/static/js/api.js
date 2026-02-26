/**
 * HydroOS API client utility.
 * API 客户端工具。
 */

export async function apiPost(url, data = {}) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || JSON.stringify(err));
    }
    return resp.json();
}

export async function apiGet(url) {
    const resp = await fetch(url);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || JSON.stringify(err));
    }
    return resp.json();
}

/**
 * Escape HTML special characters to prevent XSS.
 */
const _ESC = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
export function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, c => _ESC[c]);
}

/**
 * Show an error message in an element (XSS-safe).
 */
export function showError(el, err) {
    el.innerHTML = `<div class="alert alert-danger">${escapeHtml(err.message || String(err))}</div>`;
}

/**
 * Parse a comma-separated string into an array of floats, filtering NaN.
 */
export function parseFloatList(str) {
    return str.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
}

/**
 * Show a loading spinner inside an element.
 */
export function showLoader(el) {
    el.innerHTML = '<div class="loader"><div class="spinner"></div></div>';
}

/**
 * Format a number for display.
 */
export function fmt(n, digits = 4) {
    if (n === null || n === undefined) return 'N/A';
    if (typeof n === 'number') return n.toFixed(digits);
    return String(n);
}

/**
 * Safe array max (avoids stack overflow with spread on large arrays).
 */
export function safeMax(arr) {
    let max = -Infinity;
    for (let i = 0; i < arr.length; i++) {
        if (arr[i] > max) max = arr[i];
    }
    return max;
}

/**
 * Create and render a Chart.js line chart.
 */
export function createLineChart(canvas, labels, datasets, options = {}) {
    return new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 12 } } },
            },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: '#e2e8f0' } },
            },
            ...options,
        },
    });
}

/**
 * Format JSON result for display.
 */
export function formatResult(data) {
    return JSON.stringify(data, null, 2);
}
