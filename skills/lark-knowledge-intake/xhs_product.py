from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse


XHS_HOSTS = {
    "xiaohongshu.com",
    "www.xiaohongshu.com",
}

PRODUCT_PATH_MARKERS = (
    "/goods-detail",
    "/goods/",
    "/product/",
    "/products/",
    "/store/goods",
    "/store/product",
    "/shop/goods",
)
SHOP_PATH_MARKERS = (
    "/shop/",
    "/shop",
    "/store/",
    "/store",
    "/mall/",
    "/mall",
)
PROFILE_PATH_MARKERS = (
    "/user/profile/",
    "/user/profile",
    "/profile/",
    "/profile",
    "/user/",
)
PRODUCT_QUERY_KEYS = {
    "goods_id",
    "goodsid",
    "item_id",
    "itemid",
    "product_id",
    "productid",
    "sku_id",
    "skuid",
}
SHOP_QUERY_KEYS = {"shop_id", "shopid", "store_id", "storeid", "vendor_id", "vendorid"}
PROFILE_QUERY_KEYS = {"user_id", "userid", "author_id", "authorid", "seller_id", "sellerid"}

_ROUTE_DEFAULTS = {
    "xhs_product": {
        "source_channel": "小红书商品",
        "topic_hint": "小红书虚拟产品",
        "asset_shape_hint": "商品调研",
        "directory_topic": "小红书虚拟产品",
        "directory_bucket": "01_竞品案例",
    },
    "xhs_shop": {
        "source_channel": "小红书店铺",
        "topic_hint": "小红书虚拟产品",
        "asset_shape_hint": "赛道分析",
        "directory_topic": "小红书虚拟产品",
        "directory_bucket": "02_赛道分析",
    },
    "xhs_profile": {
        "source_channel": "小红书主页",
        "topic_hint": "小红书",
        "asset_shape_hint": "案例包",
        "directory_topic": "小红书",
        "directory_bucket": "05_案例包",
    },
}


@dataclass(slots=True)
class XHSRoutingDecision:
    source_type: str
    source_channel: str
    topic_hint: str
    asset_shape_hint: str
    directory_topic: str
    directory_bucket: str
    normalized_url: str
    resource_id: str | None = None
    processor: str = "xhs_product"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_record_defaults(self) -> dict[str, Any]:
        return {
            "来源渠道": self.source_channel,
            "专题归属": self.topic_hint,
            "资产形态": self.asset_shape_hint,
            "关联目录索引": {
                "专题": self.directory_topic,
                "目录": self.directory_bucket,
            },
        }


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return url.strip()
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _hostname(url: str) -> str:
    return (urlparse(url.strip()).hostname or "").lower()


def _path(url: str) -> str:
    return (urlparse(url.strip()).path or "").lower()


def _query(url: str) -> dict[str, list[str]]:
    raw = parse_qs(urlparse(url.strip()).query or "", keep_blank_values=False)
    return {key.lower(): values for key, values in raw.items()}


def _has_query_key(query: dict[str, list[str]], keys: set[str]) -> bool:
    return any(key in query for key in keys)


def _match_resource_id(path: str, query: dict[str, list[str]], keys: set[str]) -> str | None:
    for key in keys:
        values = query.get(key)
        if values:
            value = values[0].strip()
            if value:
                return value

    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return None
    return segments[-1]


def is_xiaohongshu_url(url: str) -> bool:
    return _hostname(url) in XHS_HOSTS


def detect_source_type(url: str) -> str | None:
    if not is_xiaohongshu_url(url):
        return None

    path = _path(url)
    query = _query(url)

    if any(marker in path for marker in PRODUCT_PATH_MARKERS) or _has_query_key(query, PRODUCT_QUERY_KEYS):
        return "xhs_product"
    if any(marker in path for marker in SHOP_PATH_MARKERS) or _has_query_key(query, SHOP_QUERY_KEYS):
        return "xhs_shop"
    if any(marker in path for marker in PROFILE_PATH_MARKERS) or _has_query_key(query, PROFILE_QUERY_KEYS):
        return "xhs_profile"
    return None


def dispatch(url: str) -> XHSRoutingDecision | None:
    source_type = detect_source_type(url)
    if source_type is None:
        return None

    defaults = _ROUTE_DEFAULTS[source_type]
    normalized_url = _normalize_url(url)
    path = _path(normalized_url)
    query = _query(normalized_url)

    if source_type == "xhs_product":
        resource_id = _match_resource_id(path, query, PRODUCT_QUERY_KEYS)
    elif source_type == "xhs_shop":
        resource_id = _match_resource_id(path, query, SHOP_QUERY_KEYS)
    else:
        resource_id = _match_resource_id(path, query, PROFILE_QUERY_KEYS)

    return XHSRoutingDecision(
        source_type=source_type,
        source_channel=defaults["source_channel"],
        topic_hint=defaults["topic_hint"],
        asset_shape_hint=defaults["asset_shape_hint"],
        directory_topic=defaults["directory_topic"],
        directory_bucket=defaults["directory_bucket"],
        normalized_url=normalized_url,
        resource_id=resource_id,
        meta={
            "hostname": _hostname(normalized_url),
            "path": path,
            "query_keys": sorted(query.keys()),
            "resource_id": resource_id,
        },
    )
