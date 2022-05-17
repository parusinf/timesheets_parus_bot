from typing import Optional


def row_to_dict(row) -> Optional[dict]:
    if row:
        (obj,) = row
        out = dict(obj.__dict__)
        del out['_sa_instance_state']
        return out
    else:
        return None


def rows_to_list(rows) -> list[dict]:
    out = []
    if rows:
        for row in rows:
            out.append(row_to_dict(row))
    return out
