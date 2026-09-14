/* Giao diện điều khiển crawl — JS thuần, không framework, không build step.
 *
 * Lý do (design.md mục 4b): thứ duy nhất màn tiến độ cần là `EventSource`, và
 * nó đã có sẵn trong trình duyệt. Một framework ở đây chỉ thêm bundler, Node,
 * node_modules và một bước build đứng giữa "sửa file" với "thấy kết quả" —
 * trong khi ta vừa quyết định bỏ cơ chế nạp lại để không lượt crawl 70 phút nào
 * bị giết ngang.
 */

const $ = (id) => document.getElementById(id);
const api = async (duong, tuy_chon) => {
  const r = await fetch(duong, tuy_chon);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `Lỗi ${r.status}`);
  }
  return r.json();
};

/* Trạng thái của LẦN TÌM HIỆN TẠI. Cố ý không lưu vào localStorage: việc bỏ
 * tick một danh mục là một lựa chọn LÚC DÙNG, không phải một cấu hình phải bảo
 * trì (spec `crawl-scope-search`). Lần tìm sau danh sách hiện đầy đủ lại. */
let phamVi = null;
let loaiDangChon = null;
let boTick = new Set();
let dongSuKien = null;

/* ---- điều hướng -------------------------------------------------------- */

document.querySelectorAll("nav button").forEach((nut) => {
  nut.onclick = () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("dang-mo"));
    nut.classList.add("dang-mo");
    document.querySelectorAll(".man").forEach((m) => (m.hidden = true));
    $("man-" + nut.dataset.man).hidden = false;
    if (nut.dataset.man === "domain") napDomain();
    if (nut.dataset.man === "job") napJob();
    if (nut.dataset.man === "so-sanh") napChonSoSanh();
  };
});

/* ---- màn 1: gợi ý khi đang gõ ------------------------------------------ */

const NHAN_NHOM = {
  brands: "Nhãn hiệu",
  categories: "Danh mục",
  products: "Tên sản phẩm",
};

let hoan;
$("tu-khoa").addEventListener("input", (e) => {
  clearTimeout(hoan);
  const q = e.target.value.trim();
  if (!q) return an(true);
  // Gõ nhanh thì chỉ lần dừng cuối cùng mới gọi API — không phải mỗi phím.
  hoan = setTimeout(() => goiY(q), 120);
});

$("tu-khoa").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    an(true);
    xemPhamVi($("tu-khoa").value.trim(), null);
  }
  if (e.key === "Escape") an(true);
});

const an = (co) => ($("goi-y").hidden = co);

async function goiY(q) {
  const kq = await api(`/api/suggest?q=${encodeURIComponent(q)}`);
  const hop = $("goi-y");
  hop.innerHTML = "";
  let coGi = false;

  for (const nhom of ["brands", "categories", "products"]) {
    const dsach = kq[nhom];
    if (!dsach.length) continue;
    coGi = true;
    const tieu = document.createElement("div");
    tieu.className = "nhom";
    tieu.textContent = NHAN_NHOM[nhom];
    hop.appendChild(tieu);

    for (const g of dsach) {
      const dong = document.createElement("div");
      dong.className = "dong";
      const ten = document.createElement("span");
      ten.textContent = g.label;
      const dem = document.createElement("span");
      dem.className = "dem";
      // Số 0 vẫn hiện: "chưa crawl" là sự thật người dùng cần biết trước khi
      // bấm, không phải thứ để giấu đi.
      dem.textContent =
        g.products === 0
          ? "chưa crawl"
          : `${g.products} SP` + (g.domains.length > 1 ? ` · ${g.domains.length} nhãn` : "");
      dong.append(ten, dem);
      // Bấm gợi ý thì truyền LOẠI của chính nó làm `prefer`. Thiếu bước này,
      // gợi ý danh mục "Đèn LED Âm Trần VinaLED" sẽ ra phạm vi cả nhãn VinaLED
      // — bấm một danh mục 166 sản phẩm lại nhận 668.
      dong.onclick = () => {
        $("tu-khoa").value = g.query;
        an(true);
        xemPhamVi(g.query, g.kind);
      };
      hop.appendChild(dong);
    }
  }
  an(!coGi);
}

/* ---- màn 2: xác nhận phạm vi ------------------------------------------- */

async function xemPhamVi(q, prefer) {
  if (!q) return;
  loaiDangChon = prefer;
  boTick = new Set(); // lần tìm mới không nhớ lựa chọn cũ
  await veLaiPhamVi(q);
}

async function veLaiPhamVi(q) {
  const tham = new URLSearchParams({ q });
  if (loaiDangChon) tham.set("prefer", loaiDangChon);
  boTick.forEach((u) => tham.append("exclude", u));

  phamVi = await api(`/api/scope?${tham}`);
  const loai = $("loai-pham-vi");
  loai.hidden = false;
  loai.innerHTML = "";

  if (phamVi.kind === "none") {
    loai.textContent = phamVi.reason || "Không khớp gì.";
    $("pham-vi").hidden = true;
    return;
  }

  loai.append(`Hiểu là ${NHAN_NHOM[phamVi.kind + "s"] || phamVi.kind}. `);
  // Khớp nhiều loại thì cho chuyển loại mà KHÔNG phải gõ lại từ khoá.
  for (const khac of phamVi.alternatives) {
    const nut = document.createElement("button");
    nut.textContent = `xem như ${NHAN_NHOM[khac + "s"] || khac}`;
    nut.onclick = () => {
      loaiDangChon = khac;
      veLaiPhamVi(q);
    };
    loai.appendChild(nut);
  }

  $("tong-so").textContent = phamVi.total;
  $("tong-co").textContent = phamVi.have;
  $("tong-thieu").textContent = phamVi.missing;
  $("nut-crawl").disabled = phamVi.missing === 0;
  $("nut-crawl").textContent =
    phamVi.missing === 0 ? "Đã crawl đủ" : `Crawl ${phamVi.missing} sản phẩm còn thiếu`;

  const hop = $("danh-sach-domain");
  hop.innerHTML = "";
  for (const d of phamVi.domains) {
    const khoi = document.createElement("div");
    khoi.className = "domain";
    const dau = document.createElement("header");
    dau.innerHTML =
      `<span class="ten">${d.brand} <span class="so">${d.domain}</span></span>` +
      `<span class="so">${d.total} SP · đã có ${d.have} · còn thiếu ${d.missing}</span>`;
    khoi.appendChild(dau);

    if (d.needs_index) {
      // "Chưa dựng chỉ mục" KHÁC HẲN "không có sản phẩm nào".
      const bao = document.createElement("p");
      bao.className = "canh-bao";
      bao.textContent =
        "Chưa dựng chỉ mục danh mục cho đối thủ này — chỉ thấy được phần đã có " +
        "trong kho. Dựng chỉ mục: scripts/build_category_index.py " + d.domain;
      khoi.appendChild(bao);
    }

    if (d.categories.length) {
      const ul = document.createElement("ul");
      for (const c of d.categories) {
        const li = document.createElement("li");
        const tick = document.createElement("input");
        tick.type = "checkbox";
        tick.checked = !boTick.has(c.url);
        tick.onchange = () => {
          tick.checked ? boTick.delete(c.url) : boTick.add(c.url);
          veLaiPhamVi(q);
        };
        const ten = document.createElement("label");
        ten.textContent = c.name || c.url;
        const so = document.createElement("span");
        so.textContent = c.ok
          ? `${c.total} SP · thiếu ${c.missing}`
          : `chưa có dữ liệu (${c.error || "fetch hỏng"})`;
        li.append(tick, ten, so);
        ul.appendChild(li);
      }
      khoi.appendChild(ul);
    }
    hop.appendChild(khoi);
  }
  $("pham-vi").hidden = false;
}

$("nut-crawl").onclick = async () => {
  const than = {
    keyword: $("tu-khoa").value.trim(),
    prefer: loaiDangChon,
    exclude: [...boTick],
  };
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    document.querySelector('nav button[data-man="job"]').click();
    theoDoi(job.id);
    if (job.queued_behind_running_job) {
      $("job-ly-do").hidden = false;
      $("job-ly-do").textContent =
        "Job này đang xếp hàng sau một job khác — mỗi lúc chỉ một job được chạy " +
        "(kho dữ liệu chỉ chịu được một người ghi).";
    }
  } catch (e) {
    alert(e.message);
  }
};

$("nut-xuat").onclick = async () => {
  const tham = new URLSearchParams({ q: $("tu-khoa").value.trim() });
  if (loaiDangChon) tham.set("prefer", loaiDangChon);
  boTick.forEach((u) => tham.append("exclude", u));
  // Thứ tự đối thủ mặc định = số sản phẩm giảm dần, đã do tầng xuất lo. Ai muốn
  // thứ hạng khác thì kéo lại thứ tự rồi xuất lại — 10 giây (design.md mục 3).
  phamVi.domains.forEach((d) => tham.append("order", d.domain));

  const bao = $("bao-xuat");
  bao.hidden = false;
  bao.textContent = "Đang dựng file…";
  const r = await fetch(`/api/export?${tham}`);
  if (!r.ok) {
    bao.textContent = (await r.json().catch(() => ({}))).detail || "Không xuất được";
    return;
  }
  const thieu = Number(r.headers.get("X-Missing") || 0);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${$("tu-khoa").value.trim() || "ket-qua"}.xlsx`;
  a.click();
  URL.revokeObjectURL(a.href);
  // Nói rõ file là bản một phần — người nhận phải biết mình đang cầm cái gì.
  bao.textContent = thieu
    ? `Đã tải. LƯU Ý: phạm vi còn thiếu ${thieu} sản phẩm chưa crawl — đây là bản một phần.`
    : "Đã tải. Phạm vi đã crawl đủ.";
};

/* ---- màn 3: tiến độ job qua SSE ---------------------------------------- */

function theoDoi(jobId) {
  if (dongSuKien) dongSuKien.close();
  $("job-dang-chay").hidden = false;
  $("job-id").textContent = jobId;

  // `EventSource` tự nối lại khi đứt — đóng và mở lại trình duyệt vẫn thấy
  // đúng tiến độ, vì trạng thái nằm trong kho chứ không nằm trong trang.
  dongSuKien = new EventSource(`/api/jobs/${jobId}/events`);
  dongSuKien.onmessage = (e) => {
    const job = JSON.parse(e.data);
    $("job-trang-thai").textContent = job.status;
    $("job-da-lam").textContent = job.processed;
    $("job-tong").textContent = job.total;
    $("thanh-tien-do").style.width = job.total ? `${(job.processed / job.total) * 100}%` : "0";
    $("job-url").textContent = job.current_url || "—";
    if (job.stop_reason) {
      $("job-ly-do").hidden = false;
      $("job-ly-do").textContent = `Lý do dừng: ${job.stop_reason}`;
    }
    $("nut-huy").disabled = ["done", "failed", "cancelled"].includes(job.status);
    if (["done", "failed", "cancelled"].includes(job.status)) {
      dongSuKien.close();
      napJob();
    }
  };
  $("nut-huy").onclick = async () => {
    await api(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  };
}

async function napJob() {
  const ds = await api("/api/jobs");
  const than = document.querySelector("#bang-job tbody");
  than.innerHTML = "";
  for (const j of ds) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td class="bam">${j.id}</td><td>${j.keyword || ""}</td><td>${j.status}</td>` +
      `<td class="so">${j.processed}/${j.total}</td><td>${j.stop_reason || ""}</td>`;
    tr.querySelector(".bam").onclick = () => theoDoi(j.id);
    than.appendChild(tr);
  }
}

/* ---- màn 4: đối thủ ---------------------------------------------------- */

async function napDomain() {
  const ds = await api("/api/domains");
  const hop = $("the-domain");
  hop.innerHTML = "";
  for (const d of ds) {
    const the = document.createElement("div");
    the.className = "the";
    the.innerHTML =
      `<b>${d.brand}</b><br><span class="ghi-chu">${d.domain}</span><br>` +
      `<span class="ghi-chu">${d.products} sản phẩm` +
      `${d.indexed ? "" : " · chưa dựng chỉ mục"}</span>`;
    the.onclick = () => xemSanPham(d);
    hop.appendChild(the);
  }
}

let domainDangXem = null;

async function xemSanPham(d) {
  domainDangXem = d;
  $("san-pham-domain").hidden = false;
  $("ten-domain").textContent = `${d.brand} — ${d.domain}`;
  await veSanPham();
}

$("loc-trang-thai").onchange = veSanPham;
$("loc-xu-ly-tay").onchange = veSanPham;

async function veSanPham() {
  if (!domainDangXem) return;
  const tham = new URLSearchParams();
  if ($("loc-trang-thai").value) tham.set("status", $("loc-trang-thai").value);
  if ($("loc-xu-ly-tay").checked) tham.set("needs_review", "true");

  const kq = await api(`/api/domains/${domainDangXem.domain}/products?${tham}`);
  $("dem-san-pham").textContent =
    kq.total === 0
      ? "Đối thủ này chưa có dữ liệu nào trong kho — chạy crawl ở màn Tìm & crawl."
      : `${kq.matched} / ${kq.total} sản phẩm`;

  const than = document.querySelector("#bang-san-pham tbody");
  than.innerHTML = "";
  for (const p of kq.products) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><a href="${p.url}" target="_blank" rel="noopener">${p.ten_san_pham || "—"}</a></td>` +
      `<td>${p.ma_san_pham || ""}</td><td>${p.category_1 || ""}</td>` +
      `<td class="so">${p.gia == null ? "" : p.gia.toLocaleString("vi-VN")}</td>` +
      `<td>${p.crawl_status}</td><td>${p.review_reason || ""}</td>`;
    than.appendChild(tr);
  }
}

/* ---- màn 5: so sánh phiên bản ------------------------------------------ */

async function napChonSoSanh() {
  const ds = await api("/api/domains");
  const chon = $("ss-domain");
  chon.innerHTML = "";
  for (const d of ds.filter((x) => x.products > 0)) {
    const o = document.createElement("option");
    o.value = d.domain;
    o.textContent = `${d.brand} (${d.domain})`;
    chon.appendChild(o);
  }
  chon.onchange = napPhienBan;
  await napPhienBan();
}

async function napPhienBan() {
  const ds = await api(`/api/domains/${$("ss-domain").value}/versions`);
  for (const id of ["ss-truoc", "ss-sau"]) {
    const chon = $(id);
    chon.innerHTML = "";
    for (const v of ds) {
      const o = document.createElement("option");
      o.value = v.version;
      o.textContent = `${v.version} (${v.snapshots} snapshot)`;
      chon.appendChild(o);
    }
  }
  if (ds.length > 1) $("ss-sau").value = ds[ds.length - 1].version;
}

$("nut-so-sanh").onclick = async () => {
  const domain = $("ss-domain").value;
  const truoc = $("ss-truoc").value;
  const sau = $("ss-sau").value;
  const kq = await api(
    `/api/domains/${domain}/diff?before=${truoc}&after=${sau}`
  );

  const td = $("ss-thong-diep");
  // Có `message` nghĩa là phép so KHÔNG HỢP LỆ — khác hẳn "hợp lệ và không có
  // gì đổi". Hiện câu thật thay vì một bảng rỗng.
  td.hidden = !kq.message && !kq.skipped_without_snapshot;
  td.textContent = [
    kq.message,
    kq.skipped_without_snapshot
      ? `Bỏ qua ${kq.skipped_without_snapshot} bản ghi không có snapshot (nhập từ .xlsx cũ).`
      : "",
    kq.shared_snapshots ? `So trên ${kq.shared_snapshots} snapshot chung.` : "",
  ]
    .filter(Boolean)
    .join(" ");

  const than = document.querySelector("#bang-so-sanh tbody");
  than.innerHTML = "";
  $("ss-danh-sach").hidden = true;
  for (const c of kq.columns) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${c.field}</td>`;
    for (const nhom of ["va", "hong", "doi"]) {
      const td2 = document.createElement("td");
      td2.className = "so";
      if (c[nhom]) {
        td2.innerHTML = `<span class="bam">${c[nhom]}</span>`;
        td2.querySelector(".bam").onclick = () =>
          xemO(domain, truoc, sau, c.field, nhom);
      } else {
        td2.textContent = "0";
      }
      tr.appendChild(td2);
    }
    than.appendChild(tr);
  }
};

const TEN_NHOM = { va: "vá được", hong: "làm hỏng", doi: "đổi khác" };

async function xemO(domain, truoc, sau, field, nhom) {
  const kq = await api(
    `/api/domains/${domain}/diff/cells?before=${truoc}&after=${sau}` +
      `&field=${field}&group=${nhom}`
  );
  $("ss-danh-sach").hidden = false;
  $("ss-tieu-de").textContent = `${field} — ${TEN_NHOM[nhom]} (${kq.total} sản phẩm)`;
  const hop = $("ss-o");
  hop.innerHTML = "";
  for (const o of kq.cells) {
    const khoi = document.createElement("div");
    khoi.className = "o-doi";
    khoi.innerHTML =
      `<a href="${o.url}" target="_blank" rel="noopener">${o.url}</a>` +
      `<pre class="truoc">${thoat(o.before)}</pre>` +
      `<pre class="sau">${thoat(o.after)}</pre>`;
    hop.appendChild(khoi);
  }
}

const thoat = (v) =>
  v == null
    ? "(trống)"
    : String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/* ---- màn 6: tìm site đối thủ ------------------------------------------- */

$("nut-tim-site").onclick = async () => {
  const tham = new URLSearchParams({ top: $("ts-top").value });
  const nhan = $("ts-nhan").value.trim();
  if (nhan) tham.set("brand", nhan);
  else
    $("ts-tu-khoa")
      .value.split(",")
      .map((x) => x.trim())
      .filter(Boolean)
      .forEach((x) => tham.append("q", x));

  const tt = $("ts-trang-thai");
  tt.hidden = false;
  tt.textContent = "Đang hỏi bộ máy tìm kiếm và tải trang chủ từng ứng viên…";
  $("ts-ket-qua").innerHTML = "";
  $("ts-da-loai").innerHTML = "";

  let kq;
  try {
    kq = await api(`/api/discover?${tham}`);
  } catch (e) {
    tt.textContent = e.message;
    return;
  }
  tt.textContent = `Truy vấn đã dùng: ${kq.queries.join(" · ")}`;

  if (!kq.candidates.length) {
    $("ts-ket-qua").innerHTML =
      '<p class="canh-bao">Không có ứng viên nào. Nếu lặp lại, nhiều khả năng ' +
      "bộ máy tìm kiếm đang chặn — xem log của api.</p>";
    return;
  }

  for (const c of kq.candidates) {
    const khoi = document.createElement("div");
    khoi.className = "domain";
    const dau = c.already_registered
      ? ' <span class="so">← đã có trong registry</span>'
      : "";
    khoi.innerHTML =
      `<header><span class="ten">${c.domain}${dau}</span>` +
      `<span class="so">${c.score} điểm · hạng ${c.best_rank}</span></header>` +
      `<p class="ghi-chu">${thoat(c.title)}</p>`;
    const ul = document.createElement("ul");
    // Hiện TỪNG tín hiệu kèm lý do: một con số trần thì không kiểm chứng được,
    // mà người đọc mới là bên quyết định có crawl domain này hay không.
    for (const s of c.signals) {
      const li = document.createElement("li");
      li.innerHTML =
        `<span style="min-width:2.4rem;display:inline-block">${s.score > 0 ? "+" : ""}${s.score}</span>` +
        `<span>${thoat(s.reason)}</span>`;
      ul.appendChild(li);
    }
    khoi.appendChild(ul);
    const goi = document.createElement("p");
    goi.className = "ghi-chu";
    goi.textContent =
      `Muốn thử: crawl_site.py https://${c.domain} --limit 15 rồi soi bằng report_crawl.py`;
    khoi.appendChild(goi);
    $("ts-ket-qua").appendChild(khoi);
  }

  if (kq.dropped.length) {
    $("ts-da-loai").innerHTML =
      `<h3>Đã loại thẳng (${kq.dropped.length})</h3>` +
      kq.dropped
        .map((d) => `<p class="ghi-chu">${d.domain} — ${thoat(d.reason)}</p>`)
        .join("");
  }
};

/* Mở trang là nạp sẵn danh sách job — người dùng đóng trình duyệt giữa chừng
 * rồi mở lại phải thấy ngay job đang chạy, vì tiến độ nằm trong kho. */
napJob();
