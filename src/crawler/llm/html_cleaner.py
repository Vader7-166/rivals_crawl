"""Lam sach HTML truoc khi dua vao LLM (task 7.5) va trich rieng bang thong so
ky thuat sach cho field `Thông số kỹ thuật` cua product-record-schema.

2 ham public phuc vu 2 muc dich khac nhau, KHONG dung chung 1 output:
- clean_html_for_llm: dua het ngu canh (bang + mo ta) cho LLM de tang 2 tach
  duoc cang nhieu thuoc tinh cang tot - chap nhan hoi "rong" vi day chi la
  input cho model, khong phai gia tri luu vao ban ghi.
- extract_spec_text: CHI lay dung cac dong "label: value" tu bang 2 cot doi
  xung (bang thong so ky thuat that) - bo qua moi bang khac hinh dang (vd
  bang "san pham tuong tu"/so sanh) va toan bo text con lai cua trang. Day
  moi la gia tri duoc ghi vao cot "Thông số kỹ thuật" - khong duoc phep la
  ban dump toan bo trang (bug da gap: field dai 4000 ky tu vi lay ca menu
  danh muc + mo ta marketing cua trang).

Khong phai site nao cung trinh bay thong so bang <table>: KingLED dung bo cuc
<label>Công Suất</label><span>: 12w</span> trong cac <div> long nhau, khong co
mot the <table> nao tren ca trang. Vi vay ngoai bang, 2 ham tren con doc duoc
cap "label: value" - nhung CHI trong pham vi `spec_root_selector` truyen vao,
xem docstring _definition_pair_lines de biet vi sao pham vi la BAT BUOC.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

_STRIP_TAGS = (
    "script", "style", "nav", "aside", "footer", "header", "noscript", "svg", "iframe",
)
# LUU Y: KHONG strip the <form> - ASP.NET WebForms (case Roman.vn) boc TOAN
# BO trang trong 1 <form id="form1"> duy nhat, khong chi cac form nho (tim
# kiem/lien he) nhu gia dinh ban dau. Strip form o day tung xoa sach hoan
# toan noi dung trang tren Roman (bao gom ca bang thong so ky thuat that).


def _cell_lines(cell) -> list[str]:
    text = cell.get_text("\n", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines or [""]


def _spec_pair_lines(table) -> list[str]:
    """Dong "label: value" tu 1 bang 2 cot doi xung ve so dong con - dung cho
    ca truong hop 1 hang duy nhat voi nhieu cap gop boi <br> (TLC) lan nhieu
    hang moi hang 1 cap (Roman). Bang khong khop hinh dang nay (vd bang so
    sanh nhieu cot) tra ve [] - bi loai khoi "Thông số kỹ thuật"."""
    lines: list[str] = []
    rows = table.find_all("tr") or [table]
    for row in rows:
        cells = row.find_all(["td", "th"]) if row.name == "tr" else row.find_all("td")
        if len(cells) != 2:
            continue
        label_lines, value_lines = _cell_lines(cells[0]), _cell_lines(cells[1])
        if len(label_lines) == len(value_lines):
            lines.extend(f"{label}: {value}" for label, value in zip(label_lines, value_lines))
    return lines


def _pair_value(label) -> str:
    """Gia tri di kem 1 the <label>: uu tien the anh em ngay sau no, fallback
    ve phan text con lai cua the cha sau khi tru di chinh text cua label."""
    siblings = [node for node in label.next_siblings if getattr(node, "name", None)]
    if siblings:
        value_node = siblings[0]
        # Thuoc tinh nhieu gia tri duoc site tach thanh nhieu <a> rieng (vd
        # Ánh Sáng: <a>Trắng</a><a>Trung tính</a><a>Vàng</a>). Noi bang dau
        # phay chu khong bang dau cach - "Trắng Trung tính Vàng" doc ra thanh
        # 1 gia tri lien khuc, LLM rat de hieu sai thanh 1 thuoc tinh la.
        anchors = value_node.find_all("a")
        if len(anchors) > 1:
            values = [a.get_text(" ", strip=True) for a in anchors]
            return ", ".join(v for v in values if v)
        return value_node.get_text(" ", strip=True).lstrip(":").strip()

    label_text = label.get_text(" ", strip=True)
    parent_text = label.parent.get_text(" ", strip=True) if label.parent else ""
    rest = parent_text[len(label_text):] if parent_text.startswith(label_text) else parent_text
    return rest.lstrip(" :").strip()


def _definition_pair_lines(soup, spec_root_selector: str) -> list[str]:
    """Dong "label: value" tu bo cuc <label>/<span> (khong dung <table>), CHI
    trong cac node khop `spec_root_selector`.

    Pham vi la bat buoc chu khong phai tuy chon. Tren KingLED, cung mot bo cuc
    <label>/<span> duoc dung lai cho KHOI SAN PHAM LIEN QUAN o cuoi trang: 1
    trang san pham dem duoc 38-107 the <label>, trong do chi 10-16 cai dau la
    cua chinh san pham dang xem, so con lai la "Mã SP / Công Suất / Quang
    Thông..." cua 8 san pham KHAC. Quet toan trang se ghi thong so cua san pham
    khac vao ban ghi nay - dung nghia bia du lieu, va khong phat hien duoc khi
    review vi moi gia tri deu "co that tren trang".

    `div.property[data-id="Property"]` cua KingLED khoanh dung 1 khoi cua san
    pham dang xem (do la tab "Thông số kỹ thuật" cua chinh no). Neu selector
    khong khop node nao thi tra ve [] - trang khong dung khuon da khao sat thi
    de trong de ban ghi bi ha xuong partial-missing-fields va duoc crawl lai,
    con hon doan bua.
    """
    lines: list[str] = []
    for root in soup.select(spec_root_selector):
        for label in root.find_all("label"):
            parent = label.parent
            # <label> cua o nhap lieu (form "Đăng ký tư vấn": Họ tên*, Số điện
            # thoại*...) khong phai thong so ky thuat.
            if parent is not None and parent.find(["input", "select", "textarea"]):
                continue
            name = label.get_text(" ", strip=True).strip(" :")
            value = _pair_value(label)
            if name and value:
                lines.append(f"{name}: {value}")
    return lines


def _table_to_lines(table) -> list[str]:
    """Nhu _spec_pair_lines nhung giu lai ca bang khong khop hinh dang 2 cot
    (join bang " | ") - dung khi dua ngu canh cho LLM (clean_html_for_llm),
    noi ngu canh du thua khong sao vi model tu loc, khac voi extract_spec_text
    la gia tri luu thang vao ban ghi nen phai sach."""
    spec_lines = _spec_pair_lines(table)
    if spec_lines:
        return spec_lines
    rows = table.find_all("tr") or [table]
    lines: list[str] = []
    for row in rows:
        cells = row.find_all(["td", "th"]) if row.name == "tr" else row.find_all("td")
        if not cells:
            continue
        lines.append(" | ".join(" ".join(_cell_lines(c)) for c in cells))
    return lines


def _strip_noise(soup, noise_selector: str | None) -> None:
    """Go cac khoi KHONG thuoc san pham dang xem (vd luoi "san pham lien quan").

    Can thiet vi clean_html_for_llm co chu dich kem ca text mo ta cua trang -
    day la noi nhieu thuoc tinh that su nam (IP, CRI, quang hieu...). Nhung tren
    site lap lai thong so cua san pham khac ngay trong cung trang, phan "rong"
    do khong con vo hai: da do duoc tren kingled.com.vn/bo-nguon-150w - khoi
    thong so rieng khong he co dong bao hanh, the ma LLM van tra ve
    `bao_hanh="Đổi mới 2 năm"` vi nhat duoc tu mot phu kien lien quan o duoi.
    """
    if not noise_selector:
        return
    for node in soup.select(noise_selector):
        node.decompose()


def clean_html_for_llm(
    html: str,
    max_chars: int = 12_000,
    spec_root_selector: str | None = None,
    noise_selector: str | None = None,
) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    _strip_noise(soup, noise_selector)

    # Dat truoc phan text con lai co chu dich: text trang bi cat cung o
    # max_chars, ma khoi thong so cua KingLED nam gan CUOI trang (trong popup
    # tab) - de theo thu tu tu nhien thi no bi cat mat va tang 2 khong con gi
    # de doc. Dua len dau cung giup model uu tien khoi nay khi phan con lai
    # cua trang co nhac toi san pham lien quan.
    spec_lines = (
        _definition_pair_lines(soup, spec_root_selector) if spec_root_selector else []
    )

    table_lines: list[str] = []
    for table in soup.find_all("table"):
        table_lines.extend(_table_to_lines(table))
        table.decompose()

    body = soup.body or soup
    remaining_text = body.get_text("\n", strip=True)

    combined = "\n".join(spec_lines + table_lines + [remaining_text])
    return combined[:max_chars]


def extract_spec_text(
    html: str,
    max_chars: int = 3000,
    spec_root_selector: str | None = None,
    noise_selector: str | None = None,
) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    _strip_noise(soup, noise_selector)

    lines: list[str] = []
    if spec_root_selector:
        lines.extend(_definition_pair_lines(soup, spec_root_selector))
    for table in soup.find_all("table"):
        lines.extend(_spec_pair_lines(table))

    return "\n".join(lines)[:max_chars]
