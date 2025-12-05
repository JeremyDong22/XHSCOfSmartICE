# Account manager for XHS multi-account system
# Version: 1.2 - CRUD operations for account management
# Updated: Added sync/cleanup functions for user_data consistency

import json
import os
import shutil
from typing import List, Dict, Optional
from datetime import datetime
from data_models import Account

# Paths relative to project root (parent of backend/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'account_config.json')
USER_DATA_DIR = os.path.join(BASE_DIR, 'user_data')


class AccountManager:
    """Manages XHS accounts and their browser data"""

    def __init__(self, config_file: str = CONFIG_FILE, user_data_dir: str = USER_DATA_DIR):
        self.config_file = config_file
        self.user_data_dir = user_data_dir
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist"""
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)

    def _load_config(self) -> dict:
        """Load account configuration from JSON file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"accounts": {}}

    def _save_config(self, config: dict):
        """Save account configuration to JSON file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_all_accounts(self) -> List[Account]:
        """Get all accounts (active and inactive)"""
        config = self._load_config()
        accounts = []
        for account_id, info in config.get("accounts", {}).items():
            accounts.append(Account(
                account_id=int(account_id),
                active=info.get("active", False),
                nickname=info.get("nickname", ""),
                created_at=info.get("created_at", ""),
                last_used=info.get("last_used")
            ))
        return sorted(accounts, key=lambda x: x.account_id)

    def get_active_accounts(self) -> List[Account]:
        """Get only active accounts"""
        return [acc for acc in self.get_all_accounts() if acc.active]

    def get_account(self, account_id: int) -> Optional[Account]:
        """Get a specific account by ID"""
        config = self._load_config()
        account_key = str(account_id)
        if account_key in config.get("accounts", {}):
            info = config["accounts"][account_key]
            return Account(
                account_id=account_id,
                active=info.get("active", False),
                nickname=info.get("nickname", ""),
                created_at=info.get("created_at", ""),
                last_used=info.get("last_used")
            )
        return None

    def create_account(self, nickname: str = "") -> Account:
        """Create a new account entry and return the account"""
        config = self._load_config()

        # Use max ID + 1 (sequential, no hole-filling)
        existing_ids = [int(k) for k in config.get("accounts", {}).keys()]
        next_id = max(existing_ids, default=0) + 1

        # Create account entry
        account = Account(
            account_id=next_id,
            active=True,
            nickname=nickname,
            created_at=datetime.now().isoformat()
        )

        config.setdefault("accounts", {})[str(next_id)] = {
            "active": account.active,
            "nickname": account.nickname,
            "created_at": account.created_at,
            "last_used": None
        }

        self._save_config(config)

        # Create user data directory for this account
        account_data_dir = os.path.join(self.user_data_dir, f'account_{next_id}')
        if not os.path.exists(account_data_dir):
            os.makedirs(account_data_dir)

        return account

    def update_account(self, account_id: int, **kwargs) -> bool:
        """Update account properties"""
        config = self._load_config()
        account_key = str(account_id)

        if account_key not in config.get("accounts", {}):
            return False

        for key, value in kwargs.items():
            if key in ['active', 'nickname', 'last_used']:
                config["accounts"][account_key][key] = value

        self._save_config(config)
        return True

    def mark_account_used(self, account_id: int):
        """Update last_used timestamp for an account"""
        self.update_account(account_id, last_used=datetime.now().isoformat())

    def delete_account(self, account_id: int) -> bool:
        """Delete an account and its browser data"""
        config = self._load_config()
        account_key = str(account_id)

        if account_key not in config.get("accounts", {}):
            return False

        # Remove from config
        del config["accounts"][account_key]
        self._save_config(config)

        # Delete browser data directory
        account_data_dir = os.path.join(self.user_data_dir, f'account_{account_id}')
        if os.path.exists(account_data_dir):
            shutil.rmtree(account_data_dir)

        return True

    def deactivate_account(self, account_id: int) -> bool:
        """Mark an account as inactive without deleting data"""
        return self.update_account(account_id, active=False)

    def activate_account(self, account_id: int) -> bool:
        """Mark an account as active"""
        return self.update_account(account_id, active=True)

    def get_user_data_path(self, account_id: int) -> str:
        """Get the browser user data path for an account"""
        return os.path.join(self.user_data_dir, f'account_{account_id}')

    def account_has_session(self, account_id: int) -> bool:
        """Check if an account has saved browser session data"""
        data_path = self.get_user_data_path(account_id)
        if not os.path.exists(data_path):
            return False
        # Check if there are actual session files
        return len(os.listdir(data_path)) > 0

    def get_stats(self) -> Dict:
        """Get account statistics"""
        all_accounts = self.get_all_accounts()
        active = [a for a in all_accounts if a.active]
        with_session = [a for a in all_accounts if self.account_has_session(a.account_id)]

        return {
            "total": len(all_accounts),
            "active": len(active),
            "inactive": len(all_accounts) - len(active),
            "with_session": len(with_session)
        }

    def get_orphaned_folders(self) -> List[str]:
        """Find user_data folders that don't have corresponding config entries"""
        if not os.path.exists(self.user_data_dir):
            return []

        config_ids = {str(acc.account_id) for acc in self.get_all_accounts()}
        orphaned = []

        for folder in os.listdir(self.user_data_dir):
            if folder.startswith('account_'):
                folder_id = folder.replace('account_', '')
                if folder_id.isdigit() and folder_id not in config_ids:
                    orphaned.append(folder)

        return orphaned

    def cleanup_orphaned_folders(self) -> List[str]:
        """Remove user_data folders that don't have config entries"""
        orphaned = self.get_orphaned_folders()
        removed = []

        for folder in orphaned:
            folder_path = os.path.join(self.user_data_dir, folder)
            try:
                shutil.rmtree(folder_path)
                removed.append(folder)
            except Exception as e:
                print(f"Failed to remove {folder}: {e}")

        return removed

    def import_orphaned_folders(self) -> List[int]:
        """Import orphaned user_data folders as new accounts"""
        orphaned = self.get_orphaned_folders()
        imported = []

        for folder in orphaned:
            folder_id = int(folder.replace('account_', ''))
            config = self._load_config()

            # Add to config
            config.setdefault("accounts", {})[str(folder_id)] = {
                "active": True,
                "nickname": f"Imported {folder_id}",
                "created_at": datetime.now().isoformat(),
                "last_used": None
            }
            self._save_config(config)
            imported.append(folder_id)

        return imported

    def sync_status(self) -> Dict:
        """Get sync status between config and user_data"""
        config_ids = {acc.account_id for acc in self.get_all_accounts()}

        # Find folders
        folder_ids = set()
        if os.path.exists(self.user_data_dir):
            for folder in os.listdir(self.user_data_dir):
                if folder.startswith('account_'):
                    folder_id = folder.replace('account_', '')
                    if folder_id.isdigit():
                        folder_ids.add(int(folder_id))

        orphaned = folder_ids - config_ids  # In folders but not config
        missing_data = config_ids - folder_ids  # In config but no folder

        return {
            "config_accounts": len(config_ids),
            "data_folders": len(folder_ids),
            "orphaned_folders": list(orphaned),
            "accounts_without_data": list(missing_data),
            "in_sync": len(orphaned) == 0 and len(missing_data) == 0
        }
