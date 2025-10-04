/**
 * WOLManager Frontend Application
 */

class WOLManagerApp {
    constructor() {
        this.apiBase = '/api/v1';
        this.hosts = [];
        this.discoveryChart = null;
        this.statusChart = null;
        this.compactView = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadInitialData();
        this.startAutoRefresh();
    }
    
    setupEventListeners() {
        // Theme selector
        document.getElementById('theme-selector').addEventListener('change', (e) => {
            this.changeTheme(e.target.value);
        });
        
        // Discovery toggle
        document.getElementById('discovery-toggle').addEventListener('click', () => {
            this.toggleDiscovery();
        });
        
        document.getElementById('force-scan').addEventListener('click', () => {
            this.forceScan();
        });
        
        // Quick actions
        document.getElementById('refresh-hosts').addEventListener('click', () => {
            this.refreshHosts();
        });
        
        document.getElementById('export-hosts').addEventListener('click', () => {
            this.exportHosts();
        });
        
        document.getElementById('view-logs').addEventListener('click', () => {
            this.viewLogs();
        });
        
        // Add host
        document.getElementById('add-host').addEventListener('click', () => {
            this.showAddHostModal();
        });
        
        document.getElementById('cancel-add-host').addEventListener('click', () => {
            this.hideAddHostModal();
        });
        
        document.getElementById('add-host-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.addHost();
        });
        
        // Search
        document.getElementById('search-hosts').addEventListener('input', (e) => {
            this.filterHosts(e.target.value);
        });
        
        // Compact view toggle
        document.getElementById('toggle-view').addEventListener('click', () => {
            this.toggleCompactView();
        });
        
        // Host details modal
        document.getElementById('close-details-modal').addEventListener('click', () => {
            this.hideHostDetailsModal();
        });
        
        document.getElementById('close-details-modal-btn').addEventListener('click', () => {
            this.hideHostDetailsModal();
        });
        
        // WOL Hosts Modal
        document.getElementById('view-wol-hosts').addEventListener('click', () => {
            this.showWOLHostsModal();
        });
        
        document.getElementById('close-wol-modal').addEventListener('click', () => {
            document.getElementById('wol-hosts-modal').classList.add('hidden');
        });
        
        document.getElementById('close-wol-modal-btn').addEventListener('click', () => {
            document.getElementById('wol-hosts-modal').classList.add('hidden');
        });
    }
    
    async loadInitialData() {
        try {
            await Promise.all([
                this.loadHosts(),
                this.loadDiscoveryStatus(),
                this.loadStatistics()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showNotification('Failed to load data', 'error');
        }
    }
    
    async loadHosts() {
        try {
            const response = await fetch(`${this.apiBase}/hosts`);
            if (!response.ok) {
                throw new Error(`Failed to fetch hosts: ${response.status} ${response.statusText}`);
            }
            
            this.hosts = await response.json();
            this.renderHostsTable();
            this.updateStats();
        } catch (error) {
            console.error('Failed to load hosts:', error);
            this.hosts = [];
            this.renderHostsTable();
            this.updateStats();
        }
    }
    
    async loadDiscoveryStatus() {
        try {
            const response = await fetch(`${this.apiBase}/discovery/status`);
            if (!response.ok) {
                throw new Error(`Failed to fetch discovery status: ${response.status} ${response.statusText}`);
            }
            
            const status = await response.json();
            this.updateDiscoveryStatus(status);
        } catch (error) {
            console.error('Failed to load discovery status:', error);
            // Show default status on error
            this.updateDiscoveryStatus({
                status: 'unknown',
                last_run: null,
                interval: 300
            });
        }
    }
    
    async loadStatistics() {
        try {
            const response = await fetch(`${this.apiBase}/discovery/statistics`);
            if (!response.ok) {
                throw new Error(`Failed to fetch statistics: ${response.status} ${response.statusText}`);
            }
            
            const stats = await response.json();
            this.updateCharts(stats);
        } catch (error) {
            console.error('Failed to load statistics:', error);
            // Show empty charts on error
            this.updateCharts({
                by_discovery_method: {},
                by_status: {}
            });
        }
    }
    
    // Helper function to sort IP addresses numerically
    sortHostsByIP(hosts) {
        return hosts.sort((a, b) => {
            const ipA = a.ip_address.split('.').map(num => parseInt(num, 10));
            const ipB = b.ip_address.split('.').map(num => parseInt(num, 10));
            
            // Compare each octet
            for (let i = 0; i < 4; i++) {
                if (ipA[i] !== ipB[i]) {
                    return ipA[i] - ipB[i];
                }
            }
            return 0;
        });
    }
    
    renderHostsTable() {
        // Clear both tables
        const registeredTbody = document.getElementById('registered-hosts-table-body');
        const unregisteredTbody = document.getElementById('unregistered-hosts-table-body');
        const registeredEmpty = document.getElementById('registered-hosts-empty');
        const unregisteredEmpty = document.getElementById('unregistered-hosts-empty');
        
        registeredTbody.innerHTML = '';
        unregisteredTbody.innerHTML = '';
        
        // Separate hosts by WOL status and sort by IP address
        const registeredHosts = this.sortHostsByIP(this.hosts.filter(host => host.wol_enabled));
        const unregisteredHosts = this.sortHostsByIP(this.hosts.filter(host => !host.wol_enabled));
        
        // Update registered hosts table
        if (registeredHosts.length > 0) {
            registeredEmpty.classList.add('hidden');
            registeredHosts.forEach(host => {
                const row = this.createRegisteredHostRow(host);
                registeredTbody.appendChild(row);
            });
        } else {
            registeredEmpty.classList.remove('hidden');
        }
        
        // Update unregistered hosts table
        if (unregisteredHosts.length > 0) {
            unregisteredEmpty.classList.add('hidden');
            unregisteredHosts.forEach(host => {
                const row = this.createUnregisteredHostRow(host);
                unregisteredTbody.appendChild(row);
            });
        } else {
            unregisteredEmpty.classList.remove('hidden');
        }
        
        // Update counters
        document.getElementById('registered-count').textContent = registeredHosts.length;
        document.getElementById('wol-enabled').textContent = registeredHosts.length;
    }
    
    createRegisteredHostRow(host) {
        const row = document.createElement('tr');
        row.className = 'hover:bg-green-50';
        
        const statusBadge = this.getStatusBadge(host.status);
        const wolBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Enabled</span>';
        
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${host.ip_address}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${host.hostname || 'Unknown'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${host.mac_address || 'Unknown'}</td>
            <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap">${wolBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <div class="flex space-x-2">
                    ${host.mac_address ? 
                        `<button onclick="app.wakeHost('${host.ip_address}')" class="text-blue-600 hover:text-blue-900" title="Wake Host">
                            <i class="fas fa-power-off"></i>
                        </button>` : ''
                    }
                    <button onclick="app.toggleWOLRegistration('${host.ip_address}', true)" 
                            class="text-red-600 hover:text-red-900" 
                            title="Unregister from WOL">
                        <i class="fas fa-toggle-off"></i>
                    </button>
                    <button onclick="app.editHost('${host.ip_address}')" class="text-indigo-600 hover:text-indigo-900" title="Edit Host">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </td>
        `;
        
        return row;
    }
    
    createUnregisteredHostRow(host) {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';
        
        const statusBadge = this.getStatusBadge(host.status);
        const wolBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Disabled</span>';
        
        // Format vendor information
        const vendor = host.vendor || 'Unknown';
        
        // Format OS/Device information
        let osDeviceInfo = '';
        if (host.inferred_os && host.inferred_device_type) {
            // Use enhanced detection results
            osDeviceInfo = `${host.inferred_os}`;
            if (host.inferred_device_type !== 'dhcp_client' && host.inferred_device_type !== 'unknown_device') {
                osDeviceInfo += ` (${host.inferred_device_type.replace('_', ' ')})`;
            }
            if (host.inference_confidence && host.inference_confidence > 50) {
                osDeviceInfo += ` [${host.inference_confidence}%]`;
            }
        } else if (host.device_type) {
            // Fallback to device_type if no enhanced detection
            if (host.device_type.includes('dhcp_lease_')) {
                const parts = host.device_type.split('_');
                if (parts.length > 2) {
                    osDeviceInfo = parts.slice(2).join(' ').replace(/([A-Z])/g, ' $1').trim();
                } else {
                    osDeviceInfo = 'DHCP Client';
                }
            } else {
                osDeviceInfo = host.device_type.replace('_', ' ');
            }
        } else {
            osDeviceInfo = 'Unknown';
        }
        
        row.innerHTML = `
            <td class="px-3 py-4 text-sm font-medium text-gray-900 truncate" title="${host.ip_address}">${host.ip_address}</td>
            <td class="px-3 py-4 text-sm text-gray-500 truncate" title="${host.hostname || 'Unknown'}">${host.hostname || 'Unknown'}</td>
            <td class="px-3 py-4 text-sm text-gray-500 truncate" title="${host.mac_address || 'Unknown'}">${host.mac_address || 'Unknown'}</td>
            <td class="px-3 py-4 text-sm text-gray-500 truncate hidden lg:table-cell" title="${vendor}">${vendor}</td>
            <td class="px-3 py-4 text-sm text-gray-500 truncate hidden md:table-cell" title="${osDeviceInfo}">${osDeviceInfo}</td>
            <td class="px-3 py-4">${statusBadge}</td>
            <td class="px-3 py-4 hidden sm:table-cell">${wolBadge}</td>
            <td class="px-3 py-4 text-sm font-medium">
                <div class="flex space-x-2">
                    ${host.mac_address ? 
                        `<button onclick="app.toggleWOLRegistration('${host.ip_address}', false)" 
                                class="text-green-600 hover:text-green-900" 
                                title="Register for WOL">
                            <i class="fas fa-toggle-on"></i>
                        </button>` : 
                        `<button class="text-gray-400 cursor-not-allowed" title="No MAC address available" disabled>
                            <i class="fas fa-toggle-off"></i>
                        </button>`
                    }
                    <button onclick="app.showHostDetails('${host.ip_address}')" class="text-blue-600 hover:text-blue-900" title="View Details">
                        <i class="fas fa-info-circle"></i>
                    </button>
                    <button onclick="app.editHost('${host.ip_address}')" class="text-indigo-600 hover:text-indigo-900" title="Edit Host">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="app.deleteHost('${host.ip_address}')" class="text-red-600 hover:text-red-900" title="Delete Host">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        return row;
    }
    
    getStatusBadge(status) {
        const badges = {
            'online': '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Online</span>',
            'offline': '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Offline</span>',
            'unknown': '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Unknown</span>'
        };
        return badges[status] || badges['unknown'];
    }
    
    updateStats() {
        document.getElementById('total-hosts').textContent = this.hosts.length;
        document.getElementById('wol-enabled').textContent = this.hosts.filter(h => h.wol_enabled).length;
        document.getElementById('online-hosts').textContent = this.hosts.filter(h => h.status === 'online').length;
    }
    
    updateDiscoveryStatus(status) {
        const lastScan = status.last_run ? new Date(status.last_run).toLocaleString() : 'Never';
        document.getElementById('last-scan').textContent = lastScan;
        
        // Update the new discovery status display in dashboard
        const statusElement = document.getElementById('discovery-status');
        const statusIcon = document.getElementById('discovery-status-icon');
        const toggleButton = document.getElementById('discovery-toggle');
        
        if (status.status === 'running') {
            statusElement.textContent = 'Running';
            statusIcon.className = 'fas fa-circle text-green-600';
            toggleButton.className = 'bg-red-600 text-white px-3 py-2 rounded-md hover:bg-red-700 transition-colors text-sm';
            toggleButton.innerHTML = '<i class="fas fa-stop"></i>';
            toggleButton.title = 'Stop Discovery';
        } else if (status.status === 'error') {
            statusElement.textContent = 'Error';
            statusIcon.className = 'fas fa-circle text-red-600';
            toggleButton.className = 'bg-green-600 text-white px-3 py-2 rounded-md hover:bg-green-700 transition-colors text-sm';
            toggleButton.innerHTML = '<i class="fas fa-play"></i>';
            toggleButton.title = 'Start Discovery';
        } else {
            statusElement.textContent = 'Stopped';
            statusIcon.className = 'fas fa-circle text-red-600';
            toggleButton.className = 'bg-green-600 text-white px-3 py-2 rounded-md hover:bg-green-700 transition-colors text-sm';
            toggleButton.innerHTML = '<i class="fas fa-play"></i>';
            toggleButton.title = 'Start Discovery';
        }
        
        // Keep the old status indicator for compatibility (if it exists)
        const indicator = document.getElementById('status-indicator');
        if (indicator) {
            const dot = indicator.querySelector('.w-2');
            const text = indicator.querySelector('span');
            
            if (status.status === 'running') {
                dot.className = 'w-2 h-2 bg-green-500 rounded-full mr-2';
                text.textContent = 'Running';
            } else if (status.status === 'error') {
                dot.className = 'w-2 h-2 bg-red-500 rounded-full mr-2';
                text.textContent = 'Error';
            } else {
                dot.className = 'w-2 h-2 bg-yellow-500 rounded-full mr-2';
                text.textContent = 'Stopped';
            }
        }
    }
    
    updateCharts(stats) {
        this.updateDiscoveryChart(stats.by_discovery_method);
        this.updateStatusChart(stats.by_status);
    }
    
    updateDiscoveryChart(methodData) {
        const ctx = document.getElementById('discovery-chart').getContext('2d');
        
        if (this.discoveryChart) {
            this.discoveryChart.destroy();
        }
        
        // Handle empty data
        const labels = Object.keys(methodData);
        const data = Object.values(methodData);
        
        if (labels.length === 0) {
            // Show empty state
            this.discoveryChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['No Data'],
                    datasets: [{
                        data: [1],
                        backgroundColor: ['#E5E7EB']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
            return;
        }
        
        this.discoveryChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        '#3B82F6',
                        '#10B981',
                        '#F59E0B',
                        '#EF4444',
                        '#8B5CF6',
                        '#06B6D4'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    updateStatusChart(statusData) {
        const ctx = document.getElementById('status-chart').getContext('2d');
        
        if (this.statusChart) {
            this.statusChart.destroy();
        }
        
        // Handle empty data
        const labels = Object.keys(statusData);
        const data = Object.values(statusData);
        
        if (labels.length === 0) {
            // Show empty state
            this.statusChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: ['No Data'],
                    datasets: [{
                        data: [1],
                        backgroundColor: ['#E5E7EB']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
            return;
        }
        
        this.statusChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        '#10B981',
                        '#EF4444',
                        '#6B7280'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    async toggleDiscovery() {
        try {
            const statusElement = document.getElementById('discovery-status');
            const statusText = statusElement.textContent;
            
            let response;
            if (statusText === 'Stopped' || statusText === 'Unknown') {
                // Start discovery
                response = await fetch(`${this.apiBase}/discovery/start`, { method: 'POST' });
                if (!response.ok) throw new Error('Failed to start discovery');
                this.showNotification('Discovery started', 'success');
            } else {
                // Stop discovery
                response = await fetch(`${this.apiBase}/discovery/stop`, { method: 'POST' });
                if (!response.ok) throw new Error('Failed to stop discovery');
                this.showNotification('Discovery stopped', 'success');
            }
            
            this.loadDiscoveryStatus();
        } catch (error) {
            console.error('Failed to toggle discovery:', error);
            this.showNotification('Failed to toggle discovery', 'error');
        }
    }
    
    async forceScan() {
        try {
            const response = await fetch(`${this.apiBase}/discovery/run`, { method: 'POST' });
            if (!response.ok) throw new Error('Failed to run discovery');
            
            this.showNotification('Discovery scan completed', 'success');
            this.loadHosts();
            this.loadStatistics();
        } catch (error) {
            console.error('Failed to run discovery:', error);
            this.showNotification('Failed to run discovery', 'error');
        }
    }
    
    async wakeHost(ipAddress) {
        try {
            const response = await fetch(`${this.apiBase}/wol/wake/${ipAddress}`, { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(`Wake-on-LAN sent to ${ipAddress}`, 'success');
            } else {
                this.showNotification(`Failed to wake ${ipAddress}: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to wake host:', error);
            this.showNotification('Failed to wake host', 'error');
        }
    }
    
    async toggleWOLRegistration(ipAddress, currentWOLStatus) {
        const action = currentWOLStatus ? 'unregister' : 'register';
        const endpoint = currentWOLStatus ? 'unregister-wol' : 'register-wol';
        
        try {
            const response = await fetch(`${this.apiBase}/hosts/${ipAddress}/${endpoint}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showNotification(result.message, 'success');
                this.loadHosts(); // Refresh the hosts list to update the UI
            } else {
                const error = await response.json();
                this.showNotification(error.detail || `Failed to ${action} host for WOL`, 'error');
            }
        } catch (error) {
            console.error(`Failed to ${action} host for WOL:`, error);
            this.showNotification(`Failed to ${action} host for WOL`, 'error');
        }
    }
    
    async addHost() {
        try {
            const form = document.getElementById('add-host-form');
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            data.wol_enabled = formData.has('wol_enabled');
            
            const response = await fetch(`${this.apiBase}/hosts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) throw new Error('Failed to add host');
            
            this.showNotification('Host added successfully', 'success');
            this.hideAddHostModal();
            this.loadHosts();
        } catch (error) {
            console.error('Failed to add host:', error);
            this.showNotification('Failed to add host', 'error');
        }
    }
    
    async deleteHost(ipAddress) {
        if (!confirm(`Are you sure you want to delete host ${ipAddress}?`)) return;
        
        try {
            const response = await fetch(`${this.apiBase}/hosts/${ipAddress}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Failed to delete host');
            
            this.showNotification('Host deleted successfully', 'success');
            this.loadHosts();
        } catch (error) {
            console.error('Failed to delete host:', error);
            this.showNotification('Failed to delete host', 'error');
        }
    }
    
    showAddHostModal() {
        document.getElementById('add-host-modal').classList.remove('hidden');
    }
    
    hideAddHostModal() {
        document.getElementById('add-host-modal').classList.add('hidden');
        document.getElementById('add-host-form').reset();
    }
    
    refreshHosts() {
        this.loadHosts();
        this.showNotification('Hosts refreshed', 'success');
    }
    
    exportHosts() {
        const csv = this.hostsToCSV(this.sortHostsByIP(this.hosts));
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'wolmanager-hosts.csv';
        a.click();
        URL.revokeObjectURL(url);
    }
    
    toggleCompactView() {
        this.compactView = !this.compactView;
        const toggleBtn = document.getElementById('toggle-view');
        const table = document.querySelector('#unregistered-hosts-table-body').closest('table');
        
        if (this.compactView) {
            // Compact view - hide less important columns
            table.classList.add('table-compact');
            toggleBtn.innerHTML = '<i class="fas fa-compress-arrows-alt mr-2"></i>Full';
            toggleBtn.title = 'Switch to full view';
            
            // Hide columns on smaller screens
            const vendorCols = table.querySelectorAll('th:nth-child(4), td:nth-child(4)');
            const osCols = table.querySelectorAll('th:nth-child(5), td:nth-child(5)');
            const wolCols = table.querySelectorAll('th:nth-child(7), td:nth-child(7)');
            
            vendorCols.forEach(col => col.classList.add('hidden'));
            osCols.forEach(col => col.classList.add('hidden', 'lg:table-cell'));
            wolCols.forEach(col => col.classList.add('hidden', 'sm:table-cell'));
        } else {
            // Full view - show all columns
            table.classList.remove('table-compact');
            toggleBtn.innerHTML = '<i class="fas fa-expand-arrows-alt mr-2"></i>Compact';
            toggleBtn.title = 'Switch to compact view';
            
            // Show all columns with responsive classes
            const vendorCols = table.querySelectorAll('th:nth-child(4), td:nth-child(4)');
            const osCols = table.querySelectorAll('th:nth-child(5), td:nth-child(5)');
            const wolCols = table.querySelectorAll('th:nth-child(7), td:nth-child(7)');
            
            vendorCols.forEach(col => {
                col.classList.remove('hidden');
                col.classList.add('hidden', 'lg:table-cell');
            });
            osCols.forEach(col => {
                col.classList.remove('hidden');
                col.classList.add('hidden', 'md:table-cell');
            });
            wolCols.forEach(col => {
                col.classList.remove('hidden');
                col.classList.add('hidden', 'sm:table-cell');
            });
        }
    }
    
    async showHostDetails(ipAddress) {
        try {
            const host = this.hosts.find(h => h.ip_address === ipAddress);
            if (!host) {
                this.showNotification('Host not found', 'error');
                return;
            }
            
            this.populateHostDetailsModal(host);
            document.getElementById('host-details-modal').classList.remove('hidden');
        } catch (error) {
            console.error('Failed to show host details:', error);
            this.showNotification('Failed to load host details', 'error');
        }
    }
    
    populateHostDetailsModal(host) {
        const content = document.getElementById('host-details-content');
        
        // Format OS/Device information
        let osDeviceInfo = '';
        if (host.inferred_os && host.inferred_device_type) {
            osDeviceInfo = `${host.inferred_os}`;
            if (host.inferred_device_type !== 'dhcp_client' && host.inferred_device_type !== 'unknown_device') {
                osDeviceInfo += ` (${host.inferred_device_type.replace('_', ' ')})`;
            }
            if (host.inference_confidence && host.inference_confidence > 50) {
                osDeviceInfo += ` [${host.inference_confidence}% confidence]`;
            }
        } else if (host.device_type) {
            osDeviceInfo = host.device_type.replace('_', ' ');
        } else {
            osDeviceInfo = 'Unknown';
        }
        
        // Format discovery info
        const discoveryMethod = host.discovery_method?.replace('_', ' ').toUpperCase() || 'Unknown';
        const lastSeen = host.last_seen ? new Date(host.last_seen).toLocaleString() : 'Never';
        
        content.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Basic Information -->
                <div class="space-y-4">
                    <h4 class="text-md font-semibold text-gray-900 border-b pb-2">Basic Information</h4>
                    
                    <div class="space-y-3">
                        <div>
                            <label class="text-sm font-medium text-gray-500">IP Address</label>
                            <p class="text-sm text-gray-900 font-mono">${host.ip_address}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">Hostname</label>
                            <p class="text-sm text-gray-900">${host.hostname || 'Not available'}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">MAC Address</label>
                            <p class="text-sm text-gray-900 font-mono">${host.mac_address || 'Not available'}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">Vendor</label>
                            <p class="text-sm text-gray-900">${host.vendor || 'Unknown'}</p>
                        </div>
                    </div>
                </div>
                
                <!-- Technical Details -->
                <div class="space-y-4">
                    <h4 class="text-md font-semibold text-gray-900 border-b pb-2">Technical Details</h4>
                    
                    <div class="space-y-3">
                        <div>
                            <label class="text-sm font-medium text-gray-500">Status</label>
                            <p class="text-sm">${this.getStatusBadge(host.status)}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">Wake-on-LAN</label>
                            <p class="text-sm">
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${host.wol_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                                    ${host.wol_enabled ? 'Enabled' : 'Disabled'}
                                </span>
                            </p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">OS/Device</label>
                            <p class="text-sm text-gray-900">${osDeviceInfo}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">Discovery Method</label>
                            <p class="text-sm text-gray-900">${discoveryMethod}</p>
                        </div>
                        
                        <div>
                            <label class="text-sm font-medium text-gray-500">Last Seen</label>
                            <p class="text-sm text-gray-900">${lastSeen}</p>
                        </div>
                    </div>
                </div>
            </div>
            
            ${host.notes ? `
                <div class="mt-6">
                    <h4 class="text-md font-semibold text-gray-900 border-b pb-2">Notes</h4>
                    <p class="text-sm text-gray-900 mt-2">${host.notes}</p>
                </div>
            ` : ''}
            
            ${host.os_info ? `
                <div class="mt-6">
                    <h4 class="text-md font-semibold text-gray-900 border-b pb-2">OS Information</h4>
                    <p class="text-sm text-gray-900 mt-2 font-mono bg-gray-50 p-3 rounded">${host.os_info}</p>
                </div>
            ` : ''}
        `;
        
        // Update edit button
        document.getElementById('edit-from-details').onclick = () => {
            this.hideHostDetailsModal();
            this.editHost(host.ip_address);
        };
    }
    
    hideHostDetailsModal() {
        document.getElementById('host-details-modal').classList.add('hidden');
    }
    
    hostsToCSV(hosts) {
        const headers = ['IP Address', 'Hostname', 'MAC Address', 'Status', 'Device Type', 'WOL Enabled'];
        const rows = hosts.map(host => [
            host.ip_address,
            host.hostname || '',
            host.mac_address || '',
            host.status,
            host.device_type || '',
            host.wol_enabled ? 'Yes' : 'No'
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }
    
    filterHosts(searchTerm) {
        if (!searchTerm) {
            // If no search term, show all hosts
            this.renderHostsTable();
            return;
        }
        
        const filteredHosts = this.hosts.filter(host => 
            host.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (host.hostname && host.hostname.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (host.mac_address && host.mac_address.toLowerCase().includes(searchTerm.toLowerCase()))
        );
        
        // Clear both tables
        const registeredTbody = document.getElementById('registered-hosts-table-body');
        const unregisteredTbody = document.getElementById('unregistered-hosts-table-body');
        const registeredEmpty = document.getElementById('registered-hosts-empty');
        const unregisteredEmpty = document.getElementById('unregistered-hosts-empty');
        
        registeredTbody.innerHTML = '';
        unregisteredTbody.innerHTML = '';
        
        // Separate filtered hosts by WOL status and sort by IP address
        const registeredHosts = this.sortHostsByIP(filteredHosts.filter(host => host.wol_enabled));
        const unregisteredHosts = this.sortHostsByIP(filteredHosts.filter(host => !host.wol_enabled));
        
        // Update registered hosts table
        if (registeredHosts.length > 0) {
            registeredEmpty.classList.add('hidden');
            registeredHosts.forEach(host => {
                const row = this.createRegisteredHostRow(host);
                registeredTbody.appendChild(row);
            });
        } else {
            registeredEmpty.classList.remove('hidden');
        }
        
        // Update unregistered hosts table
        if (unregisteredHosts.length > 0) {
            unregisteredEmpty.classList.add('hidden');
            unregisteredHosts.forEach(host => {
                const row = this.createUnregisteredHostRow(host);
                unregisteredTbody.appendChild(row);
            });
        } else {
            unregisteredEmpty.classList.remove('hidden');
        }
        
        // Update counters
        document.getElementById('registered-count').textContent = registeredHosts.length;
        document.getElementById('wol-enabled').textContent = registeredHosts.length;
    }
    
    changeTheme(theme) {
        document.body.className = `theme-${theme}`;
        localStorage.setItem('wolmanager-theme', theme);
    }
    
    viewLogs() {
        this.showNotification('Logs feature coming soon', 'info');
    }
    
    async showWOLHostsModal() {
        try {
            const response = await fetch(`${this.apiBase}/hosts/wol-registered`);
            if (!response.ok) {
                throw new Error('Failed to fetch WOL hosts');
            }
            
            const data = await response.json();
            this.populateWOLHostsModal(data);
            document.getElementById('wol-hosts-modal').classList.remove('hidden');
        } catch (error) {
            console.error('Failed to load WOL hosts:', error);
            this.showNotification('Failed to load WOL hosts', 'error');
        }
    }
    
    populateWOLHostsModal(data) {
        const hostsList = document.getElementById('wol-hosts-list');
        const emptyState = document.getElementById('wol-hosts-empty');
        
        if (data.hosts.length === 0) {
            hostsList.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }
        
        hostsList.classList.remove('hidden');
        emptyState.classList.add('hidden');
        
        // Sort WOL hosts by IP address
        const sortedWOLHosts = this.sortHostsByIP(data.hosts);
        
        hostsList.innerHTML = sortedWOLHosts.map(host => `
            <div class="bg-gray-50 rounded-lg p-4 flex items-center justify-between">
                <div class="flex-1">
                    <div class="flex items-center space-x-4">
                        <div class="flex-shrink-0">
                            <div class="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                                <i class="fas fa-power-off text-green-600"></i>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-sm font-medium text-gray-900">${host.ip_address}</h4>
                            <p class="text-sm text-gray-500">
                                ${host.hostname || 'Unknown'} • ${host.mac_address || 'No MAC'}
                                ${host.vendor ? ` • ${host.vendor}` : ''}
                            </p>
                            ${host.inferred_os ? 
                                `<p class="text-xs text-gray-400">${host.inferred_os}${host.inferred_device_type && host.inferred_device_type !== 'dhcp_client' && host.inferred_device_type !== 'unknown_device' ? ` (${host.inferred_device_type.replace('_', ' ')})` : ''}${host.inference_confidence && host.inference_confidence > 50 ? ` [${host.inference_confidence}%]` : ''}</p>` : ''
                            }
                        </div>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <button onclick="app.wakeHost('${host.ip_address}')" 
                            class="bg-blue-600 text-white px-3 py-1 rounded-md text-sm hover:bg-blue-700 transition-colors">
                        <i class="fas fa-power-off mr-1"></i>Wake
                    </button>
                    <button onclick="app.toggleWOLRegistration('${host.ip_address}', true)" 
                            class="bg-red-600 text-white px-3 py-1 rounded-md text-sm hover:bg-red-700 transition-colors">
                        <i class="fas fa-times mr-1"></i>Unregister
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    showNotification(message, type = 'info') {
        // Simple notification implementation
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 px-4 py-2 rounded-md text-white z-50 ${
            type === 'success' ? 'bg-green-600' :
            type === 'error' ? 'bg-red-600' :
            type === 'warning' ? 'bg-yellow-600' :
            'bg-blue-600'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    startAutoRefresh() {
        // Refresh data every 30 seconds
        setInterval(() => {
            this.loadHosts();
            this.loadDiscoveryStatus();
        }, 30000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new WOLManagerApp();
    
    // Load saved theme
    const savedTheme = localStorage.getItem('wolmanager-theme') || 'white';
    document.getElementById('theme-selector').value = savedTheme;
    window.app.changeTheme(savedTheme);
});
