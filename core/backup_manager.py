"""
Configuration backup and restore functionality for production safety.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class BackupManager:
    """Manages configuration backups for rollback capabilities."""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self, switch_ip: str, config_data: Dict[str, Any]) -> str:
        """
        Create a configuration backup for a switch.
        Returns backup ID for future rollback operations.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{switch_ip}_{timestamp}"
        backup_file = self.backup_dir / f"{backup_id}.json"
        
        backup_data = {
            'backup_id': backup_id,
            'switch_ip': switch_ip,
            'timestamp': timestamp,
            'config': config_data,
            'metadata': {
                'created_by': 'PyAOS-CX Automation Toolkit',
                'version': '1.0'
            }
        }
        
        try:
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            logger.info(f"Created backup {backup_id} for switch {switch_ip}")
            return backup_id
            
        except Exception as e:
            logger.error(f"Failed to create backup for {switch_ip}: {e}")
            raise
    
    def list_backups(self, switch_ip: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups, optionally filtered by switch IP."""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.json"):
            try:
                with open(backup_file, 'r') as f:
                    backup_data = json.load(f)
                
                if switch_ip is None or backup_data.get('switch_ip') == switch_ip:
                    backups.append({
                        'backup_id': backup_data.get('backup_id'),
                        'switch_ip': backup_data.get('switch_ip'),
                        'timestamp': backup_data.get('timestamp'),
                        'file_size': backup_file.stat().st_size
                    })
                    
            except Exception as e:
                logger.warning(f"Error reading backup file {backup_file}: {e}")
                
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def get_backup(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific backup by ID."""
        backup_file = self.backup_dir / f"{backup_id}.json"
        
        if not backup_file.exists():
            return None
            
        try:
            with open(backup_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading backup {backup_id}: {e}")
            return None
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete a specific backup."""
        backup_file = self.backup_dir / f"{backup_id}.json"
        
        try:
            if backup_file.exists():
                backup_file.unlink()
                logger.info(f"Deleted backup {backup_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting backup {backup_id}: {e}")
            return False
    
    def cleanup_old_backups(self, switch_ip: str, keep_count: int = 10):
        """Keep only the most recent N backups for a switch."""
        backups = self.list_backups(switch_ip)
        
        if len(backups) <= keep_count:
            return
            
        # Delete older backups
        for backup in backups[keep_count:]:
            self.delete_backup(backup['backup_id'])
            
        logger.info(f"Cleaned up old backups for {switch_ip}, kept {keep_count} most recent")

# Global backup manager instance
backup_manager = BackupManager()