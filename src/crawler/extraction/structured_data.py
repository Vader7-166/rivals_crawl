"""Tang 1: doc structured data tong quat (JSON-LD + Microdata + RDFa + OpenGraph
fallback). Tasks 5.1-5.5.

Khong hard-code theo 1 cu phap (bai hoc tu case KingLED chi dung Microdata,
khong co JSON-LD nao). RDFa dung chung parser voi Microdata vi extruct tra ve
cung 1 hinh dang node ("type"/"properties") cho ca 2 cu phap nay.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import extruct

from ..record.price import PriceValue, normalize_price

_HAS_LETTER_RE = re.compile(r"[A-Za-zÀ-ỹ]")


@dataclass
class StructuredDataResult:
    ten_san_pham: Optional[str] = None
    ma_san_pham: Optional[str] = None
    raw_id: Optional[str] = None
    gia: PriceValue = None
    link_anh_san_pham: Optional[str] = None
    category_1: Optional[str] = None
    category_2: Optional[str] = None
    category_3: Optional[str] = None
    source: str = "none"


# ---------------------------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------------------------


def _jsonld_graphs(items: list[dict]) -> list[list[dict]]:
    """Tra ve danh sach cac @graph (moi block <script ld+json> la 1 graph rieng).

    QUAN TRONG: khong duoc gop het cac graph lam 1 danh sach phang roi tim
    BreadcrumbList dau tien - 1 trang co the co NHIEU block ld+json rieng biet
    (case TLC: 1 block core WordPress voi BreadcrumbList rong/gay, 1 block
    Yoast SEO rieng chua ca Product lan BreadcrumbList day du di kem). Phai uu
    tien tim Product va BreadcrumbList trong CUNG 1 graph.
    """
    graphs: list[list[dict]] = []
    for item in items:
        graph = item.get("@graph")
        if isinstance(graph, list):
            graphs.append([n for n in graph if isinstance(n, dict)])
        else:
            graphs.append([item])
    return graphs


def _find_by_jsonld_type(nodes: list[dict], type_name: str) -> Optional[dict]:
    for node in nodes:
        t = node.get("@type")
        if t == type_name or (isinstance(t, list) and type_name in t):
            return node
    return None


def _adapt_jsonld_product(node: dict) -> dict[str, Any]:
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers = offers or {}
    image = node.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url") or image.get("@id")
    return {
        "name": node.get("name"),
        "sku": node.get("sku"),
        "image": image,
        "price": offers.get("price") if isinstance(offers, dict) else None,
        "url": node.get("url"),
    }


def _adapt_jsonld_breadcrumb(node: dict) -> list[str]:
    items = node.get("itemListElement", [])
    labeled: list[tuple[int, str]] = []
    for li in items:
        if not isinstance(li, dict):
            continue
        position = li.get("position", 0)
        item = li.get("item")
        name = item.get("name") if isinstance(item, dict) else li.get("name")
        if name:
            labeled.append((position, name))
    labeled.sort(key=lambda pair: pair[0])
    return [name for _, name in labeled]


# ---------------------------------------------------------------------------
# Microdata / RDFa (extruct tra ve cung hinh dang "type"/"properties")
# ---------------------------------------------------------------------------


def _find_by_node_type(nodes: list[dict], type_suffix: str) -> Optional[dict]:
    for node in nodes:
        node_type = node.get("type", "")
        if node_type.rstrip("/").endswith(type_suffix):
            return node
    return None


def _adapt_node_product(node: dict) -> dict[str, Any]:
    props = node.get("properties", {})
    offers = props.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers_props = (offers or {}).get("properties", {}) if isinstance(offers, dict) else {}
    image = props.get("image")
    if isinstance(image, dict):
        image = image.get("properties", {}).get("url")
    return {
        "name": props.get("name"),
        "sku": props.get("sku"),
        "image": image,
        "price": offers_props.get("price"),
        "url": props.get("url"),
    }


def _adapt_node_breadcrumb(node: dict) -> list[str]:
    props = node.get("properties", {})
    items = props.get("itemListElement", [])
    labeled: list[tuple[int, str]] = []
    for li in items:
        if not isinstance(li, dict):
            continue
        li_props = li.get("properties", {})
        name = li_props.get("name")
        try:
            position = int(li_props.get("position", 0))
        except (TypeError, ValueError):
            position = 0
        if name:
            labeled.append((position, name))
    labeled.sort(key=lambda pair: pair[0])
    return [name for _, name in labeled]


# ---------------------------------------------------------------------------
# OpenGraph (fallback yeu nhat - khong co schema.org nao)
# ---------------------------------------------------------------------------


def _adapt_opengraph(items: list[dict]) -> dict[str, Any]:
    if not items:
        return {}
    props = dict(items[0].get("properties", []))
    return {
        "name": props.get("og:title"),
        "image": props.get("og:image"),
        "url": props.get("og:url"),
        "sku": None,
        "price": None,
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _labels_to_categories(labels: list[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Bo phan tu dau (home) va cuoi (chinh trang san pham), lay toi da 3 cap
    con lai tu tong quat -> cu the (theo dung thu tu breadcrumb goc)."""
    if len(labels) <= 2:
        return None, None, None
    middle = labels[1:-1][:3]
    padded = middle + [None] * (3 - len(middle))
    return padded[0], padded[1], padded[2]


def _normalize_sku(sku: Any) -> tuple[Optional[str], Optional[str]]:
    """Tra ve (ma_san_pham, raw_id). sku chi duoc dung lam Ma San Pham neu
    trong giong ma nguoi doc duoc (co chu cai) - vd TLC json-ld sku=13178 la
    ID noi bo thuan so, khong phai "Ma San Pham" (ma that nam trong bang specs,
    can tang 2 xu ly); KingLED sku="DL-12SS-T140" moi la ma san pham that."""
    if sku is None:
        return None, None
    sku_str = str(sku).strip()
    if not sku_str:
        return None, None
    if _HAS_LETTER_RE.search(sku_str):
        return sku_str, sku_str
    return None, sku_str


def extract_structured_data(html: str, page_url: str) -> StructuredDataResult:
    try:
        data = extruct.extract(
            html,
            base_url=page_url,
            syntaxes=["json-ld", "microdata", "rdfa", "opengraph"],
            errors="log",
        )
    except Exception:  # thu vien parse ngoai, khong de crawl sap vi 1 trang loi
        data = {}

    product: dict[str, Any] = {}
    breadcrumb_labels: list[str] = []
    source = "none"

    jsonld_graphs = _jsonld_graphs(data.get("json-ld", []))
    product_graph = None
    for graph in jsonld_graphs:
        node = _find_by_jsonld_type(graph, "Product")
        if node:
            product = _adapt_jsonld_product(node)
            source = "json-ld"
            product_graph = graph
            break

    # Uu tien tim BreadcrumbList trong CUNG graph voi Product (xem docstring
    # _jsonld_graphs). Chi fallback sang cac graph khac neu graph do khong co.
    search_order = ([product_graph] if product_graph else []) + [
        g for g in jsonld_graphs if g is not product_graph
    ]
    for graph in search_order:
        bc_node = _find_by_jsonld_type(graph, "BreadcrumbList")
        if bc_node:
            labels = _adapt_jsonld_breadcrumb(bc_node)
            if len(labels) > len(breadcrumb_labels):
                breadcrumb_labels = labels
            if product_graph is not None and graph is product_graph:
                break

    if not product:
        microdata_nodes = data.get("microdata", [])
        node = _find_by_node_type(microdata_nodes, "Product")
        if node:
            product = _adapt_node_product(node)
            source = "microdata"
        if not breadcrumb_labels:
            bc_node = _find_by_node_type(microdata_nodes, "BreadcrumbList")
            if bc_node:
                breadcrumb_labels = _adapt_node_breadcrumb(bc_node)

    if not product:
        rdfa_nodes = data.get("rdfa", [])
        node = _find_by_node_type(rdfa_nodes, "Product")
        if node:
            product = _adapt_node_product(node)
            source = "rdfa"
        if not breadcrumb_labels:
            bc_node = _find_by_node_type(rdfa_nodes, "BreadcrumbList")
            if bc_node:
                breadcrumb_labels = _adapt_node_breadcrumb(bc_node)

    if not product:
        og_result = _adapt_opengraph(data.get("opengraph", []))
        if og_result.get("name") or og_result.get("image"):
            product = og_result
            source = "opengraph"

    ma_san_pham, raw_id = _normalize_sku(product.get("sku"))
    cat1, cat2, cat3 = _labels_to_categories(breadcrumb_labels)

    return StructuredDataResult(
        ten_san_pham=product.get("name"),
        ma_san_pham=ma_san_pham,
        raw_id=raw_id,
        gia=normalize_price(product.get("price")),
        link_anh_san_pham=product.get("image"),
        category_1=cat1,
        category_2=cat2,
        category_3=cat3,
        source=source,
    )
