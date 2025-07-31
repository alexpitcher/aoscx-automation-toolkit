/**
 * Enhanced PyAOS-CX Automation Toolkit - Dashboard JavaScript
 */

class Dashboard {
    constructor() {
        this.switches = new Map();
        this.currentSwitch = null;
        this.init();
    }

    init() {
        this.loadSwitches();
        this.setupEventListeners();
        this.startHealthMonitoring();
    }

    setupEventListeners() {
        // Add switch form
        const addSwitchForm = document.getElementById('add-switch-form');
        if (addSwitchForm) {
            addSwitchForm.addEventListener('submit', (e) => this.handleAddSwitch(e));
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

        // Refresh buttons
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

        // Switch selection
        document.addEventListener('change', (e) => {
            if (e.target.id === 'switch-selector') {
                this.currentSwitch = e.target.value;
                this.loadVlansForCurrentSwitch();
            }
        });
    }

    async loadSwitches() {
        try {
            const response = await fetch('/api/switches');
            const data = await response.json();
            
            if (data.switches) {
                data.switches.forEach(switch_info => {
                    this.switches.set(switch_info.ip_address, switch_info);
                });
                this.renderSwitches();
                this.updateSwitchSelector();
            }
        } catch (error) {
            this.showAlert('Error loading switches: ' + error.message, 'error');
        }
    }

    async handleAddSwitch(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const switchIp = formData.get('switch_ip');
        const switchName = formData.get('switch_name');

        if (!this.isValidIP(switchIp)) {
            this.showAlert('Please enter a valid IP address', 'error');
            return;
        }

        try {
            this.setButtonLoading('add-switch-btn', true);
            
            const response = await fetch('/api/switches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    ip_address: switchIp, 
                    name: switchName 
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.switches.set(switchIp, data.switch);
                this.renderSwitches();
                this.updateSwitchSelector();
                this.showAlert(data.message, 'success');
                event.target.reset();
                
                // Test connection immediately
                this.refreshSwitch(switchIp);
            } else {
                this.showAlert(data.error || 'Failed to add switch', 'error');
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
                this.showAlert(`Switch ${switchIp} removed`, 'success');
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
                // Refresh VLAN list with details
                this.loadVlans(switchIp);
            } else {
                // Enhanced error messaging based on error type
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
            // Always load details for better UX
            const response = await fetch(`/api/vlans?switch_ip=${encodeURIComponent(switchIp)}&load_details=true`);
            const data = await response.json();
            
            if (response.ok) {
                this.renderVlans(data.vlans || []);
            } else {
                // Enhanced error handling
                let errorMsg = data.error || 'Failed to load VLANs';
                let alertType = 'error';
                
                if (data.error_type === 'central_management') {
                    alertType = 'warning';
                    // Show Central management specific message
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

    async loadVlansForCurrentSwitch() {
        if (this.currentSwitch) {
            await this.loadVlans(this.currentSwitch);
        }
    }

    renderSwitches() {
        const container = document.getElementById('switches-container');
        if (!container) return;

        if (this.switches.size === 0) {
            container.innerHTML = `
                <div class="text-center">
                    <p class="text-secondary">No switches added yet</p>
                    <p class="text-secondary">Add a switch to get started</p>
                </div>
            `;
            return;
        }

        const switchCards = Array.from(this.switches.values()).map(switch_info => {
            // Determine management type styling
            const isCentral = switch_info.is_central_managed;
            const managementClass = isCentral ? 'central-managed' : 'standalone';
            const managementLabel = isCentral ? 'Central Managed' : 'Standalone';
            const managementIcon = isCentral ? '🏢' : '⚙️';
            const capabilityText = isCentral ? 'Read-only operations' : 'Full automation available';
            
            return `
                <div class="switch-card ${managementClass}">
                    <div class="switch-info">
                        <div class="switch-details">
                            <h4>${switch_info.name || switch_info.ip_address}</h4>
                            <div class="switch-meta">
                                IP: ${switch_info.ip_address}
                                ${switch_info.firmware_version ? `• FW: ${switch_info.firmware_version}` : ''}
                                ${switch_info.model ? `• ${switch_info.model}` : ''}
                            </div>
                            ${switch_info.management_info ? `
                                <div class="switch-meta management-info">
                                    ${managementIcon} ${managementLabel} - ${capabilityText}
                                </div>
                            ` : ''}
                            ${switch_info.last_seen ? `
                                <div class="switch-meta">
                                    Last seen: ${new Date(switch_info.last_seen).toLocaleString()}
                                </div>
                            ` : ''}
                        </div>
                        <div class="switch-status-container">
                            <span class="status status-${switch_info.status}">
                                ${switch_info.status}
                            </span>
                            ${isCentral ? `
                                <span class="management-badge central-badge" title="Managed by Aruba Central - Write operations restricted">
                                    Central
                                </span>
                            ` : `
                                <span class="management-badge standalone-badge" title="Standalone switch - Full API access available">
                                    Direct
                                </span>
                            `}
                        </div>
                    </div>
                    <div class="flex gap-1">
                        <button class="btn btn-secondary refresh-switch" data-switch-ip="${switch_info.ip_address}">
                            Test Connection
                        </button>
                        <button class="btn btn-danger remove-switch" data-switch-ip="${switch_info.ip_address}">
                            Remove
                        </button>
                    </div>
                    ${switch_info.error_message ? `
                        <div class="alert alert-error mt-1">
                            ${switch_info.error_message}
                        </div>
                    ` : ''}
                    ${isCentral ? `
                        <div class="alert alert-warning mt-1">
                            <strong>Central Management Detected:</strong> This switch is managed by Aruba Central. 
                            VLAN creation and modification are restricted. Use this interface for monitoring and Central for configuration changes.
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        container.innerHTML = `<div class="switch-grid">${switchCards}</div>`;
        
        // Update stats after rendering
        this.updateStats();
    }


    updateSwitchSelector() {
        const selector = document.getElementById('switch-selector');
        if (!selector) return;

        const options = Array.from(this.switches.values())
            .map(switch_info => {
                const managementIndicator = switch_info.is_central_managed ? ' (Central)' : ' (Direct)';
                const statusIndicator = switch_info.status === 'online' ? '✓' : '✗';
                
                return `
                    <option value="${switch_info.ip_address}" ${switch_info.ip_address === this.currentSwitch ? 'selected' : ''}>
                        ${statusIndicator} ${switch_info.name || switch_info.ip_address}${managementIndicator}
                    </option>
                `;
            }).join('');

        selector.innerHTML = `
            <option value="">Select a switch...</option>
            ${options}
        `;

        // Set current switch if only one exists
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
                <div class="table-empty">
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
            <div class="table-container">
                <table class="table">
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
        
        // Update VLAN count in stats
        const vlanCountEl = document.getElementById('vlan-count');
        if (vlanCountEl) vlanCountEl.textContent = vlans.length;
    }

    startHealthMonitoring() {
        // Refresh switch status every 30 seconds
        setInterval(() => {
            this.switches.forEach((_, switchIp) => {
                this.refreshSwitch(switchIp);
            });
        }, 30000);
    }

    // Additional dashboard methods for Quick Operations
    refreshAllSwitches() {
        this.showAlert('Refreshing all switches...', 'info');
        this.switches.forEach((_, switchIp) => {
            this.refreshSwitch(switchIp);
        });
    }

    async exportConfiguration() {
        try {
            const response = await fetch('/api/config/export');
            const config = await response.json();
            
            // Create download link
            const dataStr = JSON.stringify(config, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `aoscx-config-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            this.showAlert('Configuration exported successfully', 'success');
        } catch (error) {
            this.showAlert('Error exporting configuration: ' + error.message, 'error');
        }
    }

    viewAuditLog() {
        // For now, show a placeholder
        this.showAlert('Audit log feature coming in Phase 2', 'info');
        // TODO: Implement audit log viewer modal
    }

    generateAnsible() {
        // For now, show a placeholder
        this.showAlert('Ansible generation feature coming in Phase 2', 'info');
        // TODO: Implement Ansible playbook generation
    }

    updateStats() {
        // Update quick stats in the sidebar
        const switchCount = this.switches.size;
        const onlineCount = Array.from(this.switches.values()).filter(s => s.status === 'online').length;
        const offlineCount = switchCount - onlineCount;
        const centralCount = Array.from(this.switches.values()).filter(s => s.is_central_managed).length;
        const standaloneCount = switchCount - centralCount;
        
        const switchCountEl = document.getElementById('switch-count');
        const onlineCountEl = document.getElementById('online-count');
        const offlineCountEl = document.getElementById('offline-count');
        
        if (switchCountEl) switchCountEl.textContent = switchCount;
        if (onlineCountEl) onlineCountEl.textContent = onlineCount;
        if (offlineCountEl) offlineCountEl.textContent = offlineCount;
        
        // Update management type stats if elements exist
        const centralCountEl = document.getElementById('central-count');
        const standaloneCountEl = document.getElementById('standalone-count');
        if (centralCountEl) centralCountEl.textContent = centralCount;
        if (standaloneCountEl) standaloneCountEl.textContent = standaloneCount;
        
        // Update VLAN count for current switch if available
        const vlanCountEl = document.getElementById('vlan-count');
        if (vlanCountEl && this.currentSwitch) {
            const vlansContainer = document.getElementById('vlans-container');
            const rows = vlansContainer ? vlansContainer.querySelectorAll('tbody tr').length : 0;
            vlanCountEl.textContent = rows;
        }
    }

    showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alert-container');
        if (!alertContainer) {
            console.log(`${type.toUpperCase()}: ${message}`);
            return;
        }

        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: inherit; cursor: pointer; padding: 0; margin-left: auto;">×</button>
        `;

        alertContainer.appendChild(alert);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }

    setButtonLoading(buttonId, loading) {
        const button = document.getElementById(buttonId);
        if (!button) return;

        if (loading) {
            button.disabled = true;
            button.innerHTML = '<span class="loading"></span> Loading...';
        } else {
            button.disabled = false;
            // Restore original text based on button ID
            const originalTexts = {
                'add-switch-btn': 'Add Switch',
                'list-vlans-btn': 'List VLANs',
                'create-vlan-btn': 'Create VLAN'
            };
            button.innerHTML = originalTexts[buttonId] || 'Submit';
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
    window.dashboard = new Dashboard();
});