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

    # Tên nhãn hiệu để hiển thị và để tìm kiếm. KHAI BÁO chứ không suy ra từ
    # trang: tag `thuong_hieu` vắng ở 549/549 bản ghi KingLED, còn TLC cho ra
    # bốn cách viết ("TLC LIGHTING", "TLC", "TLC Lighting", "TLC LIGHTING, TLC
    # Lighting") cho cùng một nhãn - vừa thiếu vừa bẩn.
    #
    # Một domain là một nhãn hiệu vì hệ thống chỉ crawl web CHÍNH HÃNG. Giả
    # định này sẽ gãy nếu có ngày crawl sàn TMĐT hay đại lý (một site, nhiều
    # nhãn) - khi đó nhãn hiệu phải thành một field trích xuất, không còn là
    # một dòng khai báo ở đây.
    brand_name: Optional[str] = None

    # Cách gọi khác của cùng nhãn hiệu, để người dùng gõ kiểu nào cũng ra. Chỉ
    # cần các biến thể mà việc bỏ dấu + về chữ thường KHÔNG tự xử lý được
    # (viết tách chữ, tên công ty mẹ, tên viết tắt).
    brand_aliases: tuple[str, ...] = ()

    # Selector phải có nội dung trước khi đọc một trang DANH MỤC (tầng 0.5).
    #
    # TÁCH RIÊNG khỏi `wait_selector` chứ không dùng chung, vì `wait_selector`
    # được hiệu chỉnh cho TRANG SẢN PHẨM: giá trị của KingLED là
    # `div.property[data-id="Property"] label` — bảng thông số kỹ thuật, thứ về
    # mặt cấu trúc không bao giờ có trên trang danh mục.
    #
    # Dùng chung thì không mất dữ liệu (lỗi chờ bị nuốt, xem stealth_fetch) mà
    # mất THỜI GIAN, âm thầm: mỗi trang đứng chờ đủ 5 giây timeout rồi mới đọc.
    #
    # Đo A/B trên 5 danh mục KingLED, cùng ngày, cùng máy:
    #     không wait_selector          11,6s   → 39 cạnh
    #     wait_selector của sản phẩm   37,6s   → 39 cạnh
    # Cạnh thu được GIỐNG HỆT nhau — toàn bộ 26s chênh lệch là thời gian chờ
    # suông (5,2s/trang). Ngoại suy cho cả 138 danh mục KingLED: ~12 phút.
    #
    # Mặc định None: hầu hết trang danh mục là HTML tĩnh, không cần chờ gì. Chỉ
    # đặt khi đo được là lưới sản phẩm nạp bằng JS.
    listing_wait_selector: Optional[str] = None

    # Trang danh muc de BAT DAU do, cho site ma trang chu khong lo ra loi vao.
    #
    # Nhanh khong-sitemap (probing/product_discovery.py) bat dau tu trang chu
    # va di theo menu. Nanoco thi khong di duoc: trang chu render 244KB nhung
    # chi lo 22 link noi bo, phan lon la blog - menu do JS dung khi hover nen
    # khong co trong DOM luc doc. Trong khi chinh trang danh muc cua no lai
    # hoan toan doc duoc (`/default/danh-muc/den-chieu-sang`: 30 link
    # `/default/san-pham/*`, 24 the anh).
    #
    # Day la DU LIEU, khong phai code: chi tra loi "vao site tu dau", con viec
    # URL nao la san pham van do tang 0 tu do lay. Cung khong phai danh sach
    # danh muc day du - do duoc mot cua vao la du, phan con lai di theo link.
    listing_seed_urls: tuple[str, ...] = ()

    @property
    def fetch_options(self) -> dict:
        """Tham số cho `StealthFetcher.fetch()` khi tải một trang SẢN PHẨM."""
        return {"wait_selector": self.wait_selector} if self.wait_selector else {}

    @property
    def listing_fetch_options(self) -> dict:
        """Tham số cho `StealthFetcher.fetch()` khi tải một trang DANH MỤC."""
        return (
            {"wait_selector": self.listing_wait_selector}
            if self.listing_wait_selector
            else {}
        )


_DEFAULT_PROFILE = SiteProfile()

SITE_PROFILES: dict[str, SiteProfile] = {
    "tlclighting.com.vn": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="TLC Lighting",
        brand_aliases=("TLC",),
    ),
    "kingled.com.vn": SiteProfile(
        wait_selector='div.property[data-id="Property"] label',
        brand_name="KingLED",
        # "King LED" tách chữ; "ILIKE" là công ty mẹ (Công ty Công nghệ Chiếu
        # sáng ILIKE) - người trong ngành gọi cả hai cách.
        brand_aliases=("King LED", "ILIKE"),
    ),
    # Haravan: URL san pham deu la `/products/<handle>`, con danh muc la
    # `/collections/<handle>` - hai nhanh tach bach nen loc theo pattern duoc.
    # Sitemap `sitemap_products_1.xml` ke ca trang chu (742 muc / 741 san pham).
    "dienquang.com": SiteProfile(
        product_url_pattern="/products/",
        brand_name="Điện Quang",
        # "DQ"/"ĐQ" la tien to in tren chinh ten san pham ("Đèn Tube ĐQ
        # LEDTU09"); "Dien Quang" khong dau thi bo dau tu xu ly duoc nhung
        # "Điện Quang" viet lien thi khong.
        brand_aliases=("DQ", "ĐQ", "DienQuang"),
    ),
    # panasonic.net khong co robots.txt (404) nen khong co sitemap nao de lan.
    # Bu lai, cay san pham ro rang va sau dung 2 tang:
    #   products/wlist.php                -> 32 danh muc
    #   products/plist.php?lay3=AL300040  -> san pham
    #   products/pspec.php?id=G00025989   -> trang san pham
    # Chi tro vao wlist.php la du; pattern `pspec.php` loai moi thu con lai
    # (catalog PDF, anh spec, trang giai phap) khoi danh sach cuoi.
    "panasonic.net": SiteProfile(
        product_url_pattern="pspec.php",
        brand_name="Panasonic",
        brand_aliases=("Panasonic Lighting", "Panasonic Electric Works"),
        listing_seed_urls=(
            "https://panasonic.net/electricworks/lighting/vn/products/wlist.php",
        ),
    ),
    # 7 sitemap khai trong robots.txt deu 404. San pham nam o `/<slug>.html`,
    # danh muc o `/<slug>/` - phan biet duoc bang duoi duong dan, nhung trang
    # chu khong co the <nav> nao (0 container) nen tang 0 khong tim ra cua vao
    # va vo phai ca bai blog (cung dang `/<slug>.html`). Do tren trang danh muc
    # that: `/den-led-dan-dung/` chi chua link san pham `.html`, khong bai viet.
    "duhal.com.vn": SiteProfile(
        brand_name="Duhal",
        brand_aliases=("Duhal Lighting",),
        listing_seed_urls=(
            "https://duhal.com.vn/den-led-dan-dung/",
            "https://duhal.com.vn/den-led-cong-nghiep/",
            "https://duhal.com.vn/den-led-van-phong/",
            "https://duhal.com.vn/san-pham/",
        ),
    ),
    # Sitemap 2021 chet 44% URL nen tang 0 di duong menu_crawl. Nhung roman.vn
    # de MOI trang phang o goc duoi dang `/<slug>.html`: trang san pham, trang
    # danh muc va bai blog cung mot hinh URL, va menu trang chu la carousel ANH
    # (0 the <nav>) nen khong co gi de bam vao. Do tren 80 trang da tai: khong
    # tin hieu noi dung nao tach duoc - bai "10 thong so den LED can biet"
    # nhac du cong suat/quang thong/dien ap/nhiet do mau/CRI nen vuot moi
    # nguong thong so, con `looks_like_single_product_page` chi cat duoc 7/18
    # trang rac.
    #
    # Cai tach duoc la CAU TRUC: san pham that chi xuat hien duoi cay danh muc
    # hub -> danh muc con -> san pham (`den-noi-that.html` -> `den-downlight-
    # led.html` -> 40 san pham, khong lan bai viet nao). Cay do sau 3 tang nen
    # dem tu trang chu la vuot MAX_LISTING_DEPTH; tro thang vao hai hub thi vua.
    "roman.vn": SiteProfile(
        brand_name="Roman",
        brand_aliases=("Rạng Đông Roman", "Roman Lighting"),
        # Tro thang vao 21 trang DANH MUC, khong tro vao hub. Do tren ca 21:
        # spec_field_count deu < 5 (dung la trang liet ke, khong phai san pham)
        # va tong so the san pham ~200, khop voi so URL do duoc. Vao thang tang
        # nay thi san pham nam o do sau 1 - het cho de di lac sang muc bai viet.
        #
        # Tro vao hub (`den-noi-that.html`, `thiet-bi-dien.html`) thi khong du:
        # do duoc 189 URL nhung van con 42/45 trang rac, vi chinh cay danh muc
        # cua Roman lien ket toi bai blog.
        listing_seed_urls=(
            "https://roman.vn/den-downlight-led.html",
            "https://roman.vn/den-downlight-noi.html",
            "https://roman.vn/den-mica-led.html",
            "https://roman.vn/den-led-op-tran.html",
            "https://roman.vn/den-tuyp-led.html",
            "https://roman.vn/bong-den-led-bulb.html",
            "https://roman.vn/den-roi-ray.html",
            "https://roman.vn/bo-den-tuyp-led.html",
            "https://roman.vn/den-tuong.html",
            "https://roman.vn/den-led-am-tran.html",
            "https://roman.vn/thiet-bi-cam-ung.html",
            "https://roman.vn/den-led-trang-tri.html",
            "https://roman.vn/den-led-guong.html",
            "https://roman.vn/quat-tran.html",
            "https://roman.vn/cong-tac-o-cam.html",
            "https://roman.vn/quat-thong-gio.html",
            "https://roman.vn/aptomat.html",
            "https://roman.vn/tu-dien-roman.html",
            "https://roman.vn/tu-aptomat.html",
            "https://roman.vn/chuong-dien-roman.html",
            "https://roman.vn/o-cam-am-san-roman.html",
        ),
    ),
    # Next.js. Khong co sitemap dung duoc (`sitemap.xml` khai dung mot URL
    # `http://localhost:3000/` - cau hinh dev lot len prod), va trang chu khong
    # lo ra menu, nen phai chi cho tang 0 mot cua vao. Xem `listing_seed_urls`.
    "www.nanoco.com.vn": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="Nanoco",
        brand_aliases=("Nanuco", "Nanoco Group"),
        listing_seed_urls=("https://www.nanoco.com.vn/default/danh-muc/den-chieu-sang",),
    ),
    # Cung ca voi philipsvietnam.com: `panasonic.net/electricworks/lighting/vn`
    # la catalogue toan cau, do duoc 0/147 trang co gia - chi co thong so. Gia
    # chi cong bo o kenh phan phoi VN. WooCommerce, sitemap day du, do 6/6
    # trang lay mau deu co gia.
    "panasonicvn.com.vn": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="Panasonic",
        brand_aliases=("Panasonic Lighting", "Panasonic Electric Works", "Nanoco"),
    ),
    # Trang PHAN PHOI san pham Philips tai VN (JSON-LD khai Organization
    # "ELMALL"), khong phai site cua chinh Philips. Crawl no CO CHU DICH: site
    # chinh hang `lighting.philips.com.vn` la catalogue B2B va do duoc 0/1908
    # trang co gia, con day la WooCommerce co gia niem yet tren 8/8 trang lay
    # mau. Muon so gia doi thu thi phai lay tu noi co cong bo gia.
    "philipsvietnam.com": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="Philips",
        brand_aliases=("Signify", "Philips Lighting", "ELMALL"),
    ),
    # AEM (site toan cau cua Signify). Sitemap tron ba loai trang trong cung
    # mot danh sach, phan biet bang DUOI CUNG cua duong dan: `/product` (4180
    # trang san pham), `/family` (162 trang dong san pham), `/category` (52
    # trang danh muc). Do 4180/4180 URL chua `/product` deu ket thuc bang no,
    # pattern nay khong bat nham trang nao.
    "www.lighting.philips.com.vn": SiteProfile(
        product_url_pattern="/product",
        brand_name="Philips",
        # Signify la ten cong ty me (site tu goi minh la "Signify Viet Nam");
        # "Philips Lighting" la ten cu cua chinh no.
        brand_aliases=("Signify", "Philips Lighting"),
    ),
    # WooCommerce nhu TLC. URL san pham co ba tang `/san-pham/<danh-muc>/<slug>`
    # con trang luu tru "Cua hang" la `/san-pham` KHONG co dau `/` cuoi - nen
    # pattern `/san-pham/` loai duoc dung no (442 muc sitemap / 441 san pham).
    # Domain chinh tac la `www.` (denasia.vn chuyen huong sang do).
    "www.denasia.vn": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="Asia Lighting",
        # Nhan hieu tren san pham chi in "ASIA"; "Asia Lighting" la ten day du
        # tren chinh site, con "Den Asia" la cach goi cua nguoi trong nghe.
        brand_aliases=("Asia", "Đèn Asia", "Asia Lighting"),
    ),
    # WooCommerce nhu TLC, nhung URL san pham la `/san-pham/` con danh muc lai
    # o goc (`/den-led-am-tran-vinaled/`) chu khong o `/danh-muc/`.
    # `product-sitemap.xml` ke ca trang "Cửa hàng" (669 muc / 668 san pham).
    "denvinaled.vn": SiteProfile(
        product_url_pattern="/san-pham/",
        brand_name="VinaLED",
        brand_aliases=("Vina LED", "Đèn VinaLED"),
    ),
    # Hai entry dưới đây KHÔNG khai gì cho việc crawl — cả hai site crawl được
    # bằng đúng hành vi mặc định (180 và 120 sản phẩm trong kho), và đó vẫn là
    # tính chất mà `test_site_registry.py` chốt.
    #
    # Chúng có mặt ở đây vì tìm kiếm cần một thứ khác hẳn: tập đóng nhãn hiệu.
    # Thiếu entry thì gõ "mpe" không khớp nhãn nào và rơi xuống nhánh tên sản
    # phẩm, còn gõ "vne" thì khớp trúng danh mục `Đèn VNE` — tức người dùng hỏi
    # một nhãn hiệu và được trả về một danh mục của chính nhãn đó.
    #
    # Rút ra: `brand_name` là field DUY NHẤT trong hồ sơ có ích cho một site
    # không cần hiệu chỉnh crawl gì cả, nên nó phải được điền cho MỌI domain đã
    # crawl, không chỉ domain có phần riêng.
    "www.mpe.com.vn": SiteProfile(
        brand_name="MPE",
    ),
    "vne-led.vn": SiteProfile(
        # Site tự in nhãn là "VNE" trong chính tên sản phẩm ("Bộ bán nguyệt LED
        # 20W nhãn VNE"). "VNE Led" lấy từ domain — người dùng gõ cả hai kiểu.
        brand_name="VNE",
        brand_aliases=("VNE Led", "Đèn VNE"),
    ),
}


def get_profile(domain_or_url: str) -> SiteProfile:
    """Hồ sơ của một domain (nhận cả URL đầy đủ), mặc định rỗng nếu chưa đăng ký."""
    domain = urlparse(domain_or_url).netloc or domain_or_url
    return SITE_PROFILES.get(domain, _DEFAULT_PROFILE)


def brand_of(domain_or_url: str) -> str:
    """Tên nhãn hiệu để hiển thị. Domain chưa khai thì lấy chính domain - thà
    hiện một cái tên xấu còn hơn hiện một ô trống."""
    domain = urlparse(domain_or_url).netloc or domain_or_url
    profile = SITE_PROFILES.get(domain)
    return (profile.brand_name if profile else None) or domain


def registered_domains() -> list[str]:
    """Domain đã đăng ký. Đây là tập đóng mà bộ phân loại từ khoá khớp vào."""
    return sorted(SITE_PROFILES)


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
