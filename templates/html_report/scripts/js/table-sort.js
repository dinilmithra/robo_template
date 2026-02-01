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
    
    // Sort rows
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
    
    // Re-append sorted rows
    rows.forEach(row => {
        tbody.appendChild(row);
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
