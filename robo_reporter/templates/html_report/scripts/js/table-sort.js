// Simple table sorting functionality

document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('.results-table');
    if (!table) return;

    const headers = table.querySelectorAll('th.sortable');
    
    headers.forEach(header => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            sortTable(this, table);
        });
    });
});

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
