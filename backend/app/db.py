import json
import os
from typing import List, Dict, Any, Optional
from uuid import uuid4

class JsonDB:
    def __init__(self, db_path: str = "data"):
        self.db_path = db_path
        if not os.path.exists(db_path):
            os.makedirs(db_path)

    def _get_file_path(self, collection: str) -> str:
        return os.path.join(self.db_path, f"{collection}.json")

    def _read_file(self, collection: str) -> List[Dict[str, Any]]:
        file_path = self._get_file_path(collection)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _write_file(self, collection: str, data: List[Dict[str, Any]]):
        file_path = self._get_file_path(collection)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, default=str)

    def get_all(self, collection: str) -> List[Dict[str, Any]]:
        return self._read_file(collection)

    def get_by_id(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_file(collection)
        for item in data:
            if item.get("id") == item_id:
                return item
        return None

    def get_by_field(self, collection: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
        data = self._read_file(collection)
        for item in data:
            if item.get(field) == value:
                return item
        return None

    def add(self, collection: str, item: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read_file(collection)
        if "id" not in item:
            item["id"] = str(uuid4())
        data.append(item)
        self._write_file(collection, data)
        return item

    def update(self, collection: str, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self._read_file(collection)
        for i, item in enumerate(data):
            if item.get("id") == item_id:
                data[i].update(updates)
                self._write_file(collection, data)
                return data[i]
        return None

    def delete(self, collection: str, item_id: str) -> bool:
        data = self._read_file(collection)
        initial_len = len(data)
        data = [item for item in data if item.get("id") != item_id]
        if len(data) < initial_len:
            self._write_file(collection, data)
            return True
        return False

db = JsonDB(db_path=os.getenv("DB_PATH", "data"))
