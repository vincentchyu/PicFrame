def unique_values(values):
    seen = set()
    result = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def match_brand_asset(make_text, makes_config, default_path=None, resolve_fn=None):
    """公共核心函数：根据 Make/Model 品牌文本匹配配置中的资产路径。"""
    make_str = str(make_text or "").lower()
    for item in (makes_config or {}).values():
        item_id = str(item.get("id", "")).lower()
        if item_id and item_id in make_str:
            raw_path = item["path"]
            return resolve_fn(raw_path) if resolve_fn else raw_path
    if default_path:
        return resolve_fn(default_path) if resolve_fn else default_path
    return None

