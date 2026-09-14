"""Trich muc "Ưu điểm" trong cum mo ta san pham -> 2 cot cua khuon tham chieu:
`Tóm tắt ưu điểm, tính năng` va `Nội dung Ưu điểm SP`.

Day la du lieu CO THAT tren trang nhung truoc gio pipeline khong dung toi: 2 cot
do trong 100% o ca TLC lan KingLED, khac han cac cot nhu `Mã SAP` (site that su
khong co gi tuong duong).

Khuon tham chieu (`product_Metadata (1).xlsx`, sheet "2. LED Downlight") dinh
dang 2 cot nay nhu sau, va code o day bam theo:
  - `Tóm tắt ưu điểm, tính năng`: MOI GACH DAU DONG 1 DONG, ngan cach bang \\n.
  - `Nội dung Ưu điểm SP`: toan van muc do, cung ngan cach bang \\n.

Co che TONG QUAT cho moi site, khong co config rieng theo domain:
  tim heading chua chu "ưu điểm" -> lay cac the anh em toi heading ngang/tren
  cap -> tach gach dau dong -> nhan vao cot tom tat, toan van vao cot noi dung.
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional

from bs4 import BeautifulSoup


class Advantages(NamedTuple):
    """Ket qua trich muc uu diem, kem DUONG NAO da dinh vi duoc no.

    `nguon` khong phai du lieu san pham ma la du lieu ve chinh lan trich xuat:
    ba duong dinh vi co do tin cay RAT khac nhau (xem docstring
    extract_advantages), va truoc day thong tin do bi vut di ngay sau khi cham
    diem xong. Giu lai thi cau hoi "o nao dang dang ngo" tra loi duoc bang mot
    cau truy van thay vi mot buoi mo tay tung o - do that: 6/360 o cua KingLED
    la muc lay nham, va con so 6 do co duoc bang cach mo tay.
    """

    tom_tat: Optional[str]
    noi_dung: Optional[str]
    nguon: str


# Ba duong dinh vi + truong hop khong tim thay. Ghi vao cot `uu_diem_nguon`
# cua kho du lieu.
NGUON_TU_KHOA = "keyword"   # tieu de muc mang tin hieu duong
NGUON_LA_BAN = "anchor"     # mot dong do tang 2 (LLM) chi ra
NGUON_CUM = "cluster"       # cum de muc ngang cap, khong co tieu de muc
# Trang khong co MUC uu diem nao, lay ca khoi mo ta cua site lam noi dung.
NGUON_MO_TA = "description"
NGUON_KHONG_CO = "none"     # khong duong nao dinh vi duoc

_HEADINGS = ("h1", "h2", "h3", "h4")

# The KHONG PHAI <h*> nhung dong vai tro tieu de muc. Do tren trang that:
#   roman.vn      <div class="text">Đặc điểm nổi bật:</div>
#   dienquang.com <a>Đặc điểm</a>            (nhan tab)
# Chi coi la tieu de khi CA BA dieu kien: the thuoc nhom nay, chuoi NGAN (mot
# dong tieu de, khong phai doan van), va mang tin hieu duong `_POSITIVE_TITLE`.
# Thieu rang buoc do dai thi moi doan van co chu "dac diem" deu thanh tieu de.
_PSEUDO_HEADING_TAGS = ("div", "p", "strong", "b", "span", "a", "label", "dt")

# Chuoi ngan thoi CHUA du. Do tren fixture denvinaled: dong noi dung "Rọi vào
# cây cối, bụi hoa, tượng phù điêu để làm nổi bật vẻ đẹp..." dai 78 ky tu va
# co chu "nổi bật" - lot moi nguong do dai rong rai va cuop mat ket qua dung.
# Nen phai doi hoi no KHONG DOC NHU MOT CAU:
#   - ket thuc bang dau hai cham -> nhan ro rang, cho toi 60 ky tu
#     (roman.vn: "Đặc điểm nổi bật:")
#   - khong co dau hai cham -> phai rat ngan, khong dau phay, khong ket thuc
#     bang dau cham (dienquang.com: "Đặc điểm")
_PSEUDO_HEADING_MAX_LEN = 60
_PSEUDO_HEADING_MAX_LEN_KHONG_HAI_CHAM = 40


def _doc_nhu_tieu_de(text: str) -> bool:
    t = text.strip()
    if t.endswith(":"):
        return len(t) <= _PSEUDO_HEADING_MAX_LEN
    return (
        len(t) <= _PSEUDO_HEADING_MAX_LEN_KHONG_HAI_CHAM
        and "," not in t
        and not t.endswith(".")
    )

# Tieu de gia luon duoc coi la cap SAU NHAT: muc cua no dung lai truoc bat ky
# <h1>..<h4> nao phia sau. Coi no cap cao hon thi no se nuot ca cac muc <h*>
# ke tiep khong lien quan.
_PSEUDO_LEVEL = 4

# Bo dau de khop duoc ca "ưu điểm", "Ưu Điểm", "uu diem".
_ADVANTAGE_RE = re.compile(r"uu\s*diem", re.IGNORECASE)

# So thu tu muc dau dong ("4. ", "1.2 ") - bo khoi dong tom tat, vi no khong
# co dinh giua cac san pham (TLC danh so 4, KingLED danh so 1).
#
# Bat buoc phai co DAU PHAN CACH (dau cham/ngoac) hoac la so nhieu cap. Neu chi
# can "so + khoang trang" thi cat nham ca so lieu that: nhan "2 dải LED to bản"
# cua TLC tut xuong con "dải LED to bản".
_LEADING_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)+|\d+[.)])\s+")

# Ky tu mo dau 1 gach dau dong khi site khong dung the <li>. \uFE0F la
# variation-selector di kem emoji ("☑" + U+FE0F -> "☑️").
_BULLET_MARKER = re.compile(r"^[-•–—+*▪‣»☑✅✔✓❖◆●○\u25aa\u2022]\uFE0F?\s+")

# Dong ban cheo cuoi muc, vd TLC: ">>> Xem thêm: Đèn LED âm trần loại nào tốt".
_CROSS_SELL = re.compile(r"^\s*(>>>|&gt;&gt;&gt;)|xem\s+thêm\s*:", re.IGNORECASE)

_MAX_SUMMARY = 2000
_MAX_CONTENT = 8000


# "đ"/"Đ" la ky tu rieng (U+0111/U+0110), KHONG phai "d" + dau nen NFD khong
# tach ra duoc - phai thay tay, neu khong "ưu điểm" bo dau van con la "uu diem"
# co chu đ va regex khong khop.
_D_STROKE = str.maketrans({"đ": "d", "Đ": "D"})


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.translate(_D_STROKE))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _heading_level(node) -> int:
    """Cap cua mot tieu de. `h2` -> 2; tieu de gia -> `_PSEUDO_LEVEL`."""
    name = getattr(node, "name", None)
    if name in _HEADINGS:
        return int(name[1])
    return _PSEUDO_LEVEL


def _pseudo_headings(soup) -> list:
    """Cac the dong vai tro tieu de muc nhung khong phai <h*>.

    Bo qua the co con la the KHOI: mot <div> boc ca muc thi text cua no dai va
    da bi rang buoc do dai loai; nhung <div> boc dung mot <p> ngan thi khong -
    va lay no lam tieu de se khien muc rong (noi dung nam BEN TRONG chinh no,
    khong phai o cac the anh em).
    """
    out = []
    for tag in soup.find_all(_PSEUDO_HEADING_TAGS):
        if tag.find(["div", "p", "ul", "ol", "table", "section"]):
            continue
        text = tag.get_text(" ", strip=True)
        if not text or not _doc_nhu_tieu_de(text):
            continue
        if not _POSITIVE_TITLE.search(_strip_accents(text)):
            continue
        out.append(tag)
    return out


# Muc do MOT tieu de gia phai dan toi, de duoc coi la muc uu diem that.
_PSEUDO_MIN_DONG = 2
_PSEUDO_MIN_KY_TU = 80


def _du_noi_dung(heading, nodes: list) -> bool:
    if not nodes:
        return False
    lines = [d for d in _section_text(heading, nodes).split("\n") if d.strip()]
    # Dong dau la chinh tieu de -> bo ra khi dem.
    than = lines[1:]
    return len(than) >= _PSEUDO_MIN_DONG and sum(len(d) for d in than) >= _PSEUDO_MIN_KY_TU


def _is_advantage_heading(tag) -> bool:
    return bool(_ADVANTAGE_RE.search(_strip_accents(tag.get_text(" ", strip=True))))


def _clean_line(text: str) -> str:
    return _LEADING_NUMBER.sub("", text.strip()).strip(" :–-")


def _holds_heading_at_or_above(node, level: int) -> bool:
    """`node` CHINH LA hoac CHUA BEN TRONG mot heading ngang/tren `level`."""
    name = getattr(node, "name", None)
    if name in _HEADINGS and int(name[1]) <= level:
        return True
    if not hasattr(node, "find_all"):
        return False
    return any(int(h.name[1]) <= level for h in node.find_all(_HEADINGS))


def _leading_children_before_heading(node, level: int) -> list:
    """Phan DAU cua `node`, cat ngay truoc de muc ngang/tren `level` dau tien
    ben trong no."""
    nodes = []
    for child in node.children:
        if getattr(child, "name", None) is None:
            continue
        name = child.name
        if name in _HEADINGS and int(name[1]) <= level:
            break
        if _holds_heading_at_or_above(child, level):
            nodes.extend(_leading_children_before_heading(child, level))
            break
        nodes.append(child)
    return nodes


def _siblings_after(start, level: int) -> list:
    nodes = []
    for sibling in start.next_siblings:
        name = getattr(sibling, "name", None)
        if name is None:
            continue
        if name in _HEADINGS and int(name[1]) <= level:
            break
        if _holds_heading_at_or_above(sibling, level):
            # The anh em nay khong PHAI de muc ke tiep, no CHUA de muc ke tiep
            # ben trong - tuc mot the boc gop nhieu muc lam mot. Cat truoc day
            # thi ca noi dung nam phia truoc de muc do bi vut theo, va muc coi
            # nhu rong -> _section_nodes leo len the cha va vo phai noi dung
            # cua mot muc KHAC. Do that tren denvinaled.vn: muc "Vai trò chính
            # của đèn chiếu cảnh quan" tra ve khoi "Thông tin liên hệ" (dia chi
            # showroom, MST) va do la thu duoc ghi vao cot "Ưu điểm".
            nodes.extend(_leading_children_before_heading(sibling, level))
            break
        nodes.append(sibling)
    return nodes


def _section_nodes(heading) -> list:
    """Cac the thuoc ve muc cua `heading`, dung khi gap heading ngang/tren cap.

    Dung muc heading chu khong phai "gap the <h> bat ky": muc "Ưu điểm" cua
    KingLED la <h2> va ben trong no co 8 <h3> con - dung lai o <h3> dau tien se
    cat mat gan het muc.

    Khong phai luc nao noi dung cung la ANH EM cua heading. Do tren trang that:
    `tlclighting.com.vn/san-pham/am-tran-khoi-duc-tos-7w-vien-bac-don-sac` boc
    rieng `<h2>4. Ưu điểm...</h2>` trong mot <div> - heading do co DUNG 0 the
    anh em, con noi dung nam o anh em cua chinh cai <div> ay. Chi quet anh em
    truc tiep thi muc nay tra ve rong du tim thay heading, va do la lo hong im
    lang: khong bao loi, chi la 2 cot bi trong.
    """
    level = _heading_level(heading)
    nodes = _siblings_after(heading, level)
    if nodes:
        return nodes

    node = heading.parent
    while node is not None and node.name not in (None, "body", "[document]"):
        nodes = _siblings_after(node, level)
        if nodes:
            return nodes
        node = node.parent

    # Muc van rong -> noi long: dung lai o heading CAO CAP HON thay vi ngang cap.
    # Can cho cau truc heading PHANG, noi cac y cua muc lai la heading NGANG CAP
    # voi chinh tieu de muc. Do tren kingled.com.vn/den-exit-chi-huong-len-2m:
    #     <h3>ưu điểm sản phẩm</h3>          <- tieu de muc
    #     <h3>Thiết kế hài hòa, theo tiêu chuẩn</h3>   <- y 1
    #     <h3>...sử dụng pin dung lượng cao</h3>       <- y 2
    #     <h3>Tuổi thọ cao, tiết kiệm điện năng</h3>   <- y 3
    #     <h2>CÁC KHU VỰC CẦN TRANG BỊ...</h2>         <- het muc
    # Luat "dung o heading ngang cap" cat ngay tai y 1 -> muc rong. Chi noi long
    # KHI DA THAT BAI, nen trang co cau truc long nhau dung chuan khong bi anh
    # huong.
    return _siblings_after(heading, level - 1)


def _bullet_labels(nodes: list, heading_level: int, flat: bool = False) -> list[str]:
    """Nhan cua tung gach dau dong.

    Uu tien HEADING CON, sau do moi toi <li>. Thu tu nay quan trong: muc cua
    KingLED co ca 8 <h3> (dung la cac y chinh) lan 1 <ul> nam long trong mot y
    (cac buoc lap dat) - lay <ul> truoc se ra danh sach sai hoan toan. Muc cua
    TLC thi khong co heading con nao, gach dau dong that la cac <li>.
    """
    sub_headings: list[str] = []
    for node in nodes:
        tags = [node] if node.name in _HEADINGS else node.find_all(_HEADINGS)
        for tag in tags:
            if int(tag.name[1]) >= heading_level + (0 if flat else 1):
                line = _clean_line(tag.get_text(" ", strip=True))
                if line:
                    sub_headings.append(line)
    if sub_headings:
        return sub_headings

    labels: list[str] = []
    for node in nodes:
        items = [node] if node.name == "li" else node.find_all("li")
        for item in items:
            # Nhan in dam ("<strong>Chống ẩm tối ưu:</strong> Nhờ thiết kế...")
            # chinh la phan tom tat; khong co thi lay ca dong.
            strong = item.find(["strong", "b"])
            raw = strong.get_text(" ", strip=True) if strong else item.get_text(" ", strip=True)
            line = _clean_line(raw)
            if line:
                labels.append(line)
    if labels:
        return labels

    # Cuoi cung: gach dau dong go bang KY TU thay vi bang the. Danh sach ky tu
    # phai rong: do tren 549 san pham KingLED, 153 san pham dung EMOJI "☑️" lam
    # dau gach dau dong chu khong phai "-", va vi the truot het qua bo loc ->
    # cot Nội dung Ưu điểm SP co du lieu ma cot Tóm tắt lai trong.
    for node in nodes:
        for raw in node.get_text("\n", strip=True).split("\n"):
            line = raw.strip()
            match = _BULLET_MARKER.match(line)
            if match:
                cleaned = _clean_line(line[match.end():])
                if cleaned:
                    labels.append(cleaned)
    if labels:
        return labels

    # Het cach: y chinh duoc IN DAM ngay dau doan van, khong co the danh dau
    # nao ca - "<p><strong>Tiết kiệm điện và tuổi thọ cao:</strong> Đèn LED
    # Tuýp Oval 20W su dung...". Do tren 485 san pham TLC: 43 san pham viet
    # kieu nay.
    for node in nodes:
        paragraphs = [node] if node.name == "p" else node.find_all("p")
        for para in paragraphs:
            bold = para.find(["strong", "b"])
            if bold is None:
                continue
            label = bold.get_text(" ", strip=True)
            body = para.get_text(" ", strip=True)
            # Phai la NHAN mo dau doan (co phan mo ta theo sau), khong phai chu
            # in dam de nhan manh giua doan hay ca doan in dam.
            if not label or not body.startswith(label) or len(body) <= len(label) + 10:
                continue
            cleaned = _clean_line(label)
            if cleaned and 3 <= len(cleaned) <= 120:
                labels.append(cleaned)
    return labels


def _norm(text: str) -> str:
    return re.sub(r"[\s\u00a0]+", " ", text).strip().lower()


def _locate_by_anchor(soup, anchor: str) -> tuple:
    """Dinh vi muc uu diem bang MOT DONG do tang 2 chi ra (xem llm/schema.py
    quy tac 9). Tra ve (heading_hoac_None, nodes).

    Vi sao can den tang 2 o day: tieu de cua muc nay khong co chuan nao ca -
    do tren 20 trang that dem duoc "Ưu điểm vượt trội", "Đặc điểm cấu tạo",
    "ĐẶC ĐIỂM NỔI BẬT CỦA...", "Lợi ích khi sử dụng...", "Vì sao nên lắp đặt...",
    "Tại sao nên sử dụng..." va ca truong hop KHONG CO TIEU DE (chi la 1 <ul>
    7 muc nam sau <figure>). Danh sach tu khoa khong bao gio du; nhung LLM thi
    da doc trang do roi trong chinh loi goi tang 2 - khong ton them request nao.

    LLM chi duoc phep tra ve mot dong CO THAT tren trang; moi viec cat muc va
    lay noi dung van do code lam tren DOM, nen gia tri ghi ra file van nguyen
    van chu khong phai van model tu viet.
    """
    key = _norm(anchor)
    if len(key) < 6:  # qua ngan -> khop bua bai
        return None, []

    # La ban tro nham vao muc mang tin hieu am thi BO HAN, dung di theo.
    # Khong bo o day thi hai duong du phong ben duoi (khop <li>, khop <p>) tra
    # ve heading=None, ma luat chan tin hieu am trong _score_candidate lai co
    # dieu kien `heading is not None` - tuc la lot sach.
    # Do that tren tlclighting.com.vn: LLM tro vao dong "Thông số kỹ thuật:"
    # nam trong mot <p>, code lay <p> do + 4 the ke tiep, va CA BANG THONG SO
    # duoc ghi vao cot "Nội dung Ưu điểm SP" (3 san pham: nano-cob-gold,
    # den-exit-2-mat, highlight-smart-76w). Bo la ban di thi cac ung vien khac
    # van con nguyen - chi mat diem cong +60, khong mat kha nang tim thay muc.
    if _NEGATIVE_TITLE.search(_strip_accents(anchor)):
        return None, []

    for heading in soup.find_all(_HEADINGS):
        if key in _norm(heading.get_text(" ", strip=True)):
            nodes = _section_nodes(heading)
            if nodes:
                return heading, nodes

    # Khong co tieu de: LLM tra ve dong dau tien cua danh sach -> leo len the
    # <ul>/<ol> boc ngoai va lay ca danh sach do.
    for item in soup.find_all("li"):
        if _norm(item.get_text(" ", strip=True)).startswith(key):
            container = item.find_parent(["ul", "ol"])
            if container is not None:
                return None, [container]

    for para in soup.find_all("p"):
        if _norm(para.get_text(" ", strip=True)).startswith(key):
            nodes = [para] + _siblings_after(para, 4)
            return None, nodes

    return None, []


def _section_text(heading, nodes: list) -> str:
    lines = [_clean_line(heading.get_text(" ", strip=True))] if heading is not None else []
    for node in nodes:
        for raw in node.get_text("\n", strip=True).split("\n"):
            line = raw.strip()
            if line and not _CROSS_SELL.search(line):
                lines.append(line)
    # Giu thu tu nhung bo dong lap - trang KingLED render muc nay 2 lan (ban
    # trong trang + ban trong popup tab "Mô tả sản phẩm").
    seen: set[str] = set()
    unique = [ln for ln in lines if not (ln in seen or seen.add(ln))]
    return "\n".join(unique)


# Tin hieu DUONG trong tieu de muc (khong con dung de TIM, chi de CHAM DIEM -
# xem docstring extract_advantages).
_POSITIVE_TITLE = re.compile(
    r"uu\s*diem|dac\s*diem|noi\s*bat|loi\s*ich|tai\s*sao|vi\s*sao|tinh\s*nang|uu\s*viet",
    re.IGNORECASE,
)

# Tin hieu AM: cac muc khac cua trang san pham deu co cung hinh dang "tieu de +
# danh sach y" nen rat de bi cham diem cao. Vd tren cung 1 trang KingLED co
# "CÁC KHU VỰC CẦN TRANG BỊ ĐÈN EXIT" va "ĐỊA CHỈ MUA ĐÈN EXIT CHÍNH HÃNG",
# tren TLC co "1. Thông số kỹ thuật", "2. Sản phẩm tương tự", "Ứng dụng quan
# trọng của...". Ghi thang mot muc ung dung vao cot "Ưu điểm" la sai du lieu,
# nen cac muc nay bi LOAI chu khong phai bi tru diem.
_NEGATIVE_TITLE = re.compile(
    r"thong\s*so|ung\s*dung|dia\s*chi|mua\s|lap\s*dat|huong\s*dan|luu\s*y"
    r"|cau\s*hoi|tuong\s*tu|khu\s*vuc|chinh\s*sach|cam\s*ket|so\s*sanh|danh\s*gia"
    r"|bao\s*hanh|van\s*chuyen|thanh\s*toan|lien\s*he",
    re.IGNORECASE,
)


def _score_candidate(heading, nodes, from_anchor: bool = False, is_cluster: bool = False):
    """Diem cua 1 ung vien, None neu bi loai thang.

    Loai thang 2 truong hop: muc RONG (chi co dong tieu de) va muc co tieu de
    mang tin hieu am. Muc rong la cai bay chinh cua KingLED - trang nao cung co
    nhan tab "ưu điểm sản phẩm" nam ngay canh "Mô tả sản phẩm" / "Kiểm chứng
    chất lượng", sau khi lam phang HTML thi no trong y het mot tieu de muc that,
    nhung phan lon trang thi tab do BO TRONG con noi dung that lai nam duoi cac
    de muc khong mang dau hieu gi.
    """
    level = _heading_level(heading) if heading is not None else 1
    text = _section_text(heading, nodes)
    if len(text.split("\n")) < 2:
        return None
    if heading is not None and _NEGATIVE_TITLE.search(_strip_accents(heading.get_text(" ", strip=True))):
        return None

    flat = any(
        getattr(n, "name", None) in _HEADINGS and int(n.name[1]) == level for n in nodes
    )
    labels = _bullet_labels(nodes, level, flat=flat)

    if is_cluster:
        # Cum de muc la nhanh SUY DOAN HINH DANG, khong co tin hieu nao xac nhan
        # do la muc uu diem - nen phai kho tinh, neu khong se ghi nham du lieu
        # vao dung cot mang ten "Ưu điểm". Hai ca do duoc:
        #   - kingled/den-led-dan-dc12v-22w -> vo phai danh sach PHU KIEN
        #     (Bộ nguồn / Thanh nhôm / Phụ kiện cảm ứng...)
        #   - tlc/den-led-am-tran-mat-cong-de-mong -> vo phai muc "Cấu tạo đèn",
        #     va nuot luon ca "Ứng dụng" lan "Mua đèn ... ở đâu?"
        # Nen: de muc con mang tin hieu am nghia la cum da tran sang muc khac.
        peer_titles = [
            n.get_text(" ", strip=True)
            for n in nodes
            if getattr(n, "name", None) in _HEADINGS and int(n.name[1]) == level
        ]
        # >=2 de muc NGANG CAP theo sau, tuc it nhat 3 y ke ca chinh tieu de.
        # Nguong 3 (bo tieu de) cat mat cac muc dung 3 y - do that:
        # kingled/den-exit co dung 3 de muc, roman/plp102 cung vay.
        if len(peer_titles) < 2:
            return None
        if any(_NEGATIVE_TITLE.search(_strip_accents(t)) for t in peer_titles):
            return None

        # Cum bat dau tu de muc con DAU TIEN nen tin hieu am thuong nam o TIEU DE
        # ME cao cap hon dung phia tren, khong nam trong chinh cac de muc. Do
        # that: kingled/den-led-op-tran-30w lay nham cum "Chiếu sáng văn phòng /
        # Chiếu sáng nhà ở..." - ban than chung vo hai, nhung tieu de me cua
        # chung la "Ứng dụng của...".
        parent_title = heading.find_previous(_HEADINGS) if heading is not None else None
        while parent_title is not None and int(parent_title.name[1]) >= level:
            parent_title = parent_title.find_previous(_HEADINGS)
        if parent_title is not None and _NEGATIVE_TITLE.search(
            _strip_accents(parent_title.get_text(" ", strip=True))
        ):
            return None

    score = 0.0
    if heading is not None and _POSITIVE_TITLE.search(_strip_accents(heading.get_text(" ", strip=True))):
        score += 100
    if from_anchor:
        score += 60
    score += min(len(labels), 8) * 10
    score += min(len(text), 3000) / 100.0
    return score


def _heading_clusters(soup) -> list:
    """Cac cum "nhieu de muc ngang cap lien tiep".

    Bat nhieu site khong dat cho muc uu diem MOT TIEU DE nao, chi liet ke thang
    cac y bang de muc ngang cap. Do tren mau ngau nhien: TLC
    `mat-cong-de-mong`, KingLED `den-exit`, va 3/7 trang san pham Roman
    (`plp102`: "Tiết kiệm năng lượng" / "Tuổi thọ cao" / "Chip LED cao cấp").
    Day KHONG phai quirk cua 1 site ma la mot hinh dang pho bien - bo qua no la
    bo sot ca mot lop du lieu o ca 3 site.

    DANH DOI DA BIET va da duoc chap nhan co y thuc: nhanh nay dua do phu tren
    20 trang mau tu 10/20 len 14/20, nhung 2 trong so do lay nham muc khac cung
    hinh dang:
      - kingled/den-led-dan-dc12v-22w -> danh sach PHU KIEN
        (Bộ nguồn / Thanh nhôm / Phụ kiện cảm ứng)
      - tlc/den-led-am-tran-mat-cong-de-mong -> muc "Cấu tạo đèn"
        (Chip Led Bridgelux / Vỏ đèn led / Đế tản nhiệt)

    Ranh gioi rat mong: cai dung la LOI KHANG DINH ("Tiết kiệm năng lượng"),
    cai sai la TEN LINH KIEN ("Thanh nhôm") - nhung "Chip LED cao cấp" (dung) va
    "Chip Led Bridgelux" (sai) thi khong luat tu vung nao tach duoc. Da siet
    bang tin hieu am + toi thieu 3 de muc; phan con lai la gia phai tra cho do
    phu. Muon uu tien do chinh xac tuyet doi thi bo dong `offer(..., 
    is_cluster=True)` trong extract_advantages.
    """
    out = []
    consumed: set[int] = set()
    for heading in soup.find_all(_HEADINGS):
        if id(heading) in consumed:
            continue
        level = int(heading.name[1])
        # Dung o heading CAO CAP HON, de cac de muc ngang cap deu nam trong cum.
        nodes = _siblings_after(heading, level - 1)
        peers = [
            n for n in nodes
            if getattr(n, "name", None) in _HEADINGS and int(n.name[1]) == level
        ]
        if len(peers) >= 2:
            out.append((heading, nodes))
            # De muc sau khong duoc mo cum chong len cum vua nhan.
            consumed.update(id(n) for n in peers)
    return out


# Dong CHI LA mot cap thong so ("Cong suat (W): 7", "Tuoi tho: 25000 gio").
# Khoi mo ta chi gom nhung dong nhu vay thi KHONG phai uu diem - do la bang
# thong so viet doc. Do tren vne-led.vn: `#tab-description` cua no chua dung
# 9 dong kieu nay va khong mot cau nao.
_DONG_THONG_SO = re.compile(r"^[^:]{2,44}:\s*[<>~]?\s*[\d.,/\-]+\s*\w{0,12}$")

# Ty le toi da cac dong la cap thong so de khoi mo ta van duoc coi la uu diem.
_TY_LE_THONG_SO_TOI_DA = 0.6


def _mo_ta_la_uu_diem(text: str) -> bool:
    """Khoi mo ta co dang van xuoi (uu diem) hay chi la bang thong so.

    Doi hoi hai dieu, deu do duoc: co it nhat MOT CAU that (dai va co dau cham
    hoac dau phay), va khong qua nua so dong la cap "nhan: so".
    """
    lines = [d.strip() for d in text.split("\n") if d.strip()]
    if not lines:
        return False
    thong_so = sum(1 for d in lines if _DONG_THONG_SO.match(d))
    if thong_so / len(lines) > _TY_LE_THONG_SO_TOI_DA:
        return False
    return any(len(d) >= 40 and ("." in d or "," in d) for d in lines)


def extract_advantages(
    html: str,
    noise_selector: Optional[str] = None,
    anchor: Optional[str] = None,
    description_selector: Optional[str] = None,
) -> Advantages:
    """Tra ve (tom_tat, noi_dung, nguon). Hai gia tri dau None neu trang khong
    co muc do; `nguon` khi do la NGUON_KHONG_CO.

    KHONG tin tieu de dau tien tim thay. Gom TAT CA ung vien roi cham diem, vi
    3 cach dinh vi deu tung dan sai o cho khac nhau tren trang that:

      - tu khoa   : tieu de muc nay khong co chuan nao. Do tren 20 trang dem
                    duoc "Ưu điểm vượt trội", "Đặc điểm cấu tạo", "ĐẶC ĐIỂM NỔI
                    BẬT CỦA...", "Lợi ích khi sử dụng...", "Vì sao nên lắp
                    đặt...", "Tại sao nên sử dụng..." - va ca trang KHONG CO
                    TIEU DE nao (chi la 1 <ul> 7 muc nam sau <figure>).
      - la ban LLM: model bam vao nhan tab "ưu điểm sản phẩm" cua KingLED - dung
                    chu nhung tab do RONG tren phan lon trang.
      - cum de muc: dung hinh dang, nhung muc "ứng dụng" / "địa chỉ mua hàng"
                    cung y het hinh dang do.

    Nen: ung vien rong bi loai, ung vien mang tin hieu am bi loai, phan con lai
    cham diem theo tin hieu duong + so gach dau dong + do day noi dung.
    `noise_selector` go khoi khong thuoc san pham dang xem truoc khi tim.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "aside", "footer", "header", "noscript"]):
        tag.decompose()
    if noise_selector:
        for node in soup.select(noise_selector):
            node.decompose()

    candidates = []  # (diem, heading, nodes, nguon)

    def offer(heading, nodes, source, from_anchor=False, is_cluster=False):
        if not nodes:
            return
        score = _score_candidate(heading, nodes, from_anchor, is_cluster)
        if score is not None:
            candidates.append((score, heading, nodes, source))

    # CHI khop tren THE HEADING. Tren trang TLC, chu "ưu điểm" xuat hien 4 lan
    # theo thu tu tai lieu: mo ta blog trong mega-menu -> muc luc tu dong ->
    # <h2> that -> cau dan trong doan van. Tim tren text tho roi nhay toi cho
    # dau tien la roi vao menu.
    for heading in soup.find_all(_HEADINGS):
        # Luoi rong: MOI tieu de mang tin hieu duong deu duoc chao, khong chi
        # rieng chu "ưu điểm". An toan la nho khau LOAI (ung vien rong / tin
        # hieu am) chu khong nho khau tim hep.
        if _POSITIVE_TITLE.search(_strip_accents(heading.get_text(" ", strip=True))):
            offer(heading, _section_nodes(heading), NGUON_TU_KHOA)

    # Tieu de muc KHONG PHAI <h*>. Site tu do dat: roman.vn dung
    # `<div class="text">Đặc điểm nổi bật:</div>`, dienquang.com dung nhan tab
    # `<a>Đặc điểm</a>`. Chi quet <h1>..<h4> thi ca hai deu vo hinh - do tren
    # 40 trang Roman thieu uu diem, 37 trang CO chu "dac diem/uu diem" tren
    # trang ma khong trang nao co no trong mot the <h*>.
    for heading in _pseudo_headings(soup):
        nodes = _section_nodes(heading)
        # Tieu de gia phai DAN TOI NOI DUNG THAT. Rang buoc nay khong the bo:
        # `<a class="nav-link">Vì sao chọn MPE</a>` la link dieu huong, no van
        # qua duoc moi kiem tra hinh dang (ngan, khong dau phay, co "vi sao")
        # va keo theo dung mot dong "Hồ Sơ Năng Lực MPE". Khong chan thi ca 180
        # san pham MPE deu bi ghi ho so cong ty vao cot uu diem.
        #
        # <h*> that khong can rang buoc nay: chinh viec site danh dau no la de
        # muc da la mot khang dinh, con <div>/<a> thi khong.
        if _du_noi_dung(heading, nodes):
            offer(heading, nodes, NGUON_TU_KHOA)

    if anchor:
        anchor_heading, anchor_nodes = _locate_by_anchor(soup, anchor)
        offer(anchor_heading, anchor_nodes, NGUON_LA_BAN, from_anchor=True)

    for heading, nodes in _heading_clusters(soup):
        offer(heading, nodes, NGUON_CUM, is_cluster=True)

    if not candidates:
        return _tu_khoi_mo_ta(soup, description_selector)

    _, heading, nodes, source = max(candidates, key=lambda c: c[0])
    tom_tat, noi_dung = _assemble(heading, nodes)
    # `_assemble` van co the tra ve rong (muc chi co dong tieu de). Khong ghi ra
    # gi thi nguon phai la KHONG_CO, khong phai nhanh da thang - neu khong,
    # cot `uu_diem_nguon` se bao la tim thay trong khi hai cot kia trong.
    if tom_tat is None and noi_dung is None:
        return _tu_khoi_mo_ta(soup, description_selector)
    return Advantages(tom_tat, noi_dung, source)


# Nhan cua mot muc, khong phai mot Y. Do tren www.denasia.vn: khoi mo ta cua
# `bep-dien-tu-bt01` mo dau bang dong "Mô tả sản phẩm", va ghi thang no vao cot
# "Tóm tắt ưu điểm" thi nguoi doc nhan duoc mot cai nhan chu khong phai du lieu.
_NHAN_MUC = re.compile(
    r"^(mo\s*ta|thong\s*tin|thong\s*so|chi\s*tiet|gioi\s*thieu|noi\s*dung)"
    r"(\s+(san\s*pham|ky\s*thuat|chung))?\s*:?$",
    re.IGNORECASE,
)


def _la_nhan_muc(text: str) -> bool:
    return bool(_NHAN_MUC.match(_strip_accents(text).strip()))


def _y_do_site_tach_san(node) -> list[str]:
    """Cac y ma CHINH SITE da tach roi trong khoi mo ta.

    Hai cach site tach: the <li>, hoac ky tu gach dau dong mo dau dong. Khong
    tim thay cach nao thi tra ve rong - khong tu cat cau.
    """
    items = [_clean_line(li.get_text(" ", strip=True)) for li in node.select("li")]
    items = [d for d in items if d and not _la_nhan_muc(d)]
    if items:
        return items
    out = []
    for dong in node.get_text("\n", strip=True).split("\n"):
        dong = dong.strip()
        if _BULLET_MARKER.match(dong):
            sach = _clean_line(_BULLET_MARKER.sub("", dong))
            if sach and not _la_nhan_muc(sach):
                out.append(sach)
    return out


def _tu_khoi_mo_ta(soup, description_selector: Optional[str]) -> Advantages:
    """Duong cuoi: khong co MUC uu diem nao thi lay ca KHOI MO TA cua site.

    Nhieu site khong viet muc uu diem rieng ma go thang mot doan mo ta, va
    chinh doan do noi ve uu diem. Do tren trang that: denvinaled.vn ("chat
    luong cao, tuoi tho lau nam"), roman.vn ("ben, dep, chong oxy hoa, tan
    nhiet nhanh"), nanoco ("chi phi tiet kiem hon...").

    Cot TOM TAT chi duoc dien khi CHINH SITE da tach san cac y - bang the <li>
    hoac bang ky tu gach dau dong ("– Thiết kế hiện đại, sang trọng. – Dễ dàng
    sử dụng." tren www.denasia.vn). Doan van xuoi lien mach thi de trong cot
    do: tu cat cau ra thanh gach dau dong la tu dien giai ho site.
    """
    if not description_selector:
        return Advantages(None, None, NGUON_KHONG_CO)
    for node in soup.select(description_selector):
        lines = [
            _clean_line(d)
            for d in node.get_text("\n", strip=True).split("\n")
            if _clean_line(d) and not _CROSS_SELL.match(d)
        ]
        text = "\n".join(dict.fromkeys(lines))
        if not text or not _mo_ta_la_uu_diem(text):
            continue
        labels = _y_do_site_tach_san(node)
        tom_tat = "\n".join(dict.fromkeys(labels))[:_MAX_SUMMARY] or None
        return Advantages(tom_tat, text[:_MAX_CONTENT], NGUON_MO_TA)
    return Advantages(None, None, NGUON_KHONG_CO)


def _assemble(heading, nodes: list):
    level = _heading_level(heading) if heading is not None else 1
    # Cau truc phang: cac y cua muc la heading NGANG CAP voi tieu de muc.
    flat = any(
        getattr(n, "name", None) in _HEADINGS and int(n.name[1]) == level for n in nodes
    )
    labels = _bullet_labels(nodes, level, flat=flat)

    # Cum khong co tieu de me: chinh `heading` la Y DAU TIEN chu khong phai
    # tieu de muc, nen no phai co mat trong tom tat. Phan biet bang tin hieu
    # duong: "Ưu điểm sản phẩm" la tieu de (bo ra), con "Tiết kiệm năng lượng"
    # la mot y (giu lai).
    if flat and heading is not None and not _POSITIVE_TITLE.search(
        _strip_accents(heading.get_text(" ", strip=True))
    ):
        first = _clean_line(heading.get_text(" ", strip=True))
        if first and first not in labels:
            labels.insert(0, first)

    lines = _section_text(heading, nodes).split("\n")
    # Chi co dong tieu de, khong co noi dung nao ben duoi (vd bo-nguon-150w co
    # <h3>ưu điểm sản phẩm</h3> bo trong) -> ghi ra chi la rac, coi nhu khong co.
    if len(lines) < 2:
        return None, None

    summary = "\n".join(dict.fromkeys(labels))[:_MAX_SUMMARY] or None
    content = "\n".join(lines)[:_MAX_CONTENT] or None
    return summary, content
