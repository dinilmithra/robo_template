// ============================================================================
// Merged JavaScript: Table sorting, filtering, and modal logic
// ============================================================================

// ============================================================================
// UTILITY FUNCTIONS FOR CHARTS
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
    if (chartType === 'pie' || chartType === 'doughnut') {
        return baseColors.map((color, i) => {
            const grad = ctx.createRadialGradient(90, 90, 10, 90, 90, 90);
            grad.addColorStop(0, shadeColor(color, 0.15));
            grad.addColorStop(0.6, color);
            grad.addColorStop(1, shadeColor(color, -0.15));
            return grad;
        });
    } else if (chartType === 'bar') {
        return baseColors.map((color, i) => {
            const grad = ctx.createLinearGradient(0, 0, 0, 300);
            grad.addColorStop(0, shadeColor(color, 0.15));
            grad.addColorStop(0.5, color);
            grad.addColorStop(1, shadeColor(color, -0.15));
            return grad;
        });
    }
    return baseColors;
}

// Material Design color palette
const statusTypes = ['PASSED', 'FAILED', 'SKIPPED'];
const statusColors = {
    'PASSED': '#43a047',   // Material Green 600
    'FAILED': '#e53935',   // Material Red 600
    'SKIPPED': '#fbc02d'   // Material Yellow 700
};

// Material palette for center/doughnut charts
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
window.shadeColor = shadeColor;
window.add3DEffect = add3DEffect;
window.statusColors = statusColors;
window.centerPalette = centerPalette;
window.statusTypes = statusTypes;

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
    const isAscending = !header.classList.contains('sorted-asc');
    
    // Remove sort indicators from all headers
    headers.forEach(h => {
        h.classList.remove('sorted-asc', 'sorted-desc');
    });
    
    // Add sort indicator to current header
    if (isAscending) {
        header.classList.add('sorted-asc');
    } else {
        header.classList.add('sorted-desc');
    }
    
    // Sort rows (but don't sort by the # column itself)
    if (columnIndex !== 0) {
        rows.sort((a, b) => {
            const cellA = a.cells[columnIndex];
            const cellB = b.cells[columnIndex];
            
            // Check for data-value attribute (used for numeric columns like duration)
            let aValue = cellA.getAttribute('data-value') || cellA.textContent.trim();
            let bValue = cellB.getAttribute('data-value') || cellB.textContent.trim();
            
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
    rows.forEach((row, index) => {
        if (row.cells && row.cells[0]) {
            const oldValue = row.cells[0].textContent;
            const newValue = index + 1;
            row.cells[0].textContent = newValue;
        }
    });
}

// Reindex the row numbers based on visible rows
function reindexVisibleRows(table) {
    if (!table) {
        return;
    }
    
    const tbody = table.querySelector('tbody');
    if (!tbody) {
        return;
    }
    
    const rows = tbody.querySelectorAll('tr');
    let visibleIndex = 1;
    
    rows.forEach((row, i) => {
        // Check if row is visible (display is not 'none')
        const computedStyle = window.getComputedStyle(row);
        const isVisible = computedStyle.display !== 'none';
        
        if (isVisible && row.cells && row.cells[0]) {
            const oldValue = row.cells[0].textContent;
            row.cells[0].textContent = visibleIndex;
            visibleIndex++;
        }
    });
}

// Filter table based on status checkboxes and search input
function setupTableFilters() {
    const statusFilters = document.querySelectorAll('.status-filter');
    const searchInput = document.getElementById('resultsTableFilter');
    const table = document.getElementById('resultsTable');
    
    if (!table || statusFilters.length === 0) return;
    
    function filterTable() {
        const selectedStatuses = Array.from(statusFilters)
            .filter(f => f.checked)
            .map(f => f.value.toUpperCase());
        
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
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
// CHART INITIALIZATION (components handle chart rendering now)
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
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
        
        // Default sort by test_case_name (2nd sortable column)
        const testCaseNameHeader = table.querySelector('th.test_case_name');
        if (testCaseNameHeader) {
            sortTable(testCaseNameHeader, table);
        }
    }
    
    // Setup table filters
    setupTableFilters();
    
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
