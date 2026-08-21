"""Hồ sơ theo domain: những gì KHÔNG suy ra được khi crawl một site mới.

Nguyên tắc: thêm một đối thủ mới **không được** đẻ thêm một file .py. Mặc định
`scripts/crawl_site.py <base_url>` chạy được ngay với 0 dòng code mới — site
probing tìm nguồn URL, tầng 1 đọc structured data, tầng 2 chuẩn hoá thông số.
Chỉ khi đo trên trang thật mà thấy thiếu thì mới thêm **một dòng dữ liệu** vào
đây, không phải một module.

Phân chia với các registry ở `extraction/`:

| Registry | Trả lời câu hỏi |
|---|---|
| `sites/registry.py` (file này) | Tìm và tải trang sản phẩm thế nào |
| `extraction/css_fallback.py` | Đọc nội dung một trang đã tải thế nào |

Riêng `sites/tlc.py` là chuyện khác và không phải khuôn mẫu để nhân bản: đó là
logic phân trang qua **một category cụ thể** cho bản pilot, không phải cấu hình
để crawl toàn site.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class SiteProfile:
    """Phần riêng của một domain. Mọi field đều tuỳ chọn - domain không có mặt
    trong `SITE_PROFILES` vẫn crawl được bằng đúng hành vi mặc định."""

    # Chuỗi phải xuất hiện trong URL sản phẩm. Chỉ đặt khi sitemap sản phẩm CÒN
    # LẪN trang khác và URL có dấu hiệu phân biệt rõ ràng. Không phải site nào
    # cũng có: KingLED để URL phẳng, sản phẩm `den-panel-hop-onyx-48w-60x60cm`
    # nằm cạnh danh mục `am-tran-downlight` - lọc theo pattern là bất khả, phải
    # dựa vào phân tách của sitemap (xem probing/sitemap.py).
    product_url_pattern: Optional[str] = None

    # Selector phải có nội dung trước khi đọc HTML, cho site chỉ render thông số
    # sau khi JS chạy. KingLED: `div.property` tồn tại sẵn trong HTML tĩnh nhưng
    # RỖNG - đo được 0 dòng qua `requests` so với 16 dòng qua browser.
    wait_selector: Optional[str] = None

    @property
    def fetch_options(self) -> dict:
        """Tham số truyền thẳng cho `StealthFetcher.fetch()`."""
        return {"wait_selector": self.wait_selector} if self.wait_selector else {}


_DEFAULT_PROFILE = SiteProfile()

SITE_PROFILES: dict[str, SiteProfile] = {
    "tlclighting.com.vn": SiteProfile(product_url_pattern="/san-pham/"),
    "kingled.com.vn": SiteProfile(
        wait_selector='div.property[data-id="Property"] label',
    ),
}


def get_profile(domain_or_url: str) -> SiteProfile:
    """Hồ sơ của một domain (nhận cả URL đầy đủ), mặc định rỗng nếu chưa đăng ký."""
    domain = urlparse(domain_or_url).netloc or domain_or_url
    return SITE_PROFILES.get(domain, _DEFAULT_PROFILE)


def select_product_urls(urls: list[str], base_url: str) -> list[str]:
    """Chuẩn hoá danh sách URL từ site probing thành danh sách URL sản phẩm.

    Phần này TỔNG QUÁT cho mọi site - bỏ trang chủ, bỏ trùng lặp (sitemap thật
    có trùng: KingLED khai 557 mục cho 549 URL riêng biệt), rồi lọc theo
    `product_url_pattern` nếu domain đó có đăng ký.

    URL được GIỮ NGUYÊN VĂN, không chuẩn hoá dấu `/` cuối. Dấu `/` chỉ dùng khi
    so trùng lặp, còn bản gốc mới là thứ được trả về. Lý do: dấu `/` cuối là quy
    ước RIÊNG của từng site - cả 486 URL của TLC (WooCommerce) đều kết thúc bằng
    `/`, còn KingLED thì không URL nào có. Cắt nó đi là đổi chính DANH TÍNH của
    bản ghi: cột `Link sản phẩm` không còn là URL chính tắc của site, và nặng
    hơn - cơ chế crawl-lại-có-chọn-lọc đối chiếu theo URL nên dataset cũ mất
    khớp, mỗi lần chạy sau đều phải crawl lại từ đầu.
    """
    base = base_url.rstrip("/")
    pattern = get_profile(base_url).product_url_pattern

    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        original = url.strip()
        key = original.rstrip("/")
        if not key or key == base or key in seen:
            continue
        if pattern and pattern not in key:
            continue
        seen.add(key)
        result.append(original)
    return sorted(result)
