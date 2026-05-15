/**
 * Portfolio Tracker -- Chart rendering with Chart.js.
 * Handles the portfolio value over time chart and per-asset price history modal.
 */

document.addEventListener('DOMContentLoaded', function () {
    // ---------------------------------------------------------------
    // Portfolio Value Over Time Chart (dashboard only)
    // ---------------------------------------------------------------
    var portfolioChartInstance = null;

    window.loadPortfolioChart = function (currentValue) {
        var portfolioCanvas = document.getElementById('portfolioChart');
        if (!portfolioCanvas) return;

        // Destroy existing chart before re-rendering
        if (portfolioChartInstance) {
            portfolioChartInstance.destroy();
            portfolioChartInstance = null;
        }

        var url = '/api/portfolio_history';
        if (currentValue != null) {
            url += '?current_value=' + encodeURIComponent(currentValue);
        }

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data || data.length === 0) {
                    portfolioCanvas.parentElement.innerHTML += '<p class="muted" style="text-align:center;margin-top:1rem;">No data yet -- add transactions to see your portfolio chart.</p>';
                    return;
                }
                var labels = data.map(function (d) { return d.date; });
                var values = data.map(function (d) { return d.value; });

                portfolioChartInstance = new Chart(portfolioCanvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Portfolio Value ($)',
                            data: values,
                            borderColor: '#4f8cff',
                            backgroundColor: 'rgba(79,140,255,0.08)',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 2,
                            pointHoverRadius: 5,
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function (ctx) {
                                        return '$' + ctx.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2 });
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                ticks: { color: '#8a8f9e', maxTicksLimit: 12 }
                            },
                            y: {
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                ticks: {
                                    color: '#8a8f9e',
                                    callback: function (val) { return '$' + val.toLocaleString(); }
                                }
                            }
                        }
                    }
                });
            })
            .catch(function (err) {
                console.error('Portfolio chart error:', err);
            });
    };

    // Chart is intentionally NOT auto-loaded here.
    // prices.js triggers loadPortfolioChart(total_value) once live prices are
    // available (from cache or a fresh fetch), ensuring the final chart point
    // always matches the correct live total -- no double-render, no race.

    // ---------------------------------------------------------------
    // Per-Asset Price History Modal
    // ---------------------------------------------------------------
    var modal = document.getElementById('assetChartModal');
    var closeBtn = document.getElementById('closeModal');
    var assetCanvas = document.getElementById('assetChart');
    var titleEl = document.getElementById('assetChartTitle');
    var assetChartInstance = null;

    // State for the currently open asset
    var currentSymbol = '';
    var currentType = '';
    var currentAvgCost = 0;
    var currentPeriod = '1M';

    // Determine asset type from the page context or button data
    function getAssetType(btn) {
        var explicit = btn.getAttribute('data-type');
        if (explicit) return explicit;
        // Try to infer from the page: look for account type badge
        var badge = document.querySelector('.badge-crypto');
        if (badge) return 'crypto';
        return 'stock';
    }

    function loadAssetChart() {
        if (!currentSymbol) return;

        var url = '/api/price_history?symbol=' + encodeURIComponent(currentSymbol)
            + '&type=' + encodeURIComponent(currentType)
            + '&period=' + encodeURIComponent(currentPeriod);

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (assetChartInstance) {
                    assetChartInstance.destroy();
                    assetChartInstance = null;
                }

                if (!data || data.length === 0) {
                    assetCanvas.parentElement.insertAdjacentHTML('beforeend',
                        '<p class="muted chart-empty-msg" style="text-align:center;">No price data available for this period.</p>');
                    return;
                }

                // Remove any previous empty message
                var emptyMsg = assetCanvas.parentElement.querySelector('.chart-empty-msg');
                if (emptyMsg) emptyMsg.remove();

                var labels = data.map(function (d) { return d.date; });
                var prices = data.map(function (d) { return d.price; });

                // Cost basis line
                var costLine = labels.map(function () { return currentAvgCost; });

                assetChartInstance = new Chart(assetCanvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: currentSymbol.toUpperCase() + ' Price',
                                data: prices,
                                borderColor: '#4f8cff',
                                backgroundColor: 'rgba(79,140,255,0.08)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: 1,
                                pointHoverRadius: 4,
                                borderWidth: 2
                            },
                            {
                                label: 'Avg Cost Basis ($' + currentAvgCost.toFixed(2) + ')',
                                data: costLine,
                                borderColor: '#eab308',
                                borderDash: [6, 4],
                                borderWidth: 2,
                                pointRadius: 0,
                                fill: false
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                labels: { color: '#e4e6ed' }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function (ctx) {
                                        return ctx.dataset.label + ': $' + ctx.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2 });
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                ticks: { color: '#8a8f9e', maxTicksLimit: 10 }
                            },
                            y: {
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                ticks: {
                                    color: '#8a8f9e',
                                    callback: function (val) { return '$' + val.toLocaleString(); }
                                }
                            }
                        }
                    }
                });
            })
            .catch(function (err) {
                console.error('Asset chart error:', err);
            });
    }

    // Open modal on chart button click
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.chart-btn');
        if (!btn) return;

        currentSymbol = btn.getAttribute('data-symbol') || '';
        currentType = getAssetType(btn);
        currentAvgCost = parseFloat(btn.getAttribute('data-avg-cost')) || 0;
        var name = btn.getAttribute('data-name') || currentSymbol;
        currentPeriod = '1M';

        titleEl.textContent = name + ' (' + currentSymbol.toUpperCase() + ') -- Price History';
        modal.classList.remove('hidden');

        // Reset period buttons
        document.querySelectorAll('.period-btn').forEach(function (b) {
            b.classList.remove('active');
            if (b.getAttribute('data-period') === '1M') b.classList.add('active');
        });

        loadAssetChart();
    });

    // Close modal
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            modal.classList.add('hidden');
            if (assetChartInstance) {
                assetChartInstance.destroy();
                assetChartInstance = null;
            }
        });
    }
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.classList.add('hidden');
                if (assetChartInstance) {
                    assetChartInstance.destroy();
                    assetChartInstance = null;
                }
            }
        });
    }

    // Period selector
    document.addEventListener('click', function (e) {
        if (!e.target.classList.contains('period-btn')) return;
        document.querySelectorAll('.period-btn').forEach(function (b) { b.classList.remove('active'); });
        e.target.classList.add('active');
        currentPeriod = e.target.getAttribute('data-period');
        loadAssetChart();
    });
});
