/**
 * Portfolio Tracker — Lazy price loading with sessionStorage caching.
 *
 * Strategy:
 *   - Server renders pages without live prices (fast).
 *   - On first visit this session, auto-fetches /api/dashboard_data and caches in sessionStorage.
 *   - Cache is invalidated automatically if:
 *       a) A new transaction was added since the cache was saved (last_tx_ts mismatch), OR
 *       b) The cache is older than CACHE_TTL_MS (5 minutes).
 *   - "Refresh / Recalculate" button clears cache, re-fetches prices, and reloads the chart.
 */

(function () {
    'use strict';

    var CACHE_KEY = 'portfolioPriceData';
    var CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

    function getCachedData(serverLastTxTs) {
        try {
            var raw = sessionStorage.getItem(CACHE_KEY);
            if (!raw) return null;
            var obj = JSON.parse(raw);

            // Invalidate if TTL exceeded
            if (Date.now() - (obj._cachedAt || 0) > CACHE_TTL_MS) return null;

            // Invalidate if new transactions were added since the cache was saved
            if (serverLastTxTs && obj.last_tx_ts !== serverLastTxTs) return null;

            return obj;
        } catch (e) {
            return null;
        }
    }

    function setCachedData(data) {
        try {
            data._cachedAt = Date.now();
            sessionStorage.setItem(CACHE_KEY, JSON.stringify(data));
        } catch (e) { /* storage full — silently ignore */ }
    }

    function clearCache() {
        sessionStorage.removeItem(CACHE_KEY);
    }

    // -----------------------------------------------------------------------
    // Formatting helpers
    // -----------------------------------------------------------------------

    function fmtMoney(val) {
        return '$' + parseFloat(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function fmtMoneySign(val) {
        var n = parseFloat(val);
        return (n >= 0 ? '+' : '') + '$' + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function fmtPct(val) {
        var n = parseFloat(val);
        return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
    }

    function fmtPrice(val) {
        return '$' + parseFloat(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    }

    function pnlClass(val) {
        return parseFloat(val) >= 0 ? 'positive' : 'negative';
    }

    // -----------------------------------------------------------------------
    // DOM update — dashboard page
    // -----------------------------------------------------------------------

    function applyPricesToDashboard(dashboard) {
        // Summary cards
        setText('dash-total-value', fmtMoney(dashboard.total_value));
        setText('dash-total-pnl', fmtMoneySign(dashboard.total_pnl));
        setText('dash-total-pnl-pct', fmtPct(dashboard.total_pnl_pct));
        setClass('dash-total-pnl', pnlClass(dashboard.total_pnl));
        setClass('dash-total-pnl-pct', pnlClass(dashboard.total_pnl_pct));

        // Holdings table rows
        (dashboard.all_holdings || []).forEach(function (h) {
            var row = document.querySelector(
                'tr[data-holding-account="' + h.account_id + '"][data-holding-symbol="' + h.asset_symbol + '"]'
            );
            if (!row) return;
            fillPriceCells(row, h);
        });

        // Per-account summary cards
        (dashboard.accounts || []).forEach(function (s) {
            var acctId = s.account.id;
            var el = document.querySelector('.account-summary-card[data-account-id="' + acctId + '"]');
            if (!el) return;
            var valueEl = el.querySelector('[data-acct-value]');
            var pnlEl = el.querySelector('[data-acct-pnl]');
            if (valueEl) valueEl.textContent = fmtMoney(s.total_value);
            if (pnlEl) {
                pnlEl.textContent = fmtMoneySign(s.total_pnl) + ' (' + fmtPct(s.total_pnl_pct) + ')';
                pnlEl.className = pnlClass(s.total_pnl);
            }
        });

        // Best / Worst
        updateBestWorst('best', dashboard.best_investment);
        updateBestWorst('worst', dashboard.worst_investment);

        markPricesLoaded();
    }

    // -----------------------------------------------------------------------
    // DOM update — account detail page
    // -----------------------------------------------------------------------

    function applyPricesToAccountDetail(dashboard, accountId) {
        var summary = null;
        for (var i = 0; i < (dashboard.accounts || []).length; i++) {
            if (dashboard.accounts[i].account.id === accountId) {
                summary = dashboard.accounts[i];
                break;
            }
        }
        if (!summary) return;

        // Summary cards
        setText('dash-total-value', fmtMoney(summary.total_value));
        setText('dash-total-pnl', fmtMoneySign(summary.total_pnl) + ' (' + fmtPct(summary.total_pnl_pct) + ')');
        setClass('dash-total-pnl', pnlClass(summary.total_pnl));

        // Holdings rows
        (summary.holdings || []).forEach(function (h) {
            var row = document.querySelector(
                'tr[data-holding-symbol="' + h.asset_symbol + '"]'
            );
            if (!row) return;
            fillPriceCells(row, h);
        });

        markPricesLoaded();
    }

    // -----------------------------------------------------------------------
    // Shared helpers
    // -----------------------------------------------------------------------

    function fillPriceCells(row, h) {
        var cells = row.querySelectorAll('[data-field]');
        cells.forEach(function (cell) {
            var field = cell.getAttribute('data-field');
            switch (field) {
                case 'current_price':
                    cell.textContent = h.current_price != null ? fmtPrice(h.current_price) : 'N/A';
                    cell.className = '';
                    break;
                case 'current_value':
                    cell.textContent = fmtMoney(h.current_value);
                    cell.className = '';
                    break;
                case 'unrealized_pnl':
                    cell.textContent = fmtMoneySign(h.unrealized_pnl);
                    cell.className = pnlClass(h.unrealized_pnl);
                    break;
                case 'unrealized_pnl_pct':
                    cell.textContent = fmtPct(h.unrealized_pnl_pct);
                    cell.className = pnlClass(h.unrealized_pnl_pct);
                    break;
                case 'weight':
                    cell.textContent = parseFloat(h.weight).toFixed(2) + '%';
                    cell.className = '';
                    break;
            }
        });
    }

    function updateBestWorst(type, investment) {
        var section = document.getElementById(type + '-investment-section');
        if (!section) return;
        if (!investment) {
            section.innerHTML = '<h3>' + (type === 'best' ? 'Best' : 'Worst') + ' Investment</h3><div class="bw-empty">No positions yet</div>';
            return;
        }
        section.innerHTML =
            '<h3>' + (type === 'best' ? 'Best' : 'Worst') + ' Investment</h3>' +
            '<div class="bw-symbol">' + (investment.asset_symbol || '').toUpperCase() + '</div>' +
            '<div class="bw-name">' + (investment.asset_name || '') + '</div>' +
            '<div class="bw-return ' + pnlClass(investment.unrealized_pnl_pct) + '">' +
                fmtPct(investment.unrealized_pnl_pct) + ' (' + fmtMoneySign(investment.unrealized_pnl) + ')' +
            '</div>';
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setClass(id, cls) {
        var el = document.getElementById(id);
        if (el) {
            el.classList.remove('positive', 'negative');
            el.classList.add(cls);
        }
    }

    function markPricesLoaded() {
        var bar = document.getElementById('price-status-bar');
        if (bar) {
            bar.textContent = 'Prices loaded';
            bar.className = 'price-status-ok';
        }
        document.querySelectorAll('.price-placeholder').forEach(function (el) {
            el.classList.remove('price-placeholder');
        });
    }

    function setLoadingState(loading) {
        var btn = document.getElementById('refreshPricesBtn');
        var bar = document.getElementById('price-status-bar');
        if (btn) {
            btn.disabled = loading;
            btn.textContent = loading ? '⏳ Loading…' : '🔄 Refresh / Recalculate';
        }
        if (bar && loading) {
            bar.textContent = 'Fetching live prices…';
            bar.className = 'price-status-loading';
        }
    }

    // -----------------------------------------------------------------------
    // Fetch and apply
    // -----------------------------------------------------------------------

    function fetchAndApply(applyFn) {
        setLoadingState(true);
        fetch('/api/dashboard_data')
            .then(function (res) { return res.json(); })
            .then(function (data) {
                setCachedData(data);
                applyFn(data);
                setLoadingState(false);
                // Reload the portfolio chart if available
                if (typeof window.loadPortfolioChart === 'function') {
                    window.loadPortfolioChart();
                }
            })
            .catch(function (err) {
                console.error('Price fetch error:', err);
                setLoadingState(false);
                var bar = document.getElementById('price-status-bar');
                if (bar) {
                    bar.textContent = 'Failed to load prices — click Refresh to retry';
                    bar.className = 'price-status-error';
                }
            });
    }

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------

    document.addEventListener('DOMContentLoaded', function () {
        var isDashboard = !!document.getElementById('dashboardPricesContainer');
        var accountDetailEl = document.querySelector('.page-header[data-account-id]');

        if (!isDashboard && !accountDetailEl) return;

        var applyFn = isDashboard
            ? applyPricesToDashboard
            : function (data) { applyPricesToAccountDetail(data, parseInt(accountDetailEl.dataset.accountId)); };

        // Read server-side last transaction timestamp embedded in the page
        var serverLastTxTs = document.querySelector('meta[name="last-tx-ts"]');
        serverLastTxTs = serverLastTxTs ? serverLastTxTs.getAttribute('content') : '';

        var cached = getCachedData(serverLastTxTs);
        if (cached) {
            applyFn(cached);
        } else {
            fetchAndApply(applyFn);
        }

        // Refresh / Recalculate button
        var refreshBtn = document.getElementById('refreshPricesBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function () {
                clearCache();
                fetchAndApply(applyFn);
            });
        }
    });

    // Expose for debugging
    window.PortfolioPrices = { clearCache: clearCache };
}());

