// ============================================================================
// Merged JavaScript: All charts, table sorting, filtering, and modal logic
// ============================================================================

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// Utility to lighten or darken a hex color
function shadeColor(color, percent) {
    let R = parseInt(color.substring(1,3),16);
    let G = parseInt(color.substring(3,5),16);
    let B = parseInt(color.substring(5,7),16);
    R = Math.min(255, Math.max(0, R + Math.round(255 * percent)));
    G = Math.min(255, Math.max(0, G + Math.round(255 * percent)));
    B = Math.min(255, Math.max(0, B + Math.round(255 * percent)));
    return `rgb(${R},${G},${B})`;
}

// Utility to add 3D shadow effect to Chart.js charts
function add3DEffect(ctx, chartType, baseColors) {
    // SOFTER 3D: use less intense highlight/shadow
    if (chartType === 'pie' || chartType === 'doughnut') {
        // Create radial gradient for each segment
        return baseColors.map((color, i) => {
            const grad = ctx.createRadialGradient(90, 90, 10, 90, 90, 90);
            grad.addColorStop(0, shadeColor(color, 0.15)); // softer highlight
            grad.addColorStop(0.6, color); // base
            grad.addColorStop(1, shadeColor(color, -0.15)); // softer shadow
            return grad;
        });
    } else if (chartType === 'bar') {
        // Create vertical gradient for bars
        return baseColors.map((color, i) => {
            const grad = ctx.createLinearGradient(0, 0, 0, 300);
            grad.addColorStop(0, shadeColor(color, 0.15)); // softer highlight
            grad.addColorStop(0.5, color); // base
            grad.addColorStop(1, shadeColor(color, -0.15)); // softer shadow
            return grad;
        });
    }
    return baseColors;
}

// ============================================================================
// TABLE SORTING AND FILTERING FUNCTIONS
// ============================================================================

function sortTable(header, table) {
    const columnType = header.getAttribute('data-column-type');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Determine column index
    let columnIndex = 0;
    const headers = table.querySelectorAll('th');
    headers.forEach((h, index) => {
        if (h === header) {
            columnIndex = index;
        }
    });
    
    // Toggle sort direction
    const isAscending = !header.classList.contains('sort-asc');
    
    // Remove sort indicators from all headers
    headers.forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
    });
    
    // Add sort indicator to current header
    if (isAscending) {
        header.classList.add('sort-asc');
    } else {
        header.classList.add('sort-desc');
    }
    
    // Sort rows (but don't sort by the # column itself)
    if (columnIndex !== 0) {
        rows.sort((a, b) => {
            let aValue = a.cells[columnIndex].textContent.trim();
            let bValue = b.cells[columnIndex].textContent.trim();
            
            // Try to parse as number
            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return isAscending ? aNum - bNum : bNum - aNum;
            }
            
            // String comparison
            return isAscending 
                ? aValue.localeCompare(bValue) 
                : bValue.localeCompare(aValue);
        });
    }
    
    // Re-append sorted rows
    rows.forEach(row => {
        tbody.appendChild(row);
    });
    
    // Reindex all rows after sorting
    console.log('Reindexing after sort, total rows:', rows.length);
    rows.forEach((row, index) => {
        if (row.cells && row.cells[0]) {
            const oldValue = row.cells[0].textContent;
            const newValue = index + 1;
            row.cells[0].textContent = newValue;
            console.log(`Row ${index}: Changed # from "${oldValue}" to "${newValue}"`);
        }
    });
    console.log('Reindexing complete');
}

// Reindex the row numbers based on visible rows
function reindexVisibleRows(table) {
    console.log('reindexVisibleRows called');
    if (!table) {
        console.log('No table provided');
        return;
    }
    
    const tbody = table.querySelector('tbody');
    if (!tbody) {
        console.log('No tbody found');
        return;
    }
    
    const rows = tbody.querySelectorAll('tr');
    console.log('Total rows found:', rows.length);
    let visibleIndex = 1;
    
    rows.forEach((row, i) => {
        // Check if row is visible (display is not 'none')
        const computedStyle = window.getComputedStyle(row);
        const isVisible = computedStyle.display !== 'none';
        
        console.log(`Row ${i}: display=${computedStyle.display}, isVisible=${isVisible}`);
        
        if (isVisible && row.cells && row.cells[0]) {
            const oldValue = row.cells[0].textContent;
            row.cells[0].textContent = visibleIndex;
            console.log(`Row ${i}: Changed # from "${oldValue}" to "${visibleIndex}"`);
            visibleIndex++;
        }
    });
    console.log('reindexVisibleRows complete, final visibleIndex:', visibleIndex);
}

// Filter table based on status checkboxes and search input
function setupTableFilters() {
    const statusFilters = document.querySelectorAll('.status-filter');
    const searchInput = document.getElementById('resultsTableFilter');
    const table = document.getElementById('resultsTable');
    
    if (!table || statusFilters.length === 0) return;
    
    function filterTable() {
        console.log('filterTable called');
        const selectedStatuses = Array.from(statusFilters)
            .filter(f => f.checked)
            .map(f => f.value.toUpperCase());
        
        console.log('Selected statuses:', selectedStatuses);
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        console.log('Search term:', searchTerm);
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach((row, index) => {
            const statusCell = row.cells[1];
            if (!statusCell) return;
            
            const status = statusCell.textContent.trim().toUpperCase();
            
            // Only show rows that match CHECKED statuses (if any are checked)
            // If no statuses are checked, hide all rows
            const matchesStatus = selectedStatuses.length > 0 && selectedStatuses.includes(status);
            
            // Check if row text matches search term
            const rowText = Array.from(row.cells).map(c => c.textContent.toLowerCase()).join(' ');
            const matchesSearch = searchTerm === '' || rowText.includes(searchTerm);
            
            const shouldShow = matchesStatus && matchesSearch;
            row.style.display = shouldShow ? '' : 'none';
        });
        
        // Reindex visible rows after filtering
        reindexVisibleRows(table);
    }
    
    // Attach change listeners to checkboxes
    statusFilters.forEach(filter => {
        filter.addEventListener('change', filterTable);
    });
    
    // Attach input listener to search box
    if (searchInput) {
        searchInput.addEventListener('input', filterTable);
    }
    
    // Apply filter on initial load
    filterTable();
}

// ============================================================================
// ERROR MODAL FUNCTIONS
// ============================================================================

window.showErrorDetails = function(row) {
    document.querySelectorAll('.results-table tr.selected').forEach(tr => tr.classList.remove('selected'));
    row.classList.add('selected');
    const testName = row.getAttribute('data-test-name') || 'Unknown Test';
    const outcome = row.getAttribute('data-outcome') || 'Unknown';
    const error = row.getAttribute('data-error') || 'No error details available';
    document.getElementById('errorModalTitle').textContent = `${testName} - ${outcome.toUpperCase()}`;
    document.getElementById('errorMessage').textContent = error;
    document.getElementById('errorModal').style.display = 'block';
    document.getElementById('expandIcon').style.display = '';
    document.getElementById('minimizeIcon').style.display = 'none';
};

window.closeErrorModal = function() {
    document.getElementById('errorModal').style.display = 'none';
    document.getElementById('errorModalContent').classList.remove('fullscreen');
    document.querySelectorAll('.results-table tr.selected').forEach(tr => tr.classList.remove('selected'));
};

window.toggleFullscreen = function() {
    const modalContent = document.getElementById('errorModalContent');
    const expandIcon = document.getElementById('expandIcon');
    const minimizeIcon = document.getElementById('minimizeIcon');
    const isFullscreen = modalContent.classList.toggle('fullscreen');
    if (isFullscreen) {
        expandIcon.style.display = 'none';
        minimizeIcon.style.display = '';
    } else {
        expandIcon.style.display = '';
        minimizeIcon.style.display = 'none';
    }
};

window.onclick = function(event) {
    const modal = document.getElementById('errorModal');
    if (event.target === modal) {
        window.closeErrorModal();
    }
};

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('errorModal');
        if (modal && modal.style.display === 'block') {
            window.closeErrorModal();
        }
    }
});

// ============================================================================
// CHART INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    // Data setup
    const allResults = window.allResultsData || [];
    
    // Material Design color palette
    const statusTypes = ['PASSED', 'FAILED', 'SKIPPED'];
    const statusColors = {
        'PASSED': '#43a047',   // Material Green 600
        'FAILED': '#e53935',   // Material Red 600
        'SKIPPED': '#fbc02d'   // Material Yellow 700
    };
    
    // Material palette for center/doughnut charts (no green, yellow, or red)
    const centerPalette = [
        '#1e88e5', // Blue 600
        '#8e24aa', // Purple 600
        '#00acc1', // Cyan 600
        '#fb8c00', // Orange 600
        '#6d4c41', // Brown 600
        '#3949ab', // Indigo 600
        '#c0ca33'  // Lime 600
    ];
    
    // Export globals for component modules
    window.statusColors = statusColors;
    window.centerPalette = centerPalette;
    window.statusTypes = statusTypes;
    
    // 1. Results Summary (Pie)
    (function() {
        const ctx = document.getElementById('summaryChart');
        if (!ctx) {
            console.warn('Summary chart container not found');
            return;
        }
        const baseColors = [statusColors['PASSED'], statusColors['FAILED'], statusColors['SKIPPED']];
        new Chart(ctx.getContext('2d'), {
            type: 'pie',
            data: {
                labels: ['Passed', 'Failed', 'Skipped'],
                datasets: [{
                    data: window.summaryData || [0,0,0],
                    backgroundColor: add3DEffect(ctx.getContext('2d'), 'pie', baseColors),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        align: 'center',
                        labels: {
                            font: { size: 14 },
                            usePointStyle: true,
                            pointStyle: 'rect',
                            generateLabels: function(chart) {
                                const data = chart.data;
                                return data.labels.map((label, i) => {
                                    return {
                                        text: label,
                                        fillStyle: baseColors[i],
                                        strokeStyle: baseColors[i],
                                        lineWidth: 1,
                                        hidden: false,
                                        index: i
                                    };
                                });
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Results Summary',
                        font: { size: 18 }
                    }
                }
            }
        });
    })();
    
    // 2. Distribution by Center (Doughnut)
    const centerCounts = {};
    allResults.forEach(r => {
        if (r.center && r.center !== '-') {
            centerCounts[r.center] = (centerCounts[r.center] || 0) + 1;
        }
    });
    const centerLabels = Object.keys(centerCounts);
    const centerData = Object.values(centerCounts);
    (function() {
        const ctx = document.getElementById('centerChart');
        if (!ctx) {
            console.warn('Center chart container not found');
            return;
        }
        // Always use centerPalette (no status-like colors) for center colors and legend
        const centerColors = centerLabels.map((_, i) => centerPalette[i % centerPalette.length]);
        new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: centerLabels,
                datasets: [{
                    data: centerData,
                    backgroundColor: add3DEffect(ctx.getContext('2d'), 'doughnut', centerColors),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        align: 'center',
                        labels: {
                            font: { size: 14 },
                            usePointStyle: true,
                            pointStyle: 'rect',
                            generateLabels: function(chart) {
                                // Always use centerPalette for legend colors
                                return chart.data.labels.map((label, i) => {
                                    const color = centerPalette[i % centerPalette.length];
                                    return {
                                        text: label,
                                        fillStyle: color,
                                        strokeStyle: color,
                                        lineWidth: 1,
                                        hidden: false,
                                        index: i
                                    };
                                });
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Distribution by Center',
                        font: { size: 18 }
                    }
                }
            }
        });
    })();
    
    // Setup table sorting event listeners
    const table = document.querySelector('.results-table');
    if (table) {
        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                sortTable(this, table);
            });
        });
    }
    
    // Attach click event to table rows for error popup
    var resultsTable = document.getElementById('resultsTable');
    if (resultsTable) {
        resultsTable.querySelectorAll('tbody tr').forEach(function(row) {
            row.addEventListener('click', function() {
                showErrorDetails(row);
            });
        });
    }
});

// Set up filters when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupTableFilters);
} else {
    setupTableFilters();
}

// Ensure reindexing happens after page fully loads and filters are applied
window.addEventListener('load', function() {
    const table = document.getElementById('resultsTable');
    if (table) {
        // Delay to ensure filters have been applied
        setTimeout(function() {
            reindexVisibleRows(table);
        }, 200);
    }
});
