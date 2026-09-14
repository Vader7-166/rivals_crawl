"""Tim site LED cua doi thu bang bo may tim kiem (change `rival-discovery`).

Giai bai toan ma registry khai cung khong giai duoc: doi thu doi ten mien, hoac
co doi thu minh chua biet. Ba tang tach roi:

    queries.py   go gi     - truy van phai la TEN LOAI HANG, khong phai mo ta
                             loai hinh doanh nghiep (co so do that trong file)
    engine.py    hoi ai    - Bing mac dinh, cam engine khac vao duoc
    scoring.py   tin ai    - diem KEM LY DO, khong luat nao tu vut ung vien

Nguoi dung duyet ket qua. Do la cung hinh voi man xac nhan pham vi: khop truot
thi bo tick, gia sua bang mot cu bam - chu khong phai mot domain sai lang le
di vao kho du lieu.
"""
from .engine import BingEngine, SearchEngine, SearchHit, StaticEngine
from .finder import CUA_MINH, KetQuaTim, tim_doi_thu, tim_lai_site
from .queries import TRUY_VAN_MAC_DINH, tim_lai_nhan, tu_danh_muc
from .scoring import TinHieu, UngVien, cham_diem, ly_do_loai

__all__ = [
    "BingEngine", "SearchEngine", "SearchHit", "StaticEngine",
    "CUA_MINH", "KetQuaTim", "tim_doi_thu", "tim_lai_site",
    "TRUY_VAN_MAC_DINH", "tim_lai_nhan", "tu_danh_muc",
    "TinHieu", "UngVien", "cham_diem", "ly_do_loai",
]
