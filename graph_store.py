import kuzu
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


class KuzuGraphStore:
    """Thin Kuzu-backed graph store.

    Defensive by default: methods return empty results instead of raising when possible.
    """

    def __init__(self, db_path: Path):
        self.db = kuzu.Database(str(db_path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
        self._community_cache: Dict[str, int] = {}

    def _init_schema(self) -> None:
        # Idempotent-ish schema setup: ignore "already exists" errors.
        for stmt in (
            "CREATE NODE TABLE Entity(id STRING, name STRING, type STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE Community(id INT64, summary STRING, last_updated TIMESTAMP, PRIMARY KEY (id))",
            "CREATE REL TABLE RelatedTo("
            "FROM Entity TO Entity, "
            "type STRING, "
            "weight DOUBLE, "
            "confidence DOUBLE, "
            "valid_from TIMESTAMP, "
            "valid_to TIMESTAMP)",
            "CREATE REL TABLE MemberOf(FROM Entity TO Community)",
        ):
            try:
                self.conn.execute(stmt)
            except Exception:
                pass

    def upsert_entity(self, eid: str, name: str, etype: str) -> None:
        self.conn.execute(
            "MERGE (e:Entity {id: $id}) "
            "SET e.name = $name, e.type = $type",
            {"id": str(eid), "name": str(name), "type": str(etype)},
        )

    def upsert_community(
        self, cid: int, summary: str = "", last_updated: Optional[datetime] = None
    ) -> None:
        ts = (last_updated or datetime.now()).isoformat()
        self.conn.execute(
            "MERGE (c:Community {id: $id}) "
            "SET c.summary = $summary, c.last_updated = timestamp($ts)",
            {"id": int(cid), "summary": str(summary), "ts": ts},
        )

    def set_membership(self, entity_id: str, community_id: int) -> None:
        # Ensure nodes exist
        self.conn.execute("MERGE (e:Entity {id: $id})", {"id": str(entity_id)})
        self.conn.execute("MERGE (c:Community {id: $id})", {"id": int(community_id)})

        # Create relationship (best-effort dedupe)
        try:
            self.conn.execute(
                "MATCH (e:Entity {id: $eid}), (c:Community {id: $cid}) "
                "MERGE (e)-[:MemberOf]->(c)",
                {"eid": str(entity_id), "cid": int(community_id)},
            )
        except Exception:
            try:
                self.conn.execute(
                    "MATCH (e:Entity {id: $eid}), (c:Community {id: $cid}) "
                    "CREATE (e)-[:MemberOf]->(c)",
                    {"eid": str(entity_id), "cid": int(community_id)},
                )
            except Exception:
                pass

        self._community_cache[str(entity_id)] = int(community_id)

    def add_relation(
        self,
        src: str,
        dst: str,
        rel_type: str,
        weight: float = 1.0,
        confidence: float = 1.0,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
    ) -> None:
        # Ensure endpoints exist so MATCH succeeds.
        self.conn.execute("MERGE (e:Entity {id: $id})", {"id": str(src)})
        self.conn.execute("MERGE (e:Entity {id: $id})", {"id": str(dst)})

        vf = (valid_from or datetime.now()).isoformat()

        if valid_to is None:
            query = (
                "MATCH (a:Entity {id: $s}), (b:Entity {id: $d}) "
                "CREATE (a)-[:RelatedTo {type: $t, weight: $w, confidence: $c, "
                "valid_from: timestamp($vf)}]->(b)"
            )
            params = {
                "s": str(src),
                "d": str(dst),
                "t": str(rel_type),
                "w": float(weight),
                "c": float(confidence),
                "vf": vf,
            }
        else:
            vt = valid_to.isoformat()
            query = (
                "MATCH (a:Entity {id: $s}), (b:Entity {id: $d}) "
                "CREATE (a)-[:RelatedTo {type: $t, weight: $w, confidence: $c, "
                "valid_from: timestamp($vf), valid_to: timestamp($vt)}]->(b)"
            )
            params = {
                "s": str(src),
                "d": str(dst),
                "t": str(rel_type),
                "w": float(weight),
                "c": float(confidence),
                "vf": vf,
                "vt": vt,
            }

        self.conn.execute(query, params)

    def get_community_id(self, entity_id: str) -> Optional[int]:
        key = str(entity_id)
        if key in self._community_cache:
            return self._community_cache[key]

        res = self.conn.execute(
            "MATCH (e:Entity {id: $id})-[:MemberOf]->(c:Community) RETURN c.id",
            {"id": key},
        )
        if res is None:
            return None

        try:
            if res.has_next():
                cid = res.get_next()[0]
                if cid is None:
                    return None
                cid_int = int(cid)
                self._community_cache[key] = cid_int
                return cid_int
        except Exception:
            return None

        return None

    def traverse_bounded(
        self, start_id: str, depth: int = 2, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Traverse neighbors from `start_id` up to `depth`.

        If the start entity belongs to a Community, constrain traversal results to that same Community.
        Returns list of dicts: {id, name, type}.
        """
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
            return records if records else []
        except Exception:
            return []
