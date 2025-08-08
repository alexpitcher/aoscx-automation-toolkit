/**
 * Mobile-First AOS-CX Automation Toolkit Dashboard JavaScript
 * Enhanced version with mobile-optimized navigation and responsive design
 */

class MobileDashboard {
    constructor() {
        this.switches = new Map();
        this.currentSwitch = null;
        this.selectedSwitch = null;
        this.activeTab = 'dashboard';
        this.lastRefresh = new Date();
        this.isLoading = false;
        this.interfacesReqToken = 0;
        this.portMapReqToken = 0;
        this.changeBound = false;
        this.init();
    }

    init() {
        this.setupMobileNavigation();
        this.setupEventListeners();
        this.setupManageSubNavigation();
        this.setupToggleSwitches();
        this.setupSettingsModal();
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
        if (tabName === 'onboard') {
            this.loadSwitches();
        } else if (tabName === 'manage') {
            this.updateManageSwitchSelector();
        } else if (tabName === 'vlans') {
            this.updateSwitchSelector();
            if (this.currentSwitch) {
                this.loadVlansForCurrentSwitch();
            }
        } else if (tabName === 'logs') {
            this.loadApiLogs();
            this.updateLogsFilterSwitches();
        }
    }

    setupEventListeners() {
        // Add switch form
        const addSwitchForm = document.getElementById('add-switch-form');
        if (addSwitchForm) {
            addSwitchForm.addEventListener('submit', (e) => this.handleAddSwitch(e));
        }

        // Connection type radio buttons
        const connectionTypeRadios = document.querySelectorAll('input[name="connection_type"]');
        connectionTypeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => this.handleConnectionTypeChange(e));
        });

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

        // Logs tab event listeners
        const refreshLogsBtn = document.getElementById('refresh-logs');
        if (refreshLogsBtn) {
            refreshLogsBtn.addEventListener('click', () => this.loadApiLogs());
        }

        const clearLogsBtn = document.getElementById('clear-logs');
        if (clearLogsBtn) {
            clearLogsBtn.addEventListener('click', () => this.clearApiLogs());
        }

        // Logs filter event listeners
        const logFilterSwitch = document.getElementById('log-filter-switch');
        const logFilterCategory = document.getElementById('log-filter-category');
        const logFilterStatus = document.getElementById('log-filter-status');
        
        [logFilterSwitch, logFilterCategory, logFilterStatus].forEach(filter => {
            if (filter) {
                filter.addEventListener('change', () => this.loadApiLogs());
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

    handleConnectionTypeChange(event) {
        const connectionType = event.target.value;
        const directFields = document.getElementById('direct-connection-fields');
        const centralFields = document.getElementById('central-connection-fields');
        const credentialsSection = document.querySelector('.form-group:has(#toggle-credentials)');
        
        if (connectionType === 'central') {
            directFields.style.display = 'none';
            centralFields.style.display = 'block';
            if (credentialsSection) credentialsSection.style.display = 'none';
        } else {
            directFields.style.display = 'block';
            centralFields.style.display = 'none';
            if (credentialsSection) credentialsSection.style.display = 'block';
        }
    }

    async handleAddSwitch(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const connectionType = formData.get('connection_type') || 'direct';
        const switchName = formData.get('switch_name');

        try {
            this.setButtonLoading('add-switch-btn', true);
            
            let requestBody = { 
                connection_type: connectionType,
                name: switchName 
            };

            if (connectionType === 'central') {
                // Central connection fields
                const deviceSerial = formData.get('device_serial');
                const clientId = formData.get('client_id');
                const clientSecret = formData.get('client_secret');
                const customerId = formData.get('customer_id');
                const baseUrl = formData.get('base_url');

                // Validation for Central fields
                if (!deviceSerial || !clientId || !clientSecret || !customerId) {
                    this.showAlert('Please fill in all required Central connection fields', 'error');
                    return;
                }

                requestBody = {
                    ...requestBody,
                    device_serial: deviceSerial,
                    client_id: clientId,
                    client_secret: clientSecret,
                    customer_id: customerId,
                    base_url: baseUrl || 'https://apigw-prod2.central.arubanetworks.com'
                };
            } else {
                // Direct connection fields
                const switchIp = formData.get('switch_ip');
                const username = formData.get('switch_username');
                const password = formData.get('switch_password');

                if (!this.isValidIP(switchIp)) {
                    this.showAlert('Please enter a valid IP address', 'error');
                    return;
                }

                requestBody = {
                    ...requestBody,
                    ip_address: switchIp
                };
                
                // Only include credentials if provided
                if (username && username.trim()) {
                    requestBody.username = username.trim();
                }
                if (password) {
                    requestBody.password = password;
                }
            }
            
            const response = await fetch('/api/switches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const data = await response.json();
            
            if (response.ok) {
                const switchKey = data.switch.ip_address;
                this.switches.set(switchKey, data.switch);
                this.renderSwitches();
                this.updateSwitchSelector();
                this.updateDashboardStats();
                this.showAlert(data.message, 'success');
                event.target.reset();
                
                // Reset form state
                this.handleConnectionTypeChange({ target: { value: 'direct' } });
                document.querySelector('input[name="connection_type"][value="direct"]').checked = true;
                
                // Hide credentials section after successful add
                const credentialsSection = document.getElementById('credentials-section');
                const toggleText = document.getElementById('cred-toggle-text');
                if (credentialsSection && toggleText) {
                    credentialsSection.style.display = 'none';
                    toggleText.textContent = 'Show Credentials';
                }
                
                // Test connection immediately
                this.refreshSwitch(switchKey);
                
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
                } else {
                    // Use enhanced error handling for structured API responses
                    this.handleApiError(response, data);
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

    // Enhanced error handling for structured API responses
    handleApiError(response, data) {
        const errorType = data.error_type || 'unknown_error';
        const switchIp = data.switch_ip;
        
        // Handle HTTP status code-specific errors
        if (response.status === 429) {
            this.showErrorModal(
                'Session Limit Reached', 
                data.error || 'Session limit reached, please wait or clean sessions',
                data.suggestion || 'This typically resolves in 5-10 minutes.',
                ['cleanup', 'retry'],
                switchIp
            );
            return;
        }
        
        if (response.status === 401 && !data.error_type) {
            this.showAlert('Incorrect username or password', 'error');
            return;
        }
        
        const errorMessages = {
            'session_limit': {
                title: 'Session Limit Reached',
                message: 'Switch session limit reached. This typically resolves in 5-10 minutes.',
                actions: ['cleanup', 'retry']
            },
            'invalid_credentials': {
                title: 'Invalid Credentials',
                message: 'Username or password is incorrect.',
                actions: ['retry']
            },
            'connection_timeout': {
                title: 'Connection Failed',
                message: 'Cannot reach switch. Check IP address and network connectivity.',
                actions: ['retry']
            },
            'permission_denied': {
                title: 'Permission Denied',
                message: 'User lacks required admin privileges.',
                actions: ['retry']
            },
            'api_unavailable': {
                title: 'API Unavailable',
                message: 'Switch REST API is not properly configured.',
                actions: []
            },
            'central_managed': {
                title: 'Central Managed',
                message: 'Switch is managed by Aruba Central.',
                actions: []
            }
        };
        
        const errorConfig = errorMessages[errorType] || {
            title: 'Unknown Error',
            message: data.error || 'An unexpected error occurred.',
            actions: ['retry']
        };
        
        // Show specialized error dialog for certain error types
        if (errorType === 'session_limit') {
            this.showSessionLimitDialog(data);
        } else {
            this.showErrorDialog(errorConfig.title, errorConfig.message, data.suggestion, errorConfig.actions, switchIp);
        }
    }
    
    showSessionLimitDialog(errorData) {
        const switchIp = errorData.switch_ip;
        const modal = this.createModal('Session Limit Reached', `
            <div class="error-dialog">
                <div class="error-icon">WARNING</div>
                <p><strong>Switch ${switchIp} has reached its session limit.</strong></p>
                <p>${errorData.suggestion || 'This typically resolves automatically within 5-10 minutes.'}</p>
                <div class="session-limit-actions">
                    <button class="btn btn-primary" onclick="dashboard.attemptSessionCleanup('${switchIp}')">
                        Clean Sessions
                    </button>
                    <button class="btn btn-secondary" onclick="dashboard.retryConnection('${switchIp}')">
                        Retry
                    </button>
                    <button class="btn btn-secondary" onclick="dashboard.closeModal()">
                        Wait
                    </button>
                </div>
                <div class="countdown-timer" id="session-retry-timer" style="display: none;">
                    <p>Retrying in: <span id="countdown-seconds">30</span> seconds</p>
                </div>
            </div>
        `);
        modal.show();
    }
    
    showErrorDialog(title, message, suggestion, actions, switchIp) {
        const actionButtons = actions.map(action => {
            switch(action) {
                case 'retry':
                    return `<button class="btn btn-primary" onclick="dashboard.retryLastAction()">
                        Retry
                    </button>`;
                case 'cleanup':
                    return `<button class="btn btn-secondary" onclick="dashboard.attemptSessionCleanup('${switchIp}')">
                        Clean Sessions
                    </button>`;
                default:
                    return '';
            }
        }).join('');
        
        const modal = this.createModal(title, `
            <div class="error-dialog">
                <div class="error-icon">ERROR</div>
                <p><strong>${message}</strong></p>
                ${suggestion ? `<p class="suggestion">${suggestion}</p>` : ''}
                <div class="error-actions">
                    ${actionButtons}
                    <button class="btn btn-secondary" onclick="dashboard.closeModal()">Close</button>
                </div>
            </div>
        `);
        modal.show();
    }
    
    async attemptSessionCleanup(switchIp) {
        try {
            this.showLoadingSpinner('Cleaning up sessions...');
            
            const response = await fetch(`/api/switches/${switchIp}/cleanup-sessions`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(data.message || 'Session cleanup completed', 'success');
                this.closeModal();
                
                // Auto-retry after cleanup
                setTimeout(() => {
                    this.retryLastAction();
                }, 2000);
            } else {
                this.showAlert(data.error || 'Session cleanup failed', 'error');
            }
        } catch (error) {
            this.showAlert('Error during session cleanup: ' + error.message, 'error');
        } finally {
            this.hideLoadingSpinner();
        }
    }
    
    retryConnection(switchIp) {
        this.closeModal();
        // Trigger the add switch form submission again
        const form = document.getElementById('add-switch-form');
        if (form) {
            form.dispatchEvent(new Event('submit'));
        }
    }
    
    retryLastAction() {
        this.closeModal();
        // This would retry the last failed action
        // For now, just show a message to manually retry
        this.showAlert('Please try your action again', 'info');
    }
    
    createModal(title, content) {
        // Remove existing modal if any
        const existingModal = document.querySelector('.error-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.className = 'error-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="dashboard.closeModal()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="modal-close" onclick="dashboard.closeModal()">&times;</button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        return {
            show: () => modal.style.display = 'flex',
            hide: () => modal.style.display = 'none'
        };
    }
    
    closeModal() {
        const modal = document.querySelector('.error-modal');
        if (modal) {
            modal.remove();
        }
    }
    
    showLoadingSpinner(message) {
        const spinner = document.createElement('div');
        spinner.id = 'loading-spinner';
        spinner.innerHTML = `
            <div class="spinner-overlay">
                <div class="spinner">
                    <div class="spinner-icon">Loading...</div>
                    <div class="spinner-message">${message}</div>
                </div>
            </div>
        `;
        document.body.appendChild(spinner);
    }
    
    hideLoadingSpinner() {
        const spinner = document.getElementById('loading-spinner');
        if (spinner) {
            spinner.remove();
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
    
    showRetryButton(sectionId, message, retryCallback) {
        const section = document.getElementById(sectionId);
        if (!section) {
            console.error(`Section ${sectionId} not found for retry button`);
            return;
        }
        
        // Remove any existing retry banners
        const existingRetry = section.querySelector('.retry-banner');
        if (existingRetry) {
            existingRetry.remove();
        }
        
        // Create retry banner
        const retryBanner = document.createElement('div');
        retryBanner.className = 'retry-banner';
        retryBanner.innerHTML = `
            <div class="alert alert-warning" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
                <span>${message}</span>
                <button class="btn btn-primary btn-sm retry-btn">
                    Retry
                </button>
            </div>
        `;
        
        // Add proper event listener to retry button
        const retryBtn = retryBanner.querySelector('.retry-btn');
        if (retryBtn && retryCallback) {
            retryBtn.addEventListener('click', (e) => {
                e.preventDefault();
                retryBanner.remove();
                try {
                    retryCallback.call(this);
                } catch (error) {
                    console.error('Error in retry callback:', error);
                    this.showAlert('Error retrying operation: ' + error.message, 'error');
                }
            });
        }
        
        // Insert at the top of the section
        section.insertBefore(retryBanner, section.firstChild);
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

    // API Logs functionality
    async loadApiLogs() {
        try {
            this.setButtonLoading('refresh-logs', true);
            
            // Get filter values
            const switchIp = document.getElementById('log-filter-switch')?.value || '';
            const category = document.getElementById('log-filter-category')?.value || '';
            const successOnly = document.getElementById('log-filter-status')?.value || '';
            
            // Build query parameters
            const params = new URLSearchParams();
            params.append('limit', '50');
            if (switchIp) params.append('switch_ip', switchIp);
            if (category) params.append('category', category);
            if (successOnly) params.append('success_only', successOnly);
            
            const response = await fetch(`/api/logs/calls?${params.toString()}`);
            const data = await response.json();
            
            if (response.ok) {
                this.renderApiLogs(data.calls);
                this.updateLogsStatistics(data.statistics);
            } else {
                this.showAlert('Error loading API logs: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error loading API logs:', error);
            this.showAlert('Error loading API logs: ' + error.message, 'error');
        } finally {
            this.setButtonLoading('refresh-logs', false);
        }
    }

    renderApiLogs(calls) {
        const container = document.getElementById('logs-list');
        if (!container) return;
        
        if (!calls || calls.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-muted-foreground">
                    <svg class="h-12 w-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <p class="font-medium">No API calls logged yet</p>
                    <p class="text-sm">API calls will appear here as you interact with switches</p>
                </div>
            `;
            return;
        }
        
        // Sort calls by timestamp (most recent first)
        const sortedCalls = [...calls].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        const logsHtml = sortedCalls.map(call => `
            <div class="log-entry ${call.success ? 'success' : 'error'}">
                <div class="log-header">
                    <span class="method ${call.method.toLowerCase()}">${call.method}</span>
                    <span class="url" title="${call.url}">${this.shortenUrl(call.url)}</span>
                    <span class="status-code status-${Math.floor(call.response_code/100)}">${call.response_code}</span>
                    <span class="duration">${call.duration_ms.toFixed(0)}ms</span>
                </div>
                <div class="log-time">${this.formatTimestamp(call.timestamp)} - ${call.switch_ip || 'unknown'}</div>
                <div class="log-details">
                    <details>
                        <summary>Request Details</summary>
                        <pre>${this.formatRequestData(call)}</pre>
                    </details>
                    <details>
                        <summary>Response Details</summary>
                        <pre>${this.formatResponseData(call)}</pre>
                    </details>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = logsHtml;
    }

    updateLogsStatistics(stats) {
        const totalCalls = document.getElementById('total-calls');
        const successCalls = document.getElementById('success-calls');
        const failedCalls = document.getElementById('failed-calls');
        
        if (totalCalls) totalCalls.textContent = stats.total_calls || 0;
        if (successCalls) successCalls.textContent = stats.successful_calls || 0;
        if (failedCalls) failedCalls.textContent = stats.failed_calls || 0;
    }

    updateLogsFilterSwitches() {
        const switchFilter = document.getElementById('log-filter-switch');
        if (!switchFilter) return;
        
        // Get unique switches from current inventory
        const switches = Array.from(this.switches.values());
        const switchOptions = switches.map(sw => 
            `<option value="${sw.ip_address}">${sw.name || sw.ip_address}</option>`
        ).join('');
        
        switchFilter.innerHTML = `<option value="">All Switches</option>${switchOptions}`;
    }

    async clearApiLogs() {
        try {
            const confirmed = confirm('Are you sure you want to clear all API logs? This action cannot be undone.');
            if (!confirmed) return;
            
            this.setButtonLoading('clear-logs', true);
            
            const response = await fetch('/api/logs/clear', { method: 'POST' });
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(`Cleared ${data.cleared_entries} log entries`, 'success');
                this.loadApiLogs(); // Refresh the display
            } else {
                this.showAlert('Error clearing logs: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error clearing API logs:', error);
            this.showAlert('Error clearing logs: ' + error.message, 'error');
        } finally {
            this.setButtonLoading('clear-logs', false);
        }
    }

    // Helper methods for logs display
    shortenUrl(url) {
        try {
            const urlObj = new URL(url);
            const path = urlObj.pathname + urlObj.search;
            return path.length > 50 ? path.substring(0, 47) + '...' : path;
        } catch {
            return url.length > 50 ? url.substring(0, 47) + '...' : url;
        }
    }

    // New methods for Central-like experience
    setupManageSubNavigation() {
        const subnavBtns = document.querySelectorAll('.subnav-btn');
        subnavBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const section = btn.dataset.section;
                this.showManageSection(section);
            });
        });
        
        // Initialize with overview section
        this.showManageSection('overview');
    }
    
    showManageSection(sectionName) {
        // Remove active class from all subnav buttons
        const subnavBtns = document.querySelectorAll('.subnav-btn');
        subnavBtns.forEach(btn => btn.classList.remove('active'));
        
        // Hide all manage sections
        const sections = document.querySelectorAll('.manage-section');
        sections.forEach(section => section.classList.remove('active'));
        
        // Show selected section and activate button
        const selectedBtn = document.querySelector(`[data-section="${sectionName}"]`);
        const selectedSection = document.getElementById(`${sectionName}-section`);
        
        if (selectedBtn) selectedBtn.classList.add('active');
        if (selectedSection) selectedSection.classList.add('active');
        
        // Load data for specific sections
        if (sectionName === 'overview') {
            this.loadDeviceOverview();
        } else if (sectionName === 'vlans') {
            this.loadVlansForManage();
        } else if (sectionName === 'interfaces') {
            this.loadInterfacesForManage();
        }
    }
    
    setupToggleSwitches() {
        const toggleOptions = document.querySelectorAll('.toggle-option');
        toggleOptions.forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Remove active class from siblings
                const container = option.parentElement;
                container.querySelectorAll('.toggle-option').forEach(opt => 
                    opt.classList.remove('active')
                );
                
                // Add active class to clicked option
                option.classList.add('active');
                
                // Update hidden input
                const value = option.dataset.value;
                const hiddenInput = document.getElementById('connection-type');
                if (hiddenInput) {
                    hiddenInput.value = value;
                }
                
                // Handle connection type change
                this.handleConnectionTypeToggle(value);
            });
        });
    }
    
    handleConnectionTypeToggle(type) {
        const directFields = document.getElementById('direct-connection-fields');
        const centralFields = document.getElementById('central-connection-fields');
        
        if (type === 'central') {
            if (directFields) directFields.style.display = 'none';
            if (centralFields) centralFields.style.display = 'block';
        } else {
            if (directFields) directFields.style.display = 'block';
            if (centralFields) centralFields.style.display = 'none';
        }
    }
    
    setupSettingsModal() {
        const settingsBtn = document.getElementById('settings-btn');
        const settingsModal = document.getElementById('settings-modal');
        const settingsClose = document.getElementById('settings-close');
        
        if (settingsBtn && settingsModal) {
            settingsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                settingsModal.classList.add('active');
            });
        }
        
        if (settingsClose && settingsModal) {
            settingsClose.addEventListener('click', (e) => {
                e.preventDefault();
                settingsModal.classList.remove('active');
            });
        }
        
        // Close modal on backdrop click
        if (settingsModal) {
            settingsModal.addEventListener('click', (e) => {
                if (e.target === settingsModal) {
                    settingsModal.classList.remove('active');
                }
            });
        }
    }
    
    async loadDeviceOverview() {
        const selectedSwitch = document.getElementById('manage-switch-selector').value;
        if (!selectedSwitch) {
            this.updateDeviceInfo({});
            return;
        }
        
        try {
            console.log(`Loading device overview for ${selectedSwitch}`);
            
            const response = await fetch(`/api/switches/${selectedSwitch}/overview`);
            const data = await response.json();
            
            if (response.ok) {
                console.log('Device overview data:', data);
                this.updateDeviceInfo({
                    model: data.model || 'Unknown',
                    portCount: data.port_count || '0',
                    poeStatus: data.poe_status || 'unknown',
                    powerStatus: data.power_status || 'unknown',
                    fanStatus: data.fan_status || 'unknown',
                    cpuUsage: data.cpu_usage,
                    cpuStatus: data.cpu_status || 'unknown',
                    health: data.health
                });
            } else {
                console.error('Failed to load device overview:', data.error);
                this.showRetryButton('overview-section', 'Failed to load device overview. ', () => this.loadDeviceOverview());
                this.updateDeviceInfo({
                    model: 'Error loading device info',
                    portCount: 'Unknown',
                    poeStatus: 'unknown',
                    powerStatus: 'unknown', 
                    fanStatus: 'unknown',
                    cpuUsage: 0
                });
            }
        } catch (error) {
            console.error('Error loading device overview:', error);
            this.showRetryButton('overview-section', 'Network error loading device overview. ', () => this.loadDeviceOverview());
            this.updateDeviceInfo({
                model: 'Network Error',
                portCount: 'Unknown',
                poeStatus: 'unknown',
                powerStatus: 'unknown', 
                fanStatus: 'unknown',
                cpuUsage: 0
            });
        }
    }
    
    updateDeviceInfo(info) {
        const elements = {
            'device-model': info.model || '--',
            'device-ports': info.portCount || '--',
            'poe-status': this.formatPoEStatus(info.poeStatus),
            'power-status': this.formatStatus(info.powerStatus),
            'fan-status': this.formatStatus(info.fanStatus)
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                
                // Add status classes
                if (id.includes('status')) {
                    element.className = 'info-value status-indicator';
                    const status = id === 'poe-status' ? info.poeStatus : 
                                  id === 'power-status' ? info.powerStatus :
                                  id === 'fan-status' ? info.fanStatus : 'unknown';
                    
                    if (status === 'ok') {
                        element.classList.add('online');
                    } else if (status === 'error') {
                        element.classList.add('offline');
                    } else if (status === 'warning') {
                        element.classList.add('warning');
                    } else if (status === 'na') {
                        element.classList.add('na');
                    }
                }
            }
        });
        
        // Update health status badge
        this.updateHealthBadge(info.health);
        
        // Update CPU usage display
        this.updateCPUDisplay(info.cpuUsage, info.cpuStatus);
    }
    
    formatPoEStatus(status) {
        if (status === 'na') return 'N/A';
        if (status === 'ok') return 'Online';
        if (status === 'error') return 'Error';
        if (status === 'warning') return 'Warning';
        return 'Unknown';
    }
    
    formatStatus(status) {
        if (status === 'na') return 'N/A';
        if (status === 'ok') return 'OK';
        if (status === 'error') return 'Error';
        if (status === 'warning') return 'Warning';
        return 'Unknown';
    }
    
    updateHealthBadge(health) {
        const healthBadge = document.getElementById('device-health-badge');
        const healthReasons = document.getElementById('device-health-reasons');
        
        if (!healthBadge) return;
        
        // Clear existing classes
        healthBadge.classList.remove('badge-success', 'badge-warning', 'badge-error');
        
        if (!health) {
            healthBadge.textContent = 'Unknown';
            healthBadge.classList.add('badge-secondary');
            if (healthReasons) healthReasons.textContent = '';
            return;
        }
        
        // Set badge text and color
        healthBadge.textContent = health.status;
        
        if (health.status === 'ONLINE') {
            healthBadge.classList.add('badge-success');
        } else if (health.status === 'DEGRADED') {
            healthBadge.classList.add('badge-warning');
        } else if (health.status === 'ERRORS') {
            healthBadge.classList.add('badge-error');
        }
        
        // Update reasons
        if (healthReasons) {
            if (health.reasons && health.reasons.length > 0) {
                const displayReasons = health.reasons.slice(0, 3);
                const moreCount = health.reasons.length - 3;
                let reasonsText = displayReasons.join(', ');
                if (moreCount > 0) {
                    reasonsText += `, +${moreCount} more`;
                }
                healthReasons.textContent = reasonsText;
            } else {
                healthReasons.textContent = '';
            }
        }
    }
    
    updateCPUDisplay(usage, status) {
        const cpuBar = document.getElementById('cpu-bar');
        const cpuText = document.getElementById('cpu-text');
        
        if (status === 'na' || usage === null || usage === undefined) {
            // CPU not supported
            if (cpuBar) cpuBar.style.display = 'none';
            if (cpuText) cpuText.textContent = 'N/A';
        } else {
            // CPU supported, show actual usage
            if (cpuBar) {
                cpuBar.style.display = 'block';
                cpuBar.style.setProperty('--cpu-width', `${usage}%`);
                
                // Color based on usage level
                let color = 'var(--success)';
                if (usage > 90) color = 'var(--destructive)';
                else if (usage > 75) color = 'var(--warning)';
                
                cpuBar.style.background = `linear-gradient(90deg, ${color} ${usage}%, var(--muted) ${usage}%)`;
            }
            if (cpuText) cpuText.textContent = `${usage}%`;
        }
    }
    
    async loadVlansForManage() {
        const selectedSwitch = document.getElementById('manage-switch-selector').value;
        if (!selectedSwitch) {
            this.updateVlansList([]);
            return;
        }
        
        try {
            console.log(`Loading VLANs for ${selectedSwitch}`);
            
            const response = await fetch(`/api/switches/${selectedSwitch}/vlans`);
            const data = await response.json();
            
            if (response.ok) {
                console.log('VLANs data:', data);
                this.updateVlansList(data.vlans || []);
            } else {
                console.error('Failed to load VLANs:', data.error);
                this.showRetryButton('vlans-section', 'Failed to load VLANs. ', () => this.loadVlansForManage());
                this.updateVlansList([]);
            }
        } catch (error) {
            console.error('Error loading VLANs:', error);
            this.showRetryButton('vlans-section', 'Network error loading VLANs. ', () => this.loadVlansForManage());
            this.updateVlansList([]);
        }
    }
    
    updateVlansList(vlans) {
        const vlansList = document.getElementById('vlans-list');
        if (!vlansList) return;
        
        if (!vlans || vlans.length === 0) {
            vlansList.innerHTML = `
                <div class="text-center py-4 text-muted-foreground">
                    <p>No VLANs found</p>
                </div>
            `;
            return;
        }
        
        vlansList.innerHTML = vlans.map(vlan => `
            <div class="vlan-item">
                <div class="vlan-info">
                    <div class="vlan-id">VLAN ${vlan.id}</div>
                    <div class="vlan-name">${vlan.name || 'Unnamed'}</div>
                </div>
                <div class="interface-actions">
                    <button class="edit-btn" onclick="dashboard.editVlan(${vlan.id})" title="Edit VLAN">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    parseIfName(ifname) {
        // Parse interface name like "1/1/10" -> [1,1,10] for natural sorting
        const parts = ifname.replace(/^.*?(\d+\/\d+\/\d+).*$/, '$1').split('/');
        return parts.length === 3 ? parts.map(Number) : [0, 0, 0];
    }
    
    normalizeInterface(iface) {
        // Normalize interface objects to common shape
        return {
            name: iface.name,
            admin_state: iface.admin_state || 'unknown',
            link_state: iface.link_state || 'unknown',
            link_speed: iface.link_speed || iface.speed || 0,
            type: iface.type || 'unknown',
            description: iface.description || '',
            mtu: iface.mtu || 0,
            status: iface.status || (iface.admin_state === 'up' && iface.link_state === 'up' ? 'up' : 
                    iface.admin_state === 'down' ? 'disabled' : 'down')
        };
    }
    
    async loadInterfacesForManage() {
        const selectedSwitch = document.getElementById('manage-switch-selector').value;
        if (!selectedSwitch) {
            this.updateInterfacesList([]);
            return;
        }
        
        // Increment token for race protection
        const currentToken = ++this.interfacesReqToken;
        
        try {
            console.log(`Loading interfaces for ${selectedSwitch} (token: ${currentToken})`);
            
            const response = await fetch(`/api/switches/${selectedSwitch}/interfaces`);
            const data = await response.json();
            
            // Check if this response is still relevant
            if (currentToken !== this.interfacesReqToken) {
                console.log(`Discarding stale interfaces response (token: ${currentToken})`);
                return;
            }
            
            if (response.ok) {
                console.log('Interfaces data:', data);
                let interfaces = (data.interfaces || []).map(iface => this.normalizeInterface(iface));
                
                // Sort interfaces naturally
                interfaces.sort((a, b) => {
                    const partsA = this.parseIfName(a.name);
                    const partsB = this.parseIfName(b.name);
                    
                    for (let i = 0; i < 3; i++) {
                        if (partsA[i] !== partsB[i]) {
                            return partsA[i] - partsB[i];
                        }
                    }
                    return a.name.localeCompare(b.name);
                });
                
                this.updateInterfacesList(interfaces);
            } else {
                console.error('Failed to load interfaces:', data.error);
                this.showRetryButton('interfaces-section', 'Failed to load interfaces. ', () => this.loadInterfacesForManage());
                this.updateInterfacesList([]);
            }
        } catch (error) {
            // Check if this response is still relevant
            if (currentToken !== this.interfacesReqToken) {
                return;
            }
            
            console.error('Error loading interfaces:', error);
            this.showRetryButton('interfaces-section', 'Network error loading interfaces. ', () => this.loadInterfacesForManage());
            this.updateInterfacesList([]);
        }
    }
    
    updateInterfacesList(interfaces) {
        const interfacesList = document.getElementById('interfaces-list');
        if (!interfacesList) return;
        
        if (!interfaces || interfaces.length === 0) {
            interfacesList.innerHTML = `
                <div class="text-center py-4 text-muted-foreground">
                    <p>No interfaces found</p>
                </div>
            `;
            return;
        }
        
        interfacesList.innerHTML = interfaces.map(iface => `
            <div class="interface-item">
                <div class="interface-info">
                    <div class="interface-name">${iface.name}</div>
                    <div class="interface-status ${iface.status}">
                        <span class="status-indicator ${iface.status}">
                            ${iface.status.toUpperCase()}
                        </span>
                        <span>${iface.description || 'No description'}</span>
                    </div>
                </div>
                <div class="interface-actions">
                    <button class="edit-btn" onclick="dashboard.editInterface('${iface.name}')" title="Edit Interface">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    updatePortMap(interfaces) {
        const portMap = document.getElementById('port-map');
        if (!portMap || !interfaces || interfaces.length === 0) {
            if (portMap) {
                portMap.innerHTML = `
                    <div class="text-center py-4 text-muted-foreground">
                        <p>Select a switch to view port map</p>
                    </div>
                `;
            }
            return;
        }
        
        const portCount = interfaces.length;
        const gridClass = portCount <= 24 ? 'port-grid-24' : 'port-grid-48';
        
        portMap.className = `port-map ${gridClass}`;
        portMap.innerHTML = interfaces.map((iface, index) => {
            const portNum = index + 1;
            return `
                <div class="port-indicator ${iface.status}" 
                     title="${iface.name} - ${iface.status.toUpperCase()}"
                     onclick="dashboard.editInterface('${iface.name}')">
                    ${portNum}
                </div>
            `;
        }).join('');
    }
    
    async updateManageSwitchSelector() {
        const selector = document.getElementById('manage-switch-selector');
        if (!selector) return;
        
        try {
            // Fetch switches from API
            const response = await fetch('/api/switches');
            const data = await response.json();
            
            if (response.ok && data.switches) {
                // Clear existing options
                selector.innerHTML = '<option value="">Select a switch...</option>';
                
                // Add switches to selector
                data.switches.forEach(switchInfo => {
                    const option = document.createElement('option');
                    option.value = switchInfo.ip_address;
                    option.textContent = switchInfo.name ? `${switchInfo.name} (${switchInfo.ip_address})` : switchInfo.ip_address;
                    selector.appendChild(option);
                });
                
                // Update internal switches map
                this.switches.clear();
                data.switches.forEach(switchInfo => {
                    this.switches.set(switchInfo.ip_address, switchInfo);
                });
                
            } else {
                console.error('Failed to load switches for selector:', data.error);
                selector.innerHTML = '<option value="">No switches available</option>';
            }
        } catch (error) {
            console.error('Error loading switches for selector:', error);
            selector.innerHTML = '<option value="">Error loading switches</option>';
        }
        
        // Add event listener for switch change (ensure single binding)
        if (!this.changeBound) {
            selector.addEventListener('change', this.handleManageSwitchChange.bind(this));
            this.changeBound = true;
        }
    }
    
    handleManageSwitchChange(event) {
        const selectedSwitch = event.target.value;
        this.selectedSwitch = selectedSwitch;
        this.currentSwitch = selectedSwitch; // Keep for backward compatibility
        
        if (selectedSwitch) {
            // Load all manage section data for the selected switch with slight delays to avoid session conflicts
            this.loadDeviceOverview();
            setTimeout(() => this.loadVlansForManage(), 100);
            setTimeout(() => this.loadInterfacesForManage(), 200);
            setTimeout(() => this.loadPortMap(), 300);
        } else {
            // Clear sections if no switch selected
            this.clearManageSections();
        }
    }
    
    clearManageSections() {
        // Clear overview info
        const overviewInfo = document.getElementById('overview-info');
        if (overviewInfo) {
            overviewInfo.innerHTML = '<p class="text-muted-foreground">Select a switch to view overview</p>';
        }
        
        // Clear VLANs list
        const vlansList = document.getElementById('vlans-list');
        if (vlansList) {
            vlansList.innerHTML = '<p class="text-muted-foreground">Select a switch to view VLANs</p>';
        }
        
        // Clear interfaces list
        const interfacesList = document.getElementById('interfaces-list');
        if (interfacesList) {
            interfacesList.innerHTML = '<p class="text-muted-foreground">Select a switch to view interfaces</p>';
        }
        
        // Clear port map
        const portMap = document.getElementById('port-map');
        if (portMap) {
            portMap.innerHTML = '<p class="text-muted-foreground">Select a switch to view port map</p>';
        }
    }
    
    async loadPortMap() {
        const selectedSwitch = document.getElementById('manage-switch-selector').value;
        const portMapContainer = document.getElementById('port-map');
        
        if (!selectedSwitch) {
            if (portMapContainer) {
                portMapContainer.innerHTML = '<p class="text-muted-foreground">Select a switch to view port map</p>';
            }
            return;
        }
        
        // Increment token for race protection
        const currentToken = ++this.portMapReqToken;
        
        if (portMapContainer) {
            portMapContainer.innerHTML = '<div class="text-center py-4"><div class="inline-flex items-center gap-2"><div class="loading-spinner"></div>Loading port map...</div></div>';
        }
        
        try {
            console.log(`Loading port map for ${selectedSwitch} (token: ${currentToken})`);
            
            const response = await fetch(`/api/switches/${selectedSwitch}/interfaces`);
            const data = await response.json();
            
            // Check if this response is still relevant
            if (currentToken !== this.portMapReqToken) {
                console.log(`Discarding stale port map response (token: ${currentToken})`);
                return;
            }
            
            if (response.ok && data.interfaces) {
                let interfaces = (data.interfaces || []).map(iface => this.normalizeInterface(iface));
                
                // Sort interfaces naturally
                interfaces.sort((a, b) => {
                    const partsA = this.parseIfName(a.name);
                    const partsB = this.parseIfName(b.name);
                    
                    for (let i = 0; i < 3; i++) {
                        if (partsA[i] !== partsB[i]) {
                            return partsA[i] - partsB[i];
                        }
                    }
                    return a.name.localeCompare(b.name);
                });
                
                this.renderPortMap(interfaces);
            } else {
                console.error('Failed to load port map:', data.error);
                this.showPortMapError('Failed to load port map');
            }
        } catch (error) {
            // Check if this response is still relevant
            if (currentToken !== this.portMapReqToken) {
                return;
            }
            
            console.error('Error loading port map:', error);
            this.showPortMapError('Network error loading port map');
        }
    }
    
    showPortMapError(message) {
        const portMapContainer = document.getElementById('port-map');
        if (portMapContainer) {
            portMapContainer.innerHTML = `
                <div class="text-center py-4 text-destructive">
                    <p>${message}</p>
                    <button class="retry-btn mt-2" onclick="dashboard.loadPortMap()">Retry</button>
                </div>
            `;
        }
    }
    
    renderPortMap(interfaces) {
        const portMapContainer = document.getElementById('port-map');
        if (!portMapContainer) return;
        
        // Clear container first to avoid duplicates
        portMapContainer.innerHTML = '';
        
        if (!interfaces || interfaces.length === 0) {
            portMapContainer.innerHTML = '<p class="text-center py-4 text-muted-foreground">No interfaces found</p>';
            return;
        }
        
        try {
            // Create a grid of ports with delegated event handling
            const portsHtml = interfaces.map(iface => {
                const statusClass = iface.status === 'up' ? 'port-up' : iface.status === 'disabled' ? 'port-disabled' : 'port-down';
                return `
                    <div class="port-indicator ${statusClass}" 
                         data-interface="${iface.name}" 
                         title="${iface.name}: ${iface.status} (${iface.description || 'No description'})">
                        <div class="port-number">${iface.name.replace('1/1/', '')}</div>
                        <div class="port-status-dot"></div>
                    </div>
                `;
            }).join('');
            
            portMapContainer.innerHTML = `
                <div class="port-map-grid" id="port-map-grid">
                    ${portsHtml}
                </div>
                <div class="port-legend mt-4">
                    <div class="legend-item">
                        <div class="legend-dot port-up"></div>
                        <span>Up</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot port-down"></div>
                        <span>Down</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot port-disabled"></div>
                        <span>Disabled</span>
                    </div>
                </div>
            `;
            
            // Setup delegated click handler for port indicators
            const gridContainer = document.getElementById('port-map-grid');
            if (gridContainer) {
                gridContainer.addEventListener('click', (e) => {
                    const portIndicator = e.target.closest('.port-indicator');
                    if (portIndicator && this.selectedSwitch) {
                        const interfaceName = portIndicator.dataset.interface;
                        if (interfaceName) {
                            this.editInterface(interfaceName);
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error rendering port map:', error);
            this.showPortMapError('Error displaying port map');
        }
    }
    
    // Edit methods for VLANs and interfaces
    editVlan(vlanId) {
        if (!this.selectedSwitch) {
            this.showAlert('Please select a switch first', 'error');
            return;
        }
        
        this.showVlanEditModal(vlanId);
    }
    
    showVlanEditModal(vlanId) {
        // Find current VLAN data
        const vlansList = document.getElementById('vlans-list');
        let currentVlan = { id: vlanId, name: '', description: '', admin_state: 'up' };
        
        // Try to extract current values from the DOM or cache
        if (vlansList) {
            const vlanItems = vlansList.querySelectorAll('.vlan-item');
            vlanItems.forEach(item => {
                const nameEl = item.querySelector('.vlan-name');
                const idEl = item.querySelector('.vlan-id');
                if (idEl && nameEl && idEl.textContent.includes(vlanId.toString())) {
                    currentVlan.name = nameEl.textContent || '';
                }
            });
        }
        
        const modalHtml = `
            <div class="modal-backdrop" onclick="dashboard.closeVlanEditModal()">
                <div class="modal-content" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Edit VLAN ${vlanId}</h3>
                        <button class="modal-close" onclick="dashboard.closeVlanEditModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="vlan-name-input">VLAN Name</label>
                            <input type="text" id="vlan-name-input" class="form-control" 
                                   value="${currentVlan.name}" placeholder="Enter VLAN name">
                        </div>
                        <div class="form-group">
                            <label for="vlan-desc-input">Description</label>
                            <input type="text" id="vlan-desc-input" class="form-control" 
                                   value="${currentVlan.description}" placeholder="Enter description (optional)">
                        </div>
                        <div class="form-group">
                            <label for="vlan-admin-input">Admin State</label>
                            <select id="vlan-admin-input" class="form-control">
                                <option value="up" ${currentVlan.admin_state === 'up' ? 'selected' : ''}>Up</option>
                                <option value="down" ${currentVlan.admin_state === 'down' ? 'selected' : ''}>Down</option>
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="dashboard.closeVlanEditModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="dashboard.saveVlanEdit(${vlanId})">Save</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Focus the name input
        setTimeout(() => {
            const nameInput = document.getElementById('vlan-name-input');
            if (nameInput) {
                nameInput.focus();
                nameInput.select();
            }
        }, 100);
    }
    
    closeVlanEditModal() {
        const modal = document.querySelector('.modal-backdrop');
        if (modal) {
            modal.remove();
        }
    }
    
    saveVlanEdit(vlanId) {
        const nameInput = document.getElementById('vlan-name-input');
        const descInput = document.getElementById('vlan-desc-input');
        const adminInput = document.getElementById('vlan-admin-input');
        
        if (!nameInput) return;
        
        const vlanName = nameInput.value.trim();
        if (!vlanName) {
            this.showAlert('VLAN name is required', 'error');
            return;
        }
        
        const updateData = {
            name: vlanName
        };
        
        if (descInput && descInput.value.trim()) {
            updateData.description = descInput.value.trim();
        }
        
        if (adminInput) {
            updateData.admin_state = adminInput.value;
        }
        
        this.closeVlanEditModal();
        this.updateVlanOnSwitch(this.selectedSwitch, vlanId, updateData);
    }
    
    editInterface(interfaceName) {
        if (!this.selectedSwitch) {
            this.showAlert('Please select a switch first', 'error');
            return;
        }
        
        // Check if interfaces are still loading
        if (!this.interfacesReady()) {
            this.showAlert('Please wait for interfaces to finish loading', 'warning');
            return;
        }
        
        // Create edit modal - for now use prompt, will be replaced with proper modal
        const description = prompt(`Enter description for interface ${interfaceName}:`);
        if (description === null) return; // User cancelled
        
        this.updateInterfaceOnSwitch(this.selectedSwitch, interfaceName, { description: description });
    }
    
    interfacesReady() {
        // Simple check - could be enhanced to track actual loading state
        const interfacesList = document.getElementById('interfaces-list');
        return interfacesList && !interfacesList.innerHTML.includes('Loading');
    }
    
    async updateVlanOnSwitch(switchIp, vlanId, updateData) {
        try {
            console.log(`Updating VLAN ${vlanId} on ${switchIp}:`, updateData);
            this.showLoadingSpinner(`Updating VLAN ${vlanId}...`);
            
            const response = await fetch(`/api/switches/${switchIp}/vlans/${vlanId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(data.message || `VLAN ${vlanId} updated successfully`, 'success');
                // Refresh the VLANs list
                this.loadVlansForManage();
            } else {
                console.error('Failed to update VLAN:', data.error);
                this.showAlert(`Failed to update VLAN: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error updating VLAN:', error);
            this.showAlert('Error updating VLAN: ' + error.message, 'error');
        } finally {
            this.hideLoadingSpinner();
        }
    }
    
    async updateInterfaceOnSwitch(switchIp, interfaceName, updateData) {
        try {
            console.log(`Updating interface ${interfaceName} on ${switchIp}:`, updateData);
            this.showLoadingSpinner(`Updating interface ${interfaceName}...`);
            
            const response = await fetch(`/api/switches/${switchIp}/interfaces/${encodeURIComponent(interfaceName)}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(data.message || `Interface ${interfaceName} updated successfully`, 'success');
                // Refresh the interfaces list
                this.loadInterfacesForManage();
            } else {
                console.error('Failed to update interface:', data.error);
                this.showAlert(`Failed to update interface: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error updating interface:', error);
            this.showAlert('Error updating interface: ' + error.message, 'error');
        } finally {
            this.hideLoadingSpinner();
        }
    }
    
    formatTimestamp(timestamp) {
        try {
            const date = new Date(timestamp);
            return date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });
        } catch {
            return timestamp;
        }
    }

    formatRequestData(call) {
        const data = {
            method: call.method,
            url: call.url,
            headers: call.headers,
            data: call.request_data
        };
        return JSON.stringify(data, null, 2);
    }

    formatResponseData(call) {
        const data = {
            status: call.response_code,
            size: `${call.response_size || 0} bytes`,
            duration: `${call.duration_ms}ms`,
            response: call.response_text
        };
        return JSON.stringify(data, null, 2);
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