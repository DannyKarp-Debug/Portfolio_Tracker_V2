/**
 * Portfolio Tracker — Sortable table columns.
 * Clicking a <th> with data-sort attribute sorts the table by that column.
 */

document.addEventListener('DOMContentLoaded', function () {
    var tables = document.querySelectorAll('table.sortable');

    tables.forEach(function (table) {
        var headers = table.querySelectorAll('th[data-sort]');

        headers.forEach(function (th, colIndex) {
            th.addEventListener('click', function () {
                var sortType = th.getAttribute('data-sort'); // 'string' or 'number'
                var tbody = table.querySelector('tbody');
                var rows = Array.from(tbody.querySelectorAll('tr'));
                var ascending = !th.classList.contains('sort-asc');

                // Remove sort indicators from all headers in this table
                headers.forEach(function (h) {
                    h.classList.remove('sort-asc', 'sort-desc');
                });

                th.classList.add(ascending ? 'sort-asc' : 'sort-desc');

                rows.sort(function (a, b) {
                    var aText = a.children[colIndex] ? a.children[colIndex].textContent.trim() : '';
                    var bText = b.children[colIndex] ? b.children[colIndex].textContent.trim() : '';

                    if (sortType === 'number') {
                        // Extract numeric value, stripping $, %, +, commas
                        var aNum = parseFloat(aText.replace(/[$,%+—\s]/g, '').replace(/,/g, '')) || 0;
                        var bNum = parseFloat(bText.replace(/[$,%+—\s]/g, '').replace(/,/g, '')) || 0;
                        return ascending ? aNum - bNum : bNum - aNum;
                    } else {
                        var cmp = aText.localeCompare(bText, undefined, { sensitivity: 'base' });
                        return ascending ? cmp : -cmp;
                    }
                });

                rows.forEach(function (row) {
                    tbody.appendChild(row);
                });
            });
        });
    });
});
