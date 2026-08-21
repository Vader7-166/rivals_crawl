"""Task: chon dung sub-sitemap SAN PHAM va khong bi 1 sitemap sai chuan danh gay.

2 bay thuc te, moi site mot kieu:
1. Sub-sitemap TAXONOMY lot vao danh sach "URL san pham". WooCommerce dat ten
   `product_cat-sitemap.xml` (TLC: 73 trang danh muc), CMS dong dat ten
   `sitemap.xml?page=ProductGroup` (KingLED: 138 trang danh muc). Ca hai deu
   chua chu "product" nen bo loc "co chu product" mot minh khong du.
2. Sitemap XML sai chuan. `kingled.com.vn/sitemap.xml?page=Product` chen URL
   anh chua dau `&` chua escape, ElementTree bao "not well-formed" va vut CA
   557 san pham - site tut xuong nhanh menu-crawl du sitemap hoan toan du.
"""
import pytest

from crawler.probing.sitemap import _TAXONOMY_SITEMAP, _parse_sitemap_xml, _local_tag


@pytest.mark.parametrize(
    "url",
    [
        "https://tlclighting.com.vn/product_cat-sitemap.xml",
        "https://tlclighting.com.vn/product_tag-sitemap.xml",
        "https://kingled.com.vn/sitemap.xml?page=ProductGroup",
        "https://example.vn/sitemap.xml?page=ProductCategory",
    ],
)
def test_taxonomy_sub_sitemaps_are_rejected(url):
    assert _TAXONOMY_SITEMAP.search(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://tlclighting.com.vn/product-sitemap.xml",
        "https://kingled.com.vn/sitemap.xml?page=Product",
        "https://example.vn/products-sitemap.xml",
    ],
)
def test_real_product_sub_sitemaps_are_kept(url):
    assert not _TAXONOMY_SITEMAP.search(url)


MALFORMED_URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://kingled.com.vn/den-panel-hop-onyx-48w-60x60cm</loc>
    <image:image><image:loc>/a.jpg?src=http___x.jpg&refer=http___y.jpg</image:loc></image:image>
  </url>
  <url><loc>https://kingled.com.vn/den-san-vuon-gr-thap-nguon-dc</loc></url>
</urlset>
"""


def test_malformed_sitemap_is_recovered_instead_of_discarded():
    """Bay 2: dau `&` chua escape trong URL anh. Bo het ca sitemap vi 1 ky tu
    hong nghia la mat toan bo san pham cua site."""
    root = _parse_sitemap_xml(MALFORMED_URLSET)

    assert root is not None
    assert _local_tag(root.tag) == "urlset"
    locs = [
        child.text
        for url_el in root
        for child in url_el
        if _local_tag(child.tag) == "loc"
    ]
    assert locs == [
        "https://kingled.com.vn/den-panel-hop-onyx-48w-60x60cm",
        "https://kingled.com.vn/den-san-vuon-gr-thap-nguon-dc",
    ]


def test_html_page_served_at_sitemap_path_is_still_rejected():
    """Che do recover khong duoc lam mat hanh vi cu: nhieu site tra ve trang
    HTML 200 o duong dan sitemap khong ton tai - do KHONG phai sitemap."""
    html = b"<!DOCTYPE html><html><head><title>404</title></head><body>x</body></html>"

    assert _parse_sitemap_xml(html) is None
