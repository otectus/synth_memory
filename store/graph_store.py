import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import threading
import logging

try:
    import kuzu
except ImportError:
    kuzu = None

class NoOpGraphStore:
    """No-op graph store that gracefully degrades when Kùzu is unavailable."""
    def __init__(self, db_path: Path, buffer_pool_gb: int = 4):
        self.db_path = db_path
        self.log = logging.getLogger("SynthMemory")
        self._closed = False
        self.log.warning("[SynthMemory: GraphStore] Kùzu not available. Running in degraded mode (no graph memory).")

    def upsert_entity(self, eid: str, name: str, etype: str) -> None:
        pass

    def add_relation(self, src: str, dst: str, rtype: str, weight: float = 1.0, conf: float = 1.0) -> None:
        pass

    def get_community_id(self, entity_id: str) -> Optional[int]:
        return None

    def traverse_bounded(self, start_id: str, depth: int = 2, limit: int = 50) -> List[Dict[str, Any]]:
        return []

    def close(self):
        if not self._closed:
            self._closed = True

class KuzuGraphStore:
    def __init__(self, db_path: Path, buffer_pool_gb: int = 4):
        self.log = logging.getLogger("SynthMemory")
        self._closed = False
        if kuzu is None:
            raise ImportError("Kùzu is not available.")
        os.environ['KUZU_BUFFER_POOL_SIZE'] = str(int(buffer_pool_gb) * 1024 * 1024 * 1024)
        self.db = kuzu.Database(str(db_path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
        self.lock = threading.Lock()

    def _init_schema(self) -> None:
        # Define schema statements
        statements = [
            "CREATE NODE TABLE Entity(id STRING, name STRING, type STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE Community(id INT64, summary STRING, PRIMARY KEY (id))",
            "CREATE REL TABLE RelatedTo(FROM Entity TO Entity, type STRING, weight FLOAT, confidence DOUBLE, valid_from TIMESTAMP, valid_to TIMESTAMP)",
            "CREATE REL TABLE MemberOf(FROM Entity TO Community)"
        ]
        
        for stmt in statements:
            try:
                self.conn.execute(stmt)
            except Exception as e:
                err_msg = str(e).lower()
                # Heuristic: Kuzu usually throws 'BinderException: Node/Rel table ... already exists'
                if "already exists" in err_msg or "exist" in err_msg:
                    # Safe to ignore
                    pass
                else:
                    # Structural errors (e.g. INT66 from previous runs)
                    self.log.error(f"[SynthMemory: GraphStore] Schema init failed for '{stmt}': {type(e).__name__} {e}")
                    if "int" in err_msg or "syntax" in err_msg:
                        self.log.warning(f"[SynthMemory: GraphStore] Detected potential schema corruption. Please delete DB at '{self.db}' and restart.")

    def upsert_entity(self, eid: str, name: str, etype: str) -> None:
        with self.lock:
            self.conn.execute("MERGE (e:Entity {id: $id}) SET e.name = $name, e.type = $type", {"id": str(eid), "name": str(name), "type": str(etype)})

    def add_relation(self, src: str, dst: str, rtype: str, weight: float = 1.0, conf: float = 1.0) -> None:
        with self.lock:
            now = datetime.now().isoformat()
            query = "MATCH (a:Entity {id: $s}), (b:Entity {id: $d}) CREATE (a)-[r:RelatedTo {type: $rt, weight: $w, confidence: $c, valid_from: timestamp($ts)}]->(b)"
            self.conn.execute(query, {"s": str(src), "d": str(dst), "rt": str(rtype), "w": float(weight), "c": float(conf), "ts": now})

    def get_community_id(self, entity_id: str) -> Optional[int]:
        with self.lock:
            query = "MATCH (e:Entity {id: $id})-[:MemberOf]->(c:Community) RETURN c.id LIMIT 1"
            try:
                res = self.conn.execute(query, {"id": str(entity_id)})
                if res is None or not res.has_next(): return None
                row = res.get_next()
                return row[0] if row else None
            except Exception: return None

    def traverse_bounded(self, start_id: str, depth: int = 2, limit: int = 50) -> List[Dict[str, Any]]:
        with self.lock:
            cid = self.get_community_id(start_id)
            where = f"WHERE (neighbor)-[:MemberOf]->(:Community {{id: {cid}}})" if cid is not None else ""
            query = f"MATCH (start:Entity {{id: $id}})-[r*1..{int(depth)}]-(neighbor:Entity) {where} RETURN neighbor.id AS id, neighbor.name AS name, neighbor.type AS type LIMIT {int(limit)}"
            try:
                res = self.conn.execute(query, {"id": str(start_id)})
                if res is None: return []
                df = res.get_as_df()
                return df.to_dict("records") if df is not None else []
            except Exception: return []

    def close(self):
        with self.lock:
            if self._closed: return
            if hasattr(self, 'conn') and self.conn: self.conn.close()
            if hasattr(self, 'db') and self.db: self.db.close()
            self._closed = True
