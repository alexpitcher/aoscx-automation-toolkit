/**
 * Mobile-First AOS-CX Automation Toolkit Dashboard JavaScript
 * Enhanced version with mobile-optimized navigation and responsive design
 */

class MobileDashboard {
    constructor() {
        this.switches = new Map();
        this.currentSwitch = null;
        this.activeTab = 'dashboard';
        this.lastRefresh = new Date();
        this.isLoading = false;
        this.init();
    }

    init() {
        this.setupMobileNavigation();
        this.setupEventListeners();
        this.loadSwitches();
        this.startHealthMonitoring();
        this.setupPullToRefresh();
        this.updateLastRefreshDisplay();
    }

    setupMobileNavigation() {
        // Setup tab switching
        const navTabs = document.querySelectorAll('.nav-tab');
        navTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const tabName = tab.dataset.tab;
                this.showTab(tabName);
            });
        });

        // Show initial tab
        this.showTab(this.activeTab);
    }

    showTab(tabName) {
        // Hide all tab contents
        const allTabs = document.querySelectorAll('.tab-content');
        allTabs.forEach(tab => {
            tab.style.display = 'none';
            tab.classList.remove('active');
        });

        // Remove active class from all nav tabs
        const navTabs = document.querySelectorAll('.nav-tab');
        navTabs.forEach(tab => {
            tab.classList.remove('active');
        });

        // Show selected tab
        const selectedTab = document.getElementById(`${tabName}-tab`);
        const selectedNavTab = document.querySelector(`[data-tab="${tabName}"]`);
        
        if (selectedTab) {
            selectedTab.style.display = 'block';
            selectedTab.classList.add('active');
        }
        
        if (selectedNavTab) {
            selectedNavTab.classList.add('active');
        }

        this.activeTab = tabName;

        // Load data for specific tabs
        if (tabName === 'switches') {
            this.loadSwitches();
        } else if (tabName === 'vlans') {
            this.updateSwitchSelector();
            if (this.currentSwitch) {
                this.loadVlansForCurrentSwitch();
            }
        }
    }

    setupEventListeners() {
        // Add switch form
        const addSwitchForm = document.getElementById('add-switch-form');
        if (addSwitchForm) {
            addSwitchForm.addEventListener('submit', (e) => this.handleAddSwitch(e));
        }

        // Credential toggle
        const toggleCredentialsBtn = document.getElementById('toggle-credentials');
        if (toggleCredentialsBtn) {
            toggleCredentialsBtn.addEventListener('click', (e) => this.toggleCredentials(e));
        }

        // VLAN management forms
        const vlanListForm = document.getElementById('vlan-list-form');
        if (vlanListForm) {
            vlanListForm.addEventListener('submit', (e) => this.handleListVlans(e));
        }

        const vlanCreateForm = document.getElementById('vlan-create-form');
        if (vlanCreateForm) {
            vlanCreateForm.addEventListener('submit', (e) => this.handleCreateVlan(e));
        }

        // Switch selector
        const switchSelector = document.getElementById('switch-selector');
        if (switchSelector) {
            switchSelector.addEventListener('change', (e) => {
                this.currentSwitch = e.target.value;
                this.loadVlansForCurrentSwitch();
            });
        }

        // Handle switch actions with event delegation
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('refresh-switch')) {
                const switchIp = e.target.dataset.switchIp;
                this.refreshSwitch(switchIp);
            }
            if (e.target.classList.contains('remove-switch')) {
                const switchIp = e.target.dataset.switchIp;
                this.removeSwitch(switchIp);
            }
        });

        // Handle mobile viewport changes
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.adjustForViewport();
            }, 100);
        });

        // Handle back button on mobile
        window.addEventListener('popstate', (e) => {
            if (e.state && e.state.tab) {
                this.showTab(e.state.tab);
            }
        });
    }

    setupPullToRefresh() {
        let startY = 0;
        let isPulling = false;
        const pullThreshold = 100;

        document.addEventListener('touchstart', (e) => {
            if (window.pageYOffset === 0) {
                startY = e.touches[0].pageY;
                isPulling = true;
            }
        }, { passive: true });

        document.addEventListener('touchmove', (e) => {
            if (!isPulling) return;
            
            const currentY = e.touches[0].pageY;
            const pullDistance = currentY - startY;
            
            if (pullDistance > 0 && window.pageYOffset === 0) {
                e.preventDefault();
                
                if (pullDistance > pullThreshold) {
                    this.showAlert('Release to refresh...', 'info');
                }
            }
        }, { passive: false });

        document.addEventListener('touchend', (e) => {
            if (!isPulling) return;
            isPulling = false;
            
            const endY = e.changedTouches[0].pageY;
            const pullDistance = endY - startY;
            
            if (pullDistance > pullThreshold) {
                this.refreshAllSwitches();
            }
        }, { passive: true });
    }

    adjustForViewport() {
        // Adjust UI for different screen orientations and sizes
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }

    toggleCredentials(event) {
        event.preventDefault();
        const credentialsSection = document.getElementById('credentials-section');
        const toggleText = document.getElementById('cred-toggle-text');
        
        if (credentialsSection.style.display === 'none') {
            credentialsSection.style.display = 'block';
            toggleText.textContent = 'Hide Credentials';
        } else {
            credentialsSection.style.display = 'none';
            toggleText.textContent = 'Show Credentials';
        }
    }

    async loadSwitches() {
        try {
            this.setGlobalLoading(true);
            const response = await fetch('/api/switches');
            const data = await response.json();
            
            if (data.switches) {
                this.switches.clear();
                data.switches.forEach(switch_info => {
                    this.switches.set(switch_info.ip_address, switch_info);
                });
                this.renderSwitches();
                this.updateSwitchSelector();
                this.updateDashboardStats();
                this.updateNetworkStatus();
            }
        } catch (error) {
            this.showAlert('Error loading switches: ' + error.message, 'error');
        } finally {
            this.setGlobalLoading(false);
            this.lastRefresh = new Date();
            this.updateLastRefreshDisplay();
        }
    }

    async handleAddSwitch(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const switchIp = formData.get('switch_ip');
        const switchName = formData.get('switch_name');
        const username = formData.get('switch_username');
        const password = formData.get('switch_password');

        if (!this.isValidIP(switchIp)) {
            this.showAlert('Please enter a valid IP address', 'error');
            return;
        }

        try {
            this.setButtonLoading('add-switch-btn', true);
            
            const requestBody = { 
                ip_address: switchIp, 
                name: switchName 
            };
            
            // Only include credentials if provided
            if (username && username.trim()) {
                requestBody.username = username.trim();
            }
            if (password) {
                requestBody.password = password;
            }
            
            const response = await fetch('/api/switches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const data = await response.json();
            
            if (response.ok) {
                this.switches.set(switchIp, data.switch);
                this.renderSwitches();
                this.updateSwitchSelector();
                this.updateDashboardStats();
                this.showAlert(data.message, 'success');
                event.target.reset();
                
                // Hide credentials section after successful add
                const credentialsSection = document.getElementById('credentials-section');
                const toggleText = document.getElementById('cred-toggle-text');
                if (credentialsSection && toggleText) {
                    credentialsSection.style.display = 'none';
                    toggleText.textContent = 'Show Credentials';
                }
                
                // Test connection immediately
                this.refreshSwitch(switchIp);
                
                // Provide haptic feedback on mobile
                if (navigator.haptic) {
                    navigator.haptic.notification({ type: 'success' });
                }
            } else {
                // Handle different error types
                if (data.error_type === 'authentication_failed') {
                    this.showAlert('Authentication failed. Please provide correct credentials below.', 'warning');
                    // Auto-show credentials section
                    const credentialsSection = document.getElementById('credentials-section');
                    const toggleText = document.getElementById('cred-toggle-text');
                    if (credentialsSection && toggleText) {
                        credentialsSection.style.display = 'block';
                        toggleText.textContent = 'Hide Credentials';
                    }
                } else if (data.error && (data.error.includes('authentication') || data.error.includes('credentials'))) {
                    this.showAlert('Authentication failed. Please check credentials or try the credentials section below.', 'warning');
                    // Auto-show credentials section
                    const credentialsSection = document.getElementById('credentials-section');
                    const toggleText = document.getElementById('cred-toggle-text');
                    if (credentialsSection && toggleText) {
                        credentialsSection.style.display = 'block';
                        toggleText.textContent = 'Hide Credentials';
                    }
                } else {
                    this.showAlert(data.error || 'Failed to add switch', 'error');
                }
            }
        } catch (error) {
            this.showAlert('Error adding switch: ' + error.message, 'error');
        } finally {
            this.setButtonLoading('add-switch-btn', false);
        }
    }

    async refreshSwitch(switchIp) {
        try {
            const response = await fetch(`/api/switches/${switchIp}/test`);
            const data = await response.json();
            
            // Update switch info
            this.switches.set(switchIp, data);
            this.renderSwitches();
            this.updateDashboardStats();
            this.updateNetworkStatus();
            
            if (data.status === 'online') {
                this.showAlert(`Switch ${switchIp} is online`, 'success');
            } else {
                this.showAlert(`Switch ${switchIp}: ${data.error_message}`, 'error');
            }
        } catch (error) {
            this.showAlert('Error testing switch: ' + error.message, 'error');
        }
    }

    async removeSwitch(switchIp) {
        // Use mobile-friendly confirmation
        if (!confirm(`Remove switch ${switchIp} from inventory?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/switches/${switchIp}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.switches.delete(switchIp);
                this.renderSwitches();
                this.updateSwitchSelector();
                this.updateDashboardStats();
                this.updateNetworkStatus();
                this.showAlert(`Switch ${switchIp} removed`, 'success');
                
                // Provide haptic feedback
                if (navigator.haptic) {
                    navigator.haptic.notification({ type: 'warning' });
                }
            } else {
                const data = await response.json();
                this.showAlert(data.error || 'Failed to remove switch', 'error');
            }
        } catch (error) {
            this.showAlert('Error removing switch: ' + error.message, 'error');
        }
    }

    async handleListVlans(event) {
        event.preventDefault();
        const switchIp = this.currentSwitch;
        
        if (!switchIp) {
            this.showAlert('Please select a switch first', 'error');
            return;
        }

        try {
            this.setButtonLoading('list-vlans-btn', true);
            await this.loadVlans(switchIp);
        } finally {
            this.setButtonLoading('list-vlans-btn', false);
        }
    }

    async handleCreateVlan(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const switchIp = this.currentSwitch;
        const vlanId = parseInt(formData.get('vlan_id'));
        const vlanName = formData.get('vlan_name');

        if (!switchIp) {
            this.showAlert('Please select a switch first', 'error');
            return;
        }

        if (!vlanId || vlanId < 1 || vlanId > 4094) {
            this.showAlert('VLAN ID must be between 1 and 4094', 'error');
            return;
        }

        if (!vlanName.trim()) {
            this.showAlert('VLAN name is required', 'error');
            return;
        }

        try {
            this.setButtonLoading('create-vlan-btn', true);
            
            const response = await fetch('/api/vlans', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    switch_ip: switchIp,
                    vlan_id: vlanId,
                    name: vlanName.trim()
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(data.message, 'success');
                event.target.reset();
                // Refresh VLAN list
                this.loadVlans(switchIp);
                
                // Provide haptic feedback
                if (navigator.haptic) {
                    navigator.haptic.notification({ type: 'success' });
                }
            } else {
                // Enhanced error messaging
                let errorMsg = data.error || 'Failed to create VLAN';
                let alertType = 'error';
                
                if (data.error_type === 'central_management') {
                    alertType = 'warning';
                    errorMsg += ` ${data.suggestion || ''}`;
                } else if (data.error_type === 'permission_denied') {
                    alertType = 'warning';
                    errorMsg += ` ${data.suggestion || ''}`;
                }
                
                this.showAlert(errorMsg, alertType);
            }
        } catch (error) {
            this.showAlert('Error creating VLAN: ' + error.message, 'error');
        } finally {
            this.setButtonLoading('create-vlan-btn', false);
        }
    }

    async loadVlans(switchIp) {
        try {
            const response = await fetch(`/api/vlans?switch_ip=${encodeURIComponent(switchIp)}&load_details=true`);
            const data = await response.json();
            
            if (response.ok) {
                this.renderVlans(data.vlans || []);
            } else {
                let errorMsg = data.error || 'Failed to load VLANs';
                let alertType = 'error';
                
                if (data.error_type === 'central_management') {
                    alertType = 'warning';
                    this.showAlert(`${errorMsg} ${data.suggestion || ''}`, alertType);
                } else {
                    this.showAlert(errorMsg, alertType);
                }
                this.renderVlans([]);
            }
        } catch (error) {
            this.showAlert('Error loading VLANs: ' + error.message, 'error');
            this.renderVlans([]);
        }
    }

    loadVlansForCurrentSwitch() {
        if (this.currentSwitch) {
            this.loadVlans(this.currentSwitch);
        }
    }

    renderSwitches() {
        const container = document.getElementById('switches-container');
        if (!container) return;

        if (this.switches.size === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <p class="text-muted-foreground">No switches added yet</p>
                    <p class="text-muted-foreground text-sm">Add a switch to get started</p>
                </div>
            `;
            return;
        }

        const switchCards = Array.from(this.switches.values()).map(switch_info => {
            const statusColor = switch_info.status === 'online' ? 'text-green-600' : 
                               switch_info.status === 'error' ? 'text-red-600' : 'text-muted-foreground';
            
            const statusIcon = this.getStatusIcon(switch_info.status);
            
            return `
                <div class="switch-card">
                    <div class="switch-info">
                        <div class="switch-details">
                            <h4 class="font-semibold">${switch_info.name || switch_info.ip_address}</h4>
                            <div class="switch-meta">
                                IP: ${switch_info.ip_address}
                                ${switch_info.firmware_version ? `• FW: ${switch_info.firmware_version}` : ''}
                                ${switch_info.model ? `• ${switch_info.model}` : ''}
                            </div>
                            ${switch_info.last_seen ? `
                                <div class="switch-meta">
                                    Last seen: ${new Date(switch_info.last_seen).toLocaleString()}
                                </div>
                            ` : ''}
                        </div>
                        <div class="text-right">
                            <div class="status status-${switch_info.status}">
                                ${switch_info.status}
                            </div>
                        </div>
                    </div>
                    <div class="switch-actions">
                        <button class="btn-secondary btn-sm refresh-switch" data-switch-ip="${switch_info.ip_address}">
                            Test Connection
                        </button>
                        <button class="btn-outline btn-sm remove-switch" data-switch-ip="${switch_info.ip_address}" style="color: var(--error-color); border-color: var(--error-color);">
                            Remove
                        </button>
                    </div>
                    ${switch_info.error_message ? `
                        <div class="alert alert-error mt-1">
                            ${switch_info.error_message}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        container.innerHTML = switchCards;
    }

    updateSwitchSelector() {
        const selector = document.getElementById('switch-selector');
        if (!selector) return;

        const options = Array.from(this.switches.values())
            .map(switch_info => {
                const statusIndicator = switch_info.status === 'online' ? '✓' : '✗';
                return `
                    <option value="${switch_info.ip_address}" ${switch_info.ip_address === this.currentSwitch ? 'selected' : ''}>
                        ${statusIndicator} ${switch_info.name || switch_info.ip_address}
                    </option>
                `;
            }).join('');

        selector.innerHTML = `
            <option value="">Select a switch...</option>
            ${options}
        `;

        // Auto-select if only one switch exists
        if (this.switches.size === 1 && !this.currentSwitch) {
            this.currentSwitch = Array.from(this.switches.keys())[0];
            selector.value = this.currentSwitch;
            this.loadVlansForCurrentSwitch();
        }
    }

    renderVlans(vlans) {
        const container = document.getElementById('vlans-container');
        if (!container) return;

        if (vlans.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted-foreground">
                    <p>No VLANs found${this.currentSwitch ? ` on ${this.currentSwitch}` : ''}</p>
                </div>
            `;
            return;
        }

        const rows = vlans.map(vlan => `
            <tr>
                <td>${vlan.id}</td>
                <td>${vlan.name}</td>
                <td><span class="status status-${vlan.admin_state === 'up' ? 'online' : 'offline'}">${vlan.admin_state || 'unknown'}</span></td>
                <td><span class="status status-${vlan.oper_state === 'up' ? 'online' : 'offline'}">${vlan.oper_state || 'unknown'}</span></td>
            </tr>
        `).join('');

        container.innerHTML = `
            <div class="overflow-auto">
                <table class="vlan-table">
                    <thead>
                        <tr>
                            <th>VLAN ID</th>
                            <th>Name</th>
                            <th>Admin State</th>
                            <th>Oper State</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    }

    updateDashboardStats() {
        const totalCount = this.switches.size;
        const onlineCount = Array.from(this.switches.values()).filter(s => s.status === 'online').length;
        const errorCount = Array.from(this.switches.values()).filter(s => s.status === 'error').length;
        const systemHealth = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;

        // Update dashboard stats
        const totalEl = document.getElementById('total-switches');
        const onlineEl = document.getElementById('online-switches');
        const errorEl = document.getElementById('error-switches');
        const healthEl = document.getElementById('system-health');

        if (totalEl) totalEl.textContent = totalCount;
        if (onlineEl) onlineEl.textContent = onlineCount;
        if (errorEl) errorEl.textContent = errorCount;
        if (healthEl) healthEl.textContent = `${systemHealth}%`;
    }

    updateNetworkStatus() {
        const container = document.getElementById('network-status-content');
        const switchStatusCard = document.getElementById('switch-status-card');
        const switchStatusList = document.getElementById('switch-status-list');
        
        if (!container) return;

        if (this.switches.size === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted-foreground">
                    <svg class="h-8 w-8 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/>
                    </svg>
                    <p>No switches configured</p>
                    <p class="text-xs">Add switches to get started</p>
                </div>
            `;
            if (switchStatusCard) switchStatusCard.style.display = 'none';
        } else {
            const onlineCount = Array.from(this.switches.values()).filter(s => s.status === 'online').length;
            const offlineCount = Array.from(this.switches.values()).filter(s => s.status === 'offline').length;
            const errorCount = Array.from(this.switches.values()).filter(s => s.status === 'error').length;

            let statusContent = '';
            
            if (onlineCount > 0) {
                statusContent += `
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <svg class="h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span>Online Switches</span>
                        </div>
                        <span class="status status-online">${onlineCount}</span>
                    </div>
                `;
            }
            
            if (offlineCount > 0) {
                statusContent += `
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <svg class="h-5 w-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span>Offline Switches</span>
                        </div>
                        <span class="status status-offline">${offlineCount}</span>
                    </div>
                `;
            }
            
            if (errorCount > 0) {
                statusContent += `
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <svg class="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
                            </svg>
                            <span>Error Switches</span>
                        </div>
                        <span class="status status-error">${errorCount}</span>
                    </div>
                `;
            }

            container.innerHTML = `<div class="space-y-4">${statusContent}</div>`;

            // Update switch status list
            if (switchStatusCard && switchStatusList) {
                const switches = Array.from(this.switches.values()).slice(0, 4);
                const switchItems = switches.map(switch_ => `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            ${this.getStatusIcon(switch_.status)}
                            <div>
                                <div class="font-medium">${switch_.name || switch_.ip_address}</div>
                                <div class="text-sm text-muted-foreground">
                                    ${switch_.ip_address}${switch_.model ? ` • ${switch_.model}` : ''}
                                </div>
                            </div>
                        </div>
                        <div class="text-right">
                            <span class="status status-${switch_.status}">${switch_.status}</span>
                            ${switch_.last_seen ? `
                                <div class="text-xs text-muted-foreground mt-1">
                                    ${new Date(switch_.last_seen).toLocaleTimeString()}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `).join('');

                switchStatusList.innerHTML = switchItems;
                switchStatusCard.style.display = 'block';
            }
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'online':
                return '<svg class="h-4 w-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>';
            case 'error':
                return '<svg class="h-4 w-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>';
            default:
                return '<svg class="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>';
        }
    }

    startHealthMonitoring() {
        // Auto-refresh every 30 seconds
        setInterval(() => {
            if (!this.isLoading) {
                this.loadSwitches();
            }
        }, 30000);
    }

    refreshAllSwitches() {
        this.showAlert('Refreshing all switches...', 'info');
        
        // Refresh each switch individually
        const promises = Array.from(this.switches.keys()).map(switchIp => 
            this.refreshSwitch(switchIp)
        );
        
        Promise.allSettled(promises).then(() => {
            this.showAlert('Refresh completed', 'success');
        });
    }

    async exportConfiguration() {
        try {
            const response = await fetch('/api/config/export');
            const config = await response.json();
            
            // Create download for mobile
            const dataStr = JSON.stringify(config, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            
            // Use mobile-friendly download approach
            if (navigator.share) {
                // Use Web Share API if available
                const file = new File([dataBlob], `aoscx-config-${new Date().toISOString().split('T')[0]}.json`, {
                    type: 'application/json'
                });
                
                await navigator.share({
                    files: [file],
                    title: 'AOS-CX Configuration Export'
                });
            } else {
                // Fallback to traditional download
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `aoscx-config-${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }
            
            this.showAlert('Configuration exported successfully', 'success');
        } catch (error) {
            this.showAlert('Error exporting configuration: ' + error.message, 'error');
        }
    }

    updateLastRefreshDisplay() {
        const element = document.getElementById('last-refresh');
        if (element) {
            element.textContent = this.lastRefresh.toLocaleTimeString();
        }
    }

    showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alert-container');
        if (!alertContainer) {
            console.log(`${type.toUpperCase()}: ${message}`);
            return;
        }

        // Remove any existing alerts to show only one at a time
        alertContainer.innerHTML = '';

        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" class="btn-outline btn-sm ml-auto" style="min-height: 24px; padding: 0.25rem 0.5rem;">×</button>
        `;

        alertContainer.appendChild(alert);

        // Auto-remove after 3 seconds (faster)
        setTimeout(() => {
            if (alert.parentElement) {
                alert.style.animation = 'slideUp 0.3s ease-out reverse';
                setTimeout(() => {
                    if (alert.parentElement) {
                        alert.remove();
                    }
                }, 300);
            }
        }, 3000);
    }

    setButtonLoading(buttonId, loading) {
        const button = document.getElementById(buttonId);
        if (!button) return;

        if (loading) {
            button.disabled = true;
            button.innerHTML = '<div class="loading mr-2"></div> Loading...';
        } else {
            button.disabled = false;
            // Restore original text
            const originalTexts = {
                'add-switch-btn': 'Add Switch',
                'list-vlans-btn': 'List VLANs',
                'create-vlan-btn': 'Create VLAN'
            };
            button.innerHTML = originalTexts[buttonId] || 'Submit';
        }
    }

    setGlobalLoading(loading) {
        this.isLoading = loading;
        const refreshBtn = document.getElementById('refresh-all-btn');
        if (refreshBtn) {
            const icon = refreshBtn.querySelector('svg');
            if (icon) {
                if (loading) {
                    icon.classList.add('animate-spin');
                } else {
                    icon.classList.remove('animate-spin');
                }
            }
        }
    }

    isValidIP(ip) {
        const regex = /^(\d{1,3}\.){3}\d{1,3}$/;
        if (!regex.test(ip)) return false;
        
        return ip.split('.').every(octet => {
            const num = parseInt(octet);
            return num >= 0 && num <= 255;
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Set viewport height for mobile
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
    
    // Initialize mobile dashboard
    window.dashboard = new MobileDashboard();
    
    // Add to window for backward compatibility
    window.dashboard.showTab = window.dashboard.showTab.bind(window.dashboard);
    window.dashboard.refreshAllSwitches = window.dashboard.refreshAllSwitches.bind(window.dashboard);
    window.dashboard.exportConfiguration = window.dashboard.exportConfiguration.bind(window.dashboard);
});