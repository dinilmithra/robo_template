// All charts and modal logic for the pytest HTML report

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
        const ctx = document.getElementById('centerChart').getContext('2d');
        // Always use centerPalette (no status-like colors) for center colors and legend
        const centerColors = centerLabels.map((_, i) => centerPalette[i % centerPalette.length]);
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: centerLabels,
                datasets: [{
                    data: centerData,
                    backgroundColor: add3DEffect(ctx, 'doughnut', centerColors),
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
    // Bar charts (Phase, Category, Center) are now initialized from their component modules

    // Error modal logic
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
    // Attach click event to table rows for error popup
    var table = document.getElementById('resultsTable');
    if (table) {
        table.querySelectorAll('tbody tr').forEach(function(row) {
            row.addEventListener('click', function() {
                showErrorDetails(row);
            });
        });
    }
});
