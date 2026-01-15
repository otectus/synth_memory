import kuzu
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class KuzuGraphStore:
    """
    Bi-temporal knowledge graph using Kuzu.
    Implements community-bounded traversal to prevent graph explosion.
    """

    def __init__(self, db_path: Path):
        self.db = kuzu.Database(str(db_path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self) -> None:
        """
        Create tables if they do not exist. Kuzu will throw if they already exist,
        so we swallow errors for idempotent startup.
        """
        try:
            self.conn.execute(
                "CREATE NODE TABLE Entity(id STRING, name STRING, type STRING, PRIMARY KEY (id))"
            )
            self.conn.execute(
                "CREATE NODE TABLE Community(id INT64, summary STRING, PRIMARY KEY (id))"
            )
            self.conn.execute(
                "CREATE REL TABLE RelatedTo("
                "FROM Entity TO Entity, "
                "type STRING, weight FLOAT, confidence DOUBLE, "
                "valid_from TIMESTAMP, valid_to TIMESTAMP)"
            )
            self.conn.execute("CREATE REL TABLE MemberOf(FROM Entity TO Community)")
        except Exception:
            pass

    def upsert_entity(self, eid: str, name: str, etype: str) -> None:
        self.conn.execute(
            "MERGE (e:Entity {id: $id}) SET e.name = $name, e.type = $type",
            {"id": str(eid), "name": str(name), "type": str(etype)},
        )

    def add_relation(
        self,
        src: str,
        dst: str,
        rtype: str,
        weight: float = 1.0,
        conf: float = 1.0,
    ) -> None:
        now = datetime.now().isoformat()
        query = """
        MATCH (a:Entity {id: $s}), (b:Entity {id: $d})
        CREATE (a)-[r:RelatedTo {type: $rt, weight: $w, confidence: $c, valid_from: timestamp($ts)}]->(b)
        """
        self.conn.execute(
            query,
            {"s": str(src), "d": str(dst), "rt": str(rtype), "w": float(weight), "c": float(conf), "ts": now},
        )

    def get_community_id(self, entity_id: str) -> Optional[int]:
        query = """
        MATCH (e:Entity {id: $id})-[:MemberOf]->(c:Community)
        RETURN c.id
        LIMIT 1
        """
        try:
            res = self.conn.execute(query, {"id": str(entity_id)})
            if res is None or not res.has_next():
                return None
            row = res.get_next()
            return row[0] if row else None
        except Exception:
            return None

    def traverse_bounded(self, start_id: str, depth: int = 2, limit: int = 50) -> List[Dict[str, Any]]:
        cid = self.get_community_id(start_id)

        where_clause = (
            f"WHERE (neighbor)-[:MemberOf]->(:Community {{id: {cid}}})"
            if cid is not None
            else ""
        )

        query = (
            f"MATCH (start:Entity {{id: $id}})-[r*1..{int(depth)}]-(neighbor:Entity) "
            f"{where_clause} "
            f"RETURN neighbor.id AS id, neighbor.name AS name, neighbor.type AS type "
            f"LIMIT {int(limit)}"
        )

        try:
            res = self.conn.execute(query, {"id": str(start_id)})
            if res is None:
                return []

            df = res.get_as_df()
            if df is None:
                return []

            records = df.to_dict("records")
            return records or []
        except Exception:
            return []
