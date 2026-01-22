// Dashboard JavaScript
const API_BASE = '/api';

// State
let currentLogsPage = 0;
let currentUsersPage = 0;
let logsFilters = {};
let logsSort = { by: 'timestamp', order: 'desc' };
let usersSort = { by: 'last_name', order: 'asc' };
let charts = {};
let chartData = {}; // Store chart data for click handling
let filterOptions = { event_types: [], credential_types: [], door_names: [] };
let dashboardDateRange = { days: 30, start: null, end: null };

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initNavigation();
    initMobileMenu();
    initSyncButton();
    initStatCards();
    initFilters();
    initModal();
    initTableSorting();
    initDashboardDateFilter();
    loadDashboard();
    loadFilterOptions();
});

// Mobile Menu
function initMobileMenu() {
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const mobileSyncBtn = document.getElementById('mobile-sync-btn');
    
    // Toggle sidebar
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
    });
    
    // Close sidebar when clicking overlay
    overlay.addEventListener('click', () => {
        closeMobileMenu();
    });
    
    // Close sidebar when clicking a nav item (on mobile)
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                closeMobileMenu();
            }
        });
    });
    
    // Mobile sync button
    mobileSyncBtn.addEventListener('click', triggerSync);
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Navigation
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            showView(view);
            
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function showView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');
    
    // Load view data
    switch(viewName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'logs':
            loadAccessLogs();
            break;
        case 'users':
            loadUsers();
            break;
        case 'doors':
            loadDoors();
            break;
    }
    
    // Re-initialize icons for new content
    setTimeout(() => lucide.createIcons(), 100);
}

// Clickable Stat Cards
function initStatCards() {
    document.querySelectorAll('.stat-card.clickable').forEach(card => {
        card.addEventListener('click', () => {
            const filter = card.dataset.filter;
            handleStatCardClick(filter);
        });
    });
}

function handleStatCardClick(filter) {
    // Navigate to logs view with appropriate filter
    let dateRangeValue = '';
    
    switch(filter) {
        case 'today':
            dateRangeValue = 'today';
            break;
        case 'week':
            dateRangeValue = 'last7';
            break;
        case 'month':
            dateRangeValue = 'thisMonth';
            break;
        case 'active-users':
            // Navigate to users view
            document.querySelector('.nav-item[data-view="users"]').click();
            return;
    }
    
    if (dateRangeValue) {
        document.getElementById('filter-date-range').value = dateRangeValue;
        document.getElementById('custom-date-range').classList.add('hidden');
        const { start, end } = getDateRange(dateRangeValue);
        logsFilters.start_date = start;
        logsFilters.end_date = end;
        currentLogsPage = 0;
    }
    
    document.querySelector('.nav-item[data-view="logs"]').click();
}

// Sync Button
function initSyncButton() {
    const syncBtn = document.getElementById('sync-btn');
    syncBtn.addEventListener('click', triggerSync);
    updateSyncStatus();
}

async function triggerSync() {
    const syncBtn = document.getElementById('sync-btn');
    const mobileSyncBtn = document.getElementById('mobile-sync-btn');
    const statusText = document.getElementById('sync-status-text');
    const syncDot = document.querySelector('.sync-dot');
    
    syncBtn.disabled = true;
    syncBtn.classList.add('syncing');
    mobileSyncBtn.classList.add('syncing');
    mobileSyncBtn.disabled = true;
    syncDot.classList.add('syncing');
    statusText.textContent = 'Syncing...';
    
    try {
        const response = await fetch(`${API_BASE}/sync/trigger`, { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'started') {
            pollSyncStatus();
        }
    } catch (error) {
        console.error('Sync error:', error);
        statusText.textContent = 'Sync failed';
        syncBtn.disabled = false;
        syncBtn.classList.remove('syncing');
        mobileSyncBtn.classList.remove('syncing');
        mobileSyncBtn.disabled = false;
        syncDot.classList.remove('syncing');
    }
}

async function pollSyncStatus() {
    const syncBtn = document.getElementById('sync-btn');
    const mobileSyncBtn = document.getElementById('mobile-sync-btn');
    const statusText = document.getElementById('sync-status-text');
    const syncDot = document.querySelector('.sync-dot');
    
    const checkStatus = async () => {
        try {
            const response = await fetch(`${API_BASE}/sync/status`);
            const data = await response.json();
            
            if (data.sync_in_progress) {
                setTimeout(checkStatus, 2000);
            } else {
                syncBtn.disabled = false;
                syncBtn.classList.remove('syncing');
                mobileSyncBtn.classList.remove('syncing');
                mobileSyncBtn.disabled = false;
                syncDot.classList.remove('syncing');
                statusText.textContent = 'Sync complete';
                
                // Reload current view and filter options
                loadFilterOptions();
                const activeNav = document.querySelector('.nav-item.active');
                if (activeNav) {
                    showView(activeNav.dataset.view);
                }
                
                setTimeout(() => {
                    statusText.textContent = 'Ready';
                }, 3000);
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    };
    
    checkStatus();
}

async function updateSyncStatus() {
    try {
        const response = await fetch(`${API_BASE}/sync/status`);
        const data = await response.json();
        
        const statusText = document.getElementById('sync-status-text');
        if (data.sync_in_progress) {
            statusText.textContent = 'Syncing...';
        } else {
            statusText.textContent = 'Ready';
        }
    } catch (error) {
        console.error('Error fetching sync status:', error);
    }
}

// Load Filter Options
async function loadFilterOptions() {
    try {
        const response = await fetch(`${API_BASE}/access-logs/filters`);
        filterOptions = await response.json();
        
        // Populate door multi-select dropdown
        populateDoorMultiSelect(filterOptions.door_names);
            
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

// Multi-Select Dropdown for Doors
function populateDoorMultiSelect(doors) {
    const optionsContainer = document.getElementById('door-options');
    optionsContainer.innerHTML = doors.map(door => `
        <label class="multi-select-option">
            <input type="checkbox" value="${door}" class="door-checkbox">
            <span>${door}</span>
        </label>
    `).join('');
    
    // Initialize multi-select behavior
    initDoorMultiSelect();
}

function initDoorMultiSelect() {
    const dropdown = document.getElementById('door-dropdown');
    const trigger = document.getElementById('door-trigger');
    const menu = document.getElementById('door-menu');
    const selectAll = document.getElementById('door-select-all');
    const checkboxes = document.querySelectorAll('.door-checkbox');
    
    // Toggle dropdown
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('open');
    });
    
    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
    
    // Select All functionality
    selectAll.addEventListener('change', () => {
        checkboxes.forEach(cb => cb.checked = selectAll.checked);
        updateDoorSelection();
    });
    
    // Individual checkbox change
    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            // Update select all state
            const allChecked = Array.from(checkboxes).every(c => c.checked);
            const someChecked = Array.from(checkboxes).some(c => c.checked);
            selectAll.checked = allChecked;
            selectAll.indeterminate = someChecked && !allChecked;
            updateDoorSelection();
        });
    });
}

function updateDoorSelection() {
    const checkboxes = document.querySelectorAll('.door-checkbox:checked');
    const selected = Array.from(checkboxes).map(cb => cb.value);
    const textEl = document.querySelector('.multi-select-text');
    
    if (selected.length === 0) {
        textEl.textContent = 'All Doors';
        logsFilters.door_names = null;
    } else if (selected.length === 1) {
        textEl.textContent = selected[0];
        logsFilters.door_names = selected;
    } else if (selected.length <= 2) {
        textEl.textContent = selected.join(', ');
        logsFilters.door_names = selected;
    } else {
        textEl.textContent = `${selected.length} doors selected`;
        logsFilters.door_names = selected;
    }
    
    currentLogsPage = 0;
    loadAccessLogs();
}

function setDoorSelection(doorNames) {
    // Clear all first
    document.querySelectorAll('.door-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('door-select-all').checked = false;
    
    // Select specified doors
    if (doorNames && doorNames.length > 0) {
        doorNames.forEach(name => {
            const cb = document.querySelector(`.door-checkbox[value="${name}"]`);
            if (cb) cb.checked = true;
        });
    }
    
    // Update display
    const checkboxes = document.querySelectorAll('.door-checkbox:checked');
    const selected = Array.from(checkboxes).map(cb => cb.value);
    const textEl = document.querySelector('.multi-select-text');
    
    if (selected.length === 0) {
        textEl.textContent = 'All Doors';
    } else if (selected.length === 1) {
        textEl.textContent = selected[0];
    } else if (selected.length <= 2) {
        textEl.textContent = selected.join(', ');
    } else {
        textEl.textContent = `${selected.length} doors selected`;
    }
}

// Dashboard Date Filter
function initDashboardDateFilter() {
    const dateSelect = document.getElementById('dashboard-date-range');
    const customRange = document.getElementById('dashboard-custom-range');
    const applyBtn = document.getElementById('dashboard-apply-custom');
    
    dateSelect.addEventListener('change', (e) => {
        const value = e.target.value;
        
        if (value === 'custom') {
            customRange.classList.remove('hidden');
            return;
        }
        
        customRange.classList.add('hidden');
        applyDashboardDateRange(value);
    });
    
    applyBtn.addEventListener('click', () => {
        const start = document.getElementById('dashboard-start-date').value;
        const end = document.getElementById('dashboard-end-date').value;
        
        if (start && end) {
            dashboardDateRange = {
                days: null,
                start: new Date(start).toISOString(),
                end: new Date(end + 'T23:59:59').toISOString()
            };
            loadDashboard();
        }
    });
    
    // Initialize with default
    applyDashboardDateRange('last30');
}

function applyDashboardDateRange(rangeType) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    switch (rangeType) {
        case 'last7':
            dashboardDateRange = { days: 7, start: null, end: null };
            break;
        case 'last30':
            dashboardDateRange = { days: 30, start: null, end: null };
            break;
        case 'last90':
            dashboardDateRange = { days: 90, start: null, end: null };
            break;
        case 'thisMonth':
            const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
            dashboardDateRange = {
                days: null,
                start: monthStart.toISOString(),
                end: now.toISOString()
            };
            break;
        case 'lastMonth':
            const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59);
            dashboardDateRange = {
                days: null,
                start: lastMonthStart.toISOString(),
                end: lastMonthEnd.toISOString()
            };
            break;
        case 'thisYear':
            const yearStart = new Date(now.getFullYear(), 0, 1);
            dashboardDateRange = {
                days: null,
                start: yearStart.toISOString(),
                end: now.toISOString()
            };
            break;
        default:
            dashboardDateRange = { days: 30, start: null, end: null };
    }
    
    loadDashboard();
}

function getDashboardQueryParams() {
    const params = new URLSearchParams();
    if (dashboardDateRange.days) {
        params.append('days', dashboardDateRange.days);
    }
    if (dashboardDateRange.start) {
        params.append('start_date', dashboardDateRange.start);
    }
    if (dashboardDateRange.end) {
        params.append('end_date', dashboardDateRange.end);
    }
    return params.toString();
}

// Dashboard
async function loadDashboard() {
    await loadStats();
    await loadCharts();
}

async function loadStats() {
    try {
        const tzOffset = new Date().getTimezoneOffset();
        const response = await fetch(`${API_BASE}/stats?tz_offset=${tzOffset}`);
        const stats = await response.json();
        
        document.getElementById('stat-today').textContent = formatNumber(stats.today_accesses);
        document.getElementById('stat-week').textContent = formatNumber(stats.week_accesses);
        document.getElementById('stat-month').textContent = formatNumber(stats.month_accesses);
        document.getElementById('stat-active').textContent = formatNumber(stats.active_users_7d);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadCharts() {
    const queryParams = getDashboardQueryParams();
    const tzOffset = new Date().getTimezoneOffset();
    
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: 'rgba(48, 54, 61, 0.5)', drawBorder: false },
                ticks: { color: '#8b949e', font: { family: 'Outfit' } }
            },
            y: {
                grid: { color: 'rgba(48, 54, 61, 0.5)', drawBorder: false },
                ticks: { color: '#8b949e', font: { family: 'Outfit' } },
                beginAtZero: true
            }
        }
    };
    
    // Hourly chart - pass timezone offset so backend can convert UTC to local
    try {
        const hourlyData = await fetch(`${API_BASE}/charts/hourly?tz_offset=${tzOffset}&${queryParams}`).then(r => r.json());
        chartData.hourly = hourlyData;
        if (charts.hourly) charts.hourly.destroy();
        charts.hourly = new Chart(document.getElementById('chart-hourly'), {
            type: 'bar',
            data: {
                labels: hourlyData.labels.map(h => `${h}:00`),
                datasets: [{
                    data: hourlyData.data,
                    backgroundColor: 'rgba(57, 208, 216, 0.6)',
                    borderColor: 'rgba(57, 208, 216, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                ...chartDefaults,
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        // Navigate to logs - hourly doesn't have a specific filter, just go to logs
                        document.querySelector('.nav-item[data-view="logs"]').click();
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } catch (e) { console.error('Hourly chart error:', e); }
    
    // Weekday chart
    try {
        const weekdayData = await fetch(`${API_BASE}/charts/weekday?tz_offset=${tzOffset}&${queryParams}`).then(r => r.json());
        chartData.weekday = weekdayData;
        if (charts.weekday) charts.weekday.destroy();
        charts.weekday = new Chart(document.getElementById('chart-weekday'), {
            type: 'bar',
            data: {
                labels: weekdayData.labels,
                datasets: [{
                    data: weekdayData.data,
                    backgroundColor: [
                        'rgba(163, 113, 247, 0.6)',
                        'rgba(88, 166, 255, 0.6)',
                        'rgba(88, 166, 255, 0.6)',
                        'rgba(88, 166, 255, 0.6)',
                        'rgba(88, 166, 255, 0.6)',
                        'rgba(63, 185, 80, 0.6)',
                        'rgba(163, 113, 247, 0.6)'
                    ],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartDefaults,
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const dayIndex = elements[0].index;
                        navigateToLogsForWeekday(dayIndex);
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } catch (e) { console.error('Weekday chart error:', e); }
    
    // Daily trend chart
    try {
        const dailyData = await fetch(`${API_BASE}/charts/daily?tz_offset=${tzOffset}&${queryParams}`).then(r => r.json());
        chartData.daily = dailyData;
        if (charts.daily) charts.daily.destroy();
        charts.daily = new Chart(document.getElementById('chart-daily'), {
            type: 'line',
            data: {
                labels: dailyData.labels.map(d => formatDateShort(d)),
                datasets: [{
                    data: dailyData.data,
                    borderColor: 'rgba(57, 208, 216, 1)',
                    backgroundColor: 'rgba(57, 208, 216, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: {
                ...chartDefaults,
                scales: {
                    ...chartDefaults.scales,
                    x: { ...chartDefaults.scales.x, ticks: { ...chartDefaults.scales.x.ticks, maxTicksLimit: 10 } }
                },
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const date = chartData.daily.labels[index];
                        navigateToLogsForDate(date);
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } catch (e) { console.error('Daily chart error:', e); }
    
    // Top doors chart
    try {
        const doorsData = await fetch(`${API_BASE}/charts/by-door?${queryParams}`).then(r => r.json());
        chartData.doors = doorsData;
        if (charts.doors) charts.doors.destroy();
        charts.doors = new Chart(document.getElementById('chart-doors'), {
            type: 'doughnut',
            data: {
                labels: doorsData.labels,
                datasets: [{
                    data: doorsData.data,
                    backgroundColor: [
                        'rgba(57, 208, 216, 0.8)',
                        'rgba(88, 166, 255, 0.8)',
                        'rgba(163, 113, 247, 0.8)',
                        'rgba(63, 185, 80, 0.8)',
                        'rgba(210, 153, 34, 0.8)'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#8b949e', font: { family: 'Outfit', size: 11 }, boxWidth: 12, padding: 8 },
                        onClick: (e, legendItem, legend) => {
                            // Navigate to logs for this door when clicking legend
                            const doorName = chartData.doors.labels[legendItem.index];
                            navigateToLogsForDoor(doorName);
                        }
                    }
                },
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const doorName = chartData.doors.labels[index];
                        navigateToLogsForDoor(doorName);
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } catch (e) { console.error('Doors chart error:', e); }
    
    // Top users chart
    try {
        const usersData = await fetch(`${API_BASE}/charts/by-user?${queryParams}`).then(r => r.json());
        chartData.users = usersData;
        if (charts.users) charts.users.destroy();
        
        // Truncate names for display
        const truncatedNames = usersData.labels.map(n => {
            const parts = n.split(' ');
            return parts.length > 1 ? `${parts[0]} ${parts[1]?.[0] || ''}.` : n;
        });
        
        charts.users = new Chart(document.getElementById('chart-users'), {
            type: 'bar',
            data: {
                labels: truncatedNames,
                datasets: [{
                    data: usersData.data,
                    backgroundColor: 'rgba(163, 113, 247, 0.6)',
                    borderColor: 'rgba(163, 113, 247, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(48, 54, 61, 0.5)', drawBorder: false },
                        ticks: { 
                            color: '#8b949e', 
                            font: { family: 'Outfit' },
                            stepSize: 1,
                            precision: 0
                        },
                        beginAtZero: true
                    },
                    y: {
                        grid: { display: false },
                        ticks: { 
                            color: '#8b949e', 
                            font: { family: 'Outfit', size: 11 }
                        }
                    }
                },
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const userName = chartData.users.labels[index];
                        navigateToLogsForUser(userName);
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    } catch (e) { console.error('Users chart error:', e); }
}

// Chart click navigation helpers
function navigateToLogsForDoor(doorName) {
    logsFilters = { door_names: [doorName] };
    setDoorSelection([doorName]);
    currentLogsPage = 0;
    document.querySelector('.nav-item[data-view="logs"]').click();
}

function navigateToLogsForUser(userName) {
    logsFilters = { search: userName };
    document.getElementById('search-logs').value = userName;
    currentLogsPage = 0;
    document.querySelector('.nav-item[data-view="logs"]').click();
}

function navigateToLogsForDate(dateStr) {
    // Parse as local date to avoid timezone shift
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day); // Local midnight
    const nextDay = new Date(year, month - 1, day + 1); // Next day local midnight
    
    logsFilters = {
        start_date: date.toISOString(),
        end_date: nextDay.toISOString()
    };
    
    // Set custom date range in filter
    document.getElementById('filter-date-range').value = 'custom';
    document.getElementById('custom-date-range').classList.remove('hidden');
    document.getElementById('filter-start-date').value = dateStr;
    document.getElementById('filter-end-date').value = dateStr;
    
    currentLogsPage = 0;
    document.querySelector('.nav-item[data-view="logs"]').click();
}

function navigateToLogsForWeekday(dayIndex) {
    // dayIndex: 0=Sunday, 1=Monday, etc.
    // Find the most recent occurrence of this weekday (including today)
    const today = new Date();
    const currentDay = today.getDay();
    let daysBack = currentDay - dayIndex;
    if (daysBack < 0) daysBack += 7;
    // If today is the same day, daysBack will be 0, which is correct (show today)
    
    const targetDate = new Date(today);
    targetDate.setDate(today.getDate() - daysBack);
    
    const dateStr = targetDate.toISOString().split('T')[0];
    navigateToLogsForDate(dateStr);
}

// Filters
function initFilters() {
    // Access logs filters
    document.getElementById('search-logs').addEventListener('input', debounce(() => {
        logsFilters.search = document.getElementById('search-logs').value;
        currentLogsPage = 0;
        loadAccessLogs();
    }, 300));
    
    // Door multi-select is handled by initDoorMultiSelect()
    
    // Date range dropdown
    document.getElementById('filter-date-range').addEventListener('change', (e) => {
        const value = e.target.value;
        const customRange = document.getElementById('custom-date-range');
        
        if (value === 'custom') {
            customRange.classList.remove('hidden');
            return; // Don't apply filter yet, wait for custom dates
        } else {
            customRange.classList.add('hidden');
        }
        
        const { start, end } = getDateRange(value);
        logsFilters.start_date = start;
        logsFilters.end_date = end;
        currentLogsPage = 0;
        loadAccessLogs();
    });
    
    document.getElementById('filter-start-date').addEventListener('change', () => {
        applyCustomDateRange();
    });
    
    document.getElementById('filter-end-date').addEventListener('change', () => {
        applyCustomDateRange();
    });
    
    document.getElementById('clear-filters').addEventListener('click', () => {
        document.getElementById('search-logs').value = '';
        document.getElementById('filter-date-range').value = '';
        document.getElementById('custom-date-range').classList.add('hidden');
        // Clear door multi-select
        document.querySelectorAll('.door-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('door-select-all').checked = false;
        document.querySelector('.multi-select-text').textContent = 'All Doors';
        document.getElementById('filter-start-date').value = '';
        document.getElementById('filter-end-date').value = '';
        logsFilters = {};
        currentLogsPage = 0;
        loadAccessLogs();
    });
    
    document.getElementById('export-csv').addEventListener('click', exportLogsCSV);
    
    // Users filters
    document.getElementById('search-users').addEventListener('input', debounce(() => {
        currentUsersPage = 0;
        loadUsers();
    }, 300));
    
    document.getElementById('filter-user-status').addEventListener('change', () => {
        currentUsersPage = 0;
        loadUsers();
    });
    
    // Doors search
    document.getElementById('search-doors').addEventListener('input', debounce(() => {
        loadDoors();
    }, 300));
}

// Table Sorting
function initTableSorting() {
    // Logs table sorting
    document.querySelectorAll('#logs-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const sortBy = th.dataset.sort;
            if (logsSort.by === sortBy) {
                logsSort.order = logsSort.order === 'asc' ? 'desc' : 'asc';
            } else {
                logsSort.by = sortBy;
                logsSort.order = 'desc';
            }
            updateSortIndicators('logs-table', logsSort);
            loadAccessLogs();
        });
    });
    
    // Users table sorting
    document.querySelectorAll('#users-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const sortBy = th.dataset.sort;
            if (usersSort.by === sortBy) {
                usersSort.order = usersSort.order === 'asc' ? 'desc' : 'asc';
            } else {
                usersSort.by = sortBy;
                usersSort.order = 'asc';
            }
            updateSortIndicators('users-table', usersSort);
            loadUsers();
        });
    });
}

function updateSortIndicators(tableId, sortState) {
    document.querySelectorAll(`#${tableId} th.sortable`).forEach(th => {
        th.classList.remove('active');
        if (th.dataset.sort === sortState.by) {
            th.classList.add('active');
        }
    });
}

// Access Logs
async function loadAccessLogs() {
    const tbody = document.getElementById('logs-tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';
    
    try {
        const params = new URLSearchParams({
            limit: 50,
            offset: currentLogsPage * 50,
            sort_by: logsSort.by,
            sort_order: logsSort.order
        });
        
        // Add filters
        Object.entries(logsFilters).forEach(([key, value]) => {
            if (value) {
                if (key === 'door_names' && Array.isArray(value)) {
                    value.forEach(v => params.append('door_name', v));
                } else {
                    params.append(key, value);
                }
            }
        });
        
        const response = await fetch(`${API_BASE}/access-logs?${params}`);
        const data = await response.json();
        
        if (data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading">No access logs found</td></tr>';
        } else {
            tbody.innerHTML = data.data.map(log => `
                <tr onclick="handleLogClick('${log.user?.id || ''}', '${log.user?.name || ''}')">
                    <td>${formatLocalDateTime(log.timestamp)}</td>
                    <td><strong>${log.user?.name || 'Unknown'}</strong></td>
                    <td>${log.door?.name || 'Unknown'}</td>
                    <td><span class="badge ${(log.event_type || '').toLowerCase().replace(' ', '-')}">${log.event_type || '-'}</span></td>
                    <td><span class="badge ${log.credential_type || ''}">${log.credential_type || '-'}</span></td>
                </tr>
            `).join('');
        }
        
        renderPagination('logs-pagination', data.total, 50, currentLogsPage, (page) => {
            currentLogsPage = page;
            loadAccessLogs();
        });
        
    } catch (error) {
        console.error('Error loading access logs:', error);
        tbody.innerHTML = '<tr><td colspan="5" class="loading">Error loading data</td></tr>';
    }
}

function handleLogClick(userId, userName) {
    if (userId) {
        showUserDetail(userId);
    }
}

async function exportLogsCSV() {
    try {
        const params = new URLSearchParams({ limit: 10000 });
        Object.entries(logsFilters).forEach(([key, value]) => {
            if (value) params.append(key, value);
        });
        
        const response = await fetch(`${API_BASE}/access-logs?${params}`);
        const data = await response.json();
        
        const csv = [
            ['Time (Local)', 'User', 'Email', 'Door', 'Event', 'Credential'],
            ...data.data.map(log => [
                formatLocalDateTime(log.timestamp),
                log.user?.name || 'Unknown',
                log.user?.email || '',
                log.door?.name || 'Unknown',
                log.event_type || '',
                log.credential_type || ''
            ])
        ].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `access_logs_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error exporting CSV:', error);
    }
}

// Users
async function loadUsers() {
    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = '<tr><td colspan="4" class="loading">Loading...</td></tr>';
    
    const search = document.getElementById('search-users').value;
    const status = document.getElementById('filter-user-status').value;
    
    try {
        const params = new URLSearchParams({
            limit: 50,
            offset: currentUsersPage * 50,
            sort_by: usersSort.by,
            sort_order: usersSort.order
        });
        
        if (search) params.append('search', search);
        if (status) params.append('status', status);
        
        const response = await fetch(`${API_BASE}/users?${params}`);
        const data = await response.json();
        
        if (data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading">No users found</td></tr>';
        } else {
            tbody.innerHTML = data.data.map(user => `
                <tr onclick="showUserDetail('${user.id}')">
                    <td><strong>${user.name}</strong></td>
                    <td>${user.email || '-'}</td>
                    <td><span class="badge ${user.status || 'active'}">${user.status || 'Active'}</span></td>
                    <td>${formatNumber(user.access_count)}</td>
                </tr>
            `).join('');
        }
        
        renderPagination('users-pagination', data.total, 50, currentUsersPage, (page) => {
            currentUsersPage = page;
            loadUsers();
        });
        
    } catch (error) {
        console.error('Error loading users:', error);
        tbody.innerHTML = '<tr><td colspan="4" class="loading">Error loading data</td></tr>';
    }
}

// Doors
async function loadDoors() {
    const grid = document.getElementById('doors-grid');
    grid.innerHTML = '<div class="loading">Loading doors...</div>';
    
    const search = document.getElementById('search-doors')?.value || '';
    
    try {
        const params = new URLSearchParams({ limit: 100 });
        if (search) params.append('search', search);
        
        const response = await fetch(`${API_BASE}/doors?${params}`);
        const data = await response.json();
        
        if (data.data.length === 0) {
            grid.innerHTML = '<div class="loading">No doors found. Try syncing data first.</div>';
        } else {
            grid.innerHTML = data.data.map(door => `
                <div class="door-card" onclick="showDoorLogs('${encodeURIComponent(door.name)}')">
                    <h4>
                        <span class="door-icon"><i data-lucide="door-open"></i></span>
                        ${door.name}
                    </h4>
                    <p class="last-access">Last access: ${door.last_access ? formatLocalDateTime(door.last_access) : 'Never'}</p>
                    <div class="door-stats">
                        <div class="door-stat">
                            <span class="door-stat-value">${formatNumber(door.total_accesses)}</span>
                            <span class="door-stat-label">Total Accesses</span>
                        </div>
                    </div>
                </div>
            `).join('');
            
            lucide.createIcons();
        }
    } catch (error) {
        console.error('Error loading doors:', error);
        grid.innerHTML = '<div class="loading">Error loading doors</div>';
    }
}

function showDoorLogs(doorName) {
    // Set door filter and navigate to logs
    const decodedName = decodeURIComponent(doorName);
    
    // Use the new multi-select
    logsFilters.door_names = [decodedName];
    setDoorSelection([decodedName]);
    currentLogsPage = 0;
    document.querySelector('.nav-item[data-view="logs"]').click();
}

// Modal
function initModal() {
    const modal = document.getElementById('user-modal');
    const closeBtn = modal.querySelector('.modal-close');
    
    closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });
}

async function showUserDetail(userId) {
    const modal = document.getElementById('user-modal');
    const content = document.getElementById('user-detail-content');
    
    content.innerHTML = '<div class="loading">Loading user details...</div>';
    modal.classList.add('active');
    
    try {
        const response = await fetch(`${API_BASE}/users/${userId}`);
        const data = await response.json();
        
        if (data.error) {
            content.innerHTML = `<div class="loading">${data.error}</div>`;
            return;
        }
        
        const initials = (data.user.first_name?.[0] || '') + (data.user.last_name?.[0] || '');
        
        content.innerHTML = `
            <div class="user-detail-header">
                <div class="user-avatar">${initials || '?'}</div>
                <div class="user-info">
                    <h2>${data.user.name}</h2>
                    <p class="email">${data.user.email || 'No email'}</p>
                </div>
            </div>
            
            <div class="user-stats-grid">
                <div class="user-stat-card">
                    <div class="label">Total Accesses</div>
                    <div class="value">${formatNumber(data.stats.total_accesses)}</div>
                </div>
                <div class="user-stat-card">
                    <div class="label">This Month</div>
                    <div class="value">${formatNumber(data.stats.month_accesses)}</div>
                </div>
            </div>
            
            ${data.stats.top_doors.length > 0 ? `
                <div class="top-doors-list">
                    <h3>Most Used Doors</h3>
                    ${data.stats.top_doors.map(d => `
                        <div class="top-door-item">
                            <span>${d.name}</span>
                            <span class="badge entry">${d.count}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            ${data.recent_activity.length > 0 ? `
                <div class="recent-activity">
                    <h3>Recent Activity</h3>
                    ${data.recent_activity.slice(0, 15).map(a => `
                        <div class="activity-item">
                            <span class="activity-time">${formatLocalDateTime(a.timestamp)}</span>
                            <span class="activity-door">${a.door_name}</span>
                            <span class="badge ${(a.event_type || '').toLowerCase().replace(' ', '-')}">${a.event_type || '-'}</span>
                        </div>
                    `).join('')}
                </div>
            ` : '<p style="color: var(--text-muted)">No recent activity</p>'}
            
            <div style="margin-top: 24px;">
                <button class="filter-btn" onclick="viewUserLogs('${userId}')">
                    View All Logs
                </button>
            </div>
        `;
        
        lucide.createIcons();
    } catch (error) {
        console.error('Error loading user detail:', error);
        content.innerHTML = '<div class="loading">Error loading user details</div>';
    }
}

function viewUserLogs(userId) {
    document.getElementById('user-modal').classList.remove('active');
    logsFilters = { user_id: userId };
    currentLogsPage = 0;
    document.querySelector('.nav-item[data-view="logs"]').click();
}

// Pagination
function renderPagination(containerId, total, limit, currentPage, onPageChange) {
    const container = document.getElementById(containerId);
    const totalPages = Math.ceil(total / limit);
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '';
    html += `<button ${currentPage === 0 ? 'disabled' : ''}>← Prev</button>`;
    
    const maxVisible = 5;
    let startPage = Math.max(0, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages - 1, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(0, endPage - maxVisible + 1);
    }
    
    if (startPage > 0) {
        html += `<button>1</button>`;
        if (startPage > 1) html += `<button disabled>...</button>`;
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="${i === currentPage ? 'active' : ''}">${i + 1}</button>`;
    }
    
    if (endPage < totalPages - 1) {
        if (endPage < totalPages - 2) html += `<button disabled>...</button>`;
        html += `<button>${totalPages}</button>`;
    }
    
    html += `<button ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Next →</button>`;
    
    container.innerHTML = html;
    
    container.querySelectorAll('button:not([disabled])').forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.textContent;
            if (text === '← Prev') {
                onPageChange(currentPage - 1);
            } else if (text === 'Next →') {
                onPageChange(currentPage + 1);
            } else {
                onPageChange(parseInt(text) - 1);
            }
        });
    });
}

// Utilities
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString();
}

function formatLocalDateTime(isoString) {
    if (!isoString) return '-';
    // Ensure the timestamp is treated as UTC by adding 'Z' if not present
    let dateStr = isoString;
    if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) {
        dateStr = dateStr + 'Z';
    }
    const date = new Date(dateStr);
    // Convert to local timezone
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function formatDateShort(dateString) {
    if (!dateString) return '-';
    // Parse as local date to avoid timezone shift
    // "2026-01-21" should display as "Jan 21", not shifted by timezone
    const [year, month, day] = dateString.split('-').map(Number);
    const date = new Date(year, month - 1, day); // month is 0-indexed
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getDateRange(rangeType) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    let start = null;
    let end = null;
    
    switch (rangeType) {
        case 'today':
            start = today.toISOString();
            break;
        case 'yesterday':
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            start = yesterday.toISOString();
            end = today.toISOString();
            break;
        case 'last7':
            const last7 = new Date(today);
            last7.setDate(last7.getDate() - 7);
            start = last7.toISOString();
            break;
        case 'last30':
            const last30 = new Date(today);
            last30.setDate(last30.getDate() - 30);
            start = last30.toISOString();
            break;
        case 'thisMonth':
            start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
            break;
        case 'lastMonth':
            const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0);
            start = lastMonthStart.toISOString();
            end = lastMonthEnd.toISOString();
            break;
        default:
            // All time
            break;
    }
    
    return { start, end };
}

function applyCustomDateRange() {
    const startVal = document.getElementById('filter-start-date').value;
    const endVal = document.getElementById('filter-end-date').value;
    
    if (startVal) {
        logsFilters.start_date = new Date(startVal).toISOString();
    } else {
        logsFilters.start_date = null;
    }
    
    if (endVal) {
        const endDate = new Date(endVal);
        endDate.setHours(23, 59, 59, 999);
        logsFilters.end_date = endDate.toISOString();
    } else {
        logsFilters.end_date = null;
    }
    
    currentLogsPage = 0;
    loadAccessLogs();
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
