
import builtins
import contextlib
import importlib.util
import io
import itertools
import os
import re
import tempfile
from fractions import Fraction

import numpy as np

from big_m import giai_big_m, fmt

LP_DIR = os.path.dirname(os.path.abspath(__file__))
_cache = {}


# ----------------------------------------------------------------------
#  Nạp module có tên bắt đầu bằng chữ số (không import thường được)
# ----------------------------------------------------------------------
def nap_module(ten_file):
    if ten_file not in _cache:
        path = os.path.join(LP_DIR, ten_file)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Không thấy {ten_file} trong {LP_DIR}")
        spec = importlib.util.spec_from_file_location("lp_" + ten_file[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cache[ten_file] = mod
    return _cache[ten_file]


@contextlib.contextmanager
def _chay_trong(thu_muc, fake_input=None):
    """chdir vào thư mục tạm, gom print vào buffer, (tuỳ chọn) thay input()."""
    cwd = os.getcwd()
    buf = io.StringIO()
    old_input = builtins.input
    os.chdir(thu_muc)
    try:
        if fake_input is not None:
            builtins.input = fake_input
        with contextlib.redirect_stdout(buf):
            yield buf
    finally:
        builtins.input = old_input
        os.chdir(cwd)


# ----------------------------------------------------------------------
#  Ghi / đọc file data.txt theo đúng định dạng của project
# ----------------------------------------------------------------------
def _so(x):
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else repr(float(x))


def _bieu_thuc(coefs):
    parts = []
    for j, c in enumerate(coefs):
        if c == 0:
            continue
        mag = abs(c)
        body = f"{_so(mag)}*x{j + 1}"
        if not parts:
            parts.append(("-" if c < 0 else "") + body)
        else:
            parts.append((" - " if c < 0 else " + ") + body)
    return "".join(parts) or "0*x1"


def ghi_data(path, mode, c, A, signs, b, x0=None, B=None, force_max=False):
    """
    force_max=True: bài MIN được đổi thành MAX bằng cách đổi dấu c
    (1_dual.py và 1_simplex.py làm việc với dạng max).
    Các ràng buộc xj >= 0 được ghi thành các dòng cuối (đúng quy ước của project).
    """
    n, m = len(c), len(A)
    doi = force_max and mode == "MIN"
    cc = [-v for v in c] if doi else list(c)
    target = "min" if (mode == "MIN" and not force_max) else "max"

    L = ["[POINT]"]
    if x0 is not None:
        L.append(", ".join(str(Fraction(v)) for v in x0))
    L += ["", f"target: {target} {_bieu_thuc(cc)}", "",
          "c: [" + ", ".join(_so(v) for v in cc) + "]", "", "[CONSTRAINTS]"]
    for i in range(m):
        L.append(f"{i + 1} : {_bieu_thuc(A[i])} {signs[i]} {_so(b[i])}")
        L.append("")
    L.append("# Non neg")
    for j in range(n):
        L.append(f"{m + j + 1} : 1*x{j + 1} >= 0")
    if B:
        L += ["", f"B: {list(B)}"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def doc_data(path):
    """
    Đọc data.txt của project vào dạng (mode, c, A, signs, b, x0).
    Bỏ qua các dòng 'xj >= 0' (giao diện mặc định mọi biến >= 0).
    """
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]

    mode, c, x0, cons = "MAX", None, None, []
    in_point = False
    for l in lines:
        low = l.lower()
        if l.startswith("[POINT]") or l.startswith("[PUNTO]"):
            in_point = True
            continue
        if l.startswith("[CONSTRAINTS]") or l.startswith("[VINCOLI]"):
            in_point = False
            continue
        if low.startswith("target"):
            in_point = False
            mode = "MIN" if "min" in low else "MAX"
            continue
        if low.startswith("c:"):
            in_point = False
            c = [Fraction(v.strip()) for v in l.split(":", 1)[1].strip(" []").split(",") if v.strip()]
            continue
        if low.startswith("b:"):
            continue
        if in_point:
            try:
                x0 = [Fraction(v.strip()) for v in l.split(",") if v.strip()]
            except ValueError:
                pass
            continue
        m = re.match(r"^\d+\s*:\s*(.*?)\s*(<=|>=|=)\s*([+\-]?[\d./]+)\s*$", l)
        if m:
            cons.append((m.group(1), m.group(2), Fraction(m.group(3))))

    if c is None:
        raise ValueError("Không thấy dòng 'c: [...]' trong file.")
    n = len(c)
    A, signs, b = [], [], []
    for expr, op, rhs in cons:
        row = [Fraction(0)] * n
        for sg, num, idx in re.findall(r"([+\-]?)\s*(\d+(?:\.\d+)?(?:/\d+)?)?\s*\*?\s*x(\d+)", expr):
            coef = Fraction(num) if num else Fraction(1)
            if sg == "-":
                coef = -coef
            if 1 <= int(idx) <= n:
                row[int(idx) - 1] += coef
        nonzero = [v for v in row if v != 0]
        if op == ">=" and rhs == 0 and len(nonzero) == 1 and nonzero[0] == 1:
            continue                       # dòng xj >= 0
        A.append(row)
        signs.append(op)
        b.append(rhs)
    return mode, c, A, signs, b, x0


def doc_diem(text, n):
    """'4, 0, 2.5, 1/3' -> list Fraction (rỗng -> None)."""
    text = text.strip()
    if not text:
        return None
    vals = [Fraction(v) for v in re.split(r"[,;\s]+", text) if v]
    if len(vals) != n:
        raise ValueError(f"Điểm xuất phát cần đúng {n} toạ độ, bạn nhập {len(vals)}.")
    return vals


# ----------------------------------------------------------------------
#  Chọn cơ sở B (n ràng buộc active độc lập) cho một đỉnh
# ----------------------------------------------------------------------
def _hang_max_form(mode, c, A, signs, b):
    """Các hàng ở dạng max, <= như 1_dual/1_simplex hiểu: (id, a, b, dấu)."""
    n = len(c)
    rows = []
    for i in range(len(A)):
        s = -1 if signs[i] == ">=" else 1
        rows.append((i + 1, [s * v for v in A[i]], s * b[i], signs[i], A[i], b[i]))
    for j in range(n):
        a = [Fraction(0)] * n
        a[j] = Fraction(-1)                 # xj >= 0  <=>  -xj <= 0
        rows.append((len(A) + j + 1, a, Fraction(0), ">=", [Fraction(1) if k == j else Fraction(0)
                                                            for k in range(n)], Fraction(0)))
    return rows


def chon_co_so(mode, c, A, signs, b, x):
    n = len(c)
    c_max = [(-v if mode == "MIN" else v) for v in c]
    rows = _hang_max_form(mode, c, A, signs, b)
    active = [r for r in rows
              if sum(Fraction(a) * Fraction(xv) for a, xv in zip(r[4], x)) == r[5]]
    if len(active) < n:
        return None
    first_indep = None
    for combo in itertools.islice(itertools.combinations(active, n), 20000):
        M = np.array([[float(v) for v in r[1]] for r in combo])
        if abs(np.linalg.det(M)) < 1e-9:
            continue
        ids = sorted(r[0] for r in combo)
        if first_indep is None:
            first_indep = ids
        y = np.linalg.solve(M.T, np.array([float(v) for v in c_max]))
        if all(yv >= -1e-9 or r[3] == "=" for yv, r in zip(y, combo)):
            return ids
    return first_indep


# ----------------------------------------------------------------------
#  CÁC CHỨC NĂNG GỌI SCRIPT CỦA PROJECT (trả về văn bản)
# ----------------------------------------------------------------------
def chay_doi_ngau(mode, c, A, signs, b):
    info = giai_big_m(c, A, signs, b, mode)
    if info["status"] != "optimal":
        return ("Bài toán không có phương án tối ưu hữu hạn "
                f"({info['status']}) nên không tính nghiệm đối ngẫu.\n")
    x = info["x"]
    B = chon_co_so(mode, c, A, signs, b, x)
    if B is None:
        return "Không tìm được cơ sở B tại điểm tối ưu.\n"

    tmp = tempfile.mkdtemp(prefix="qhtt_")
    ghi_data(os.path.join(tmp, "data.txt"), mode, c, A, signs, b, x0=x, B=B, force_max=True)

    head = ("=== ĐỐI NGẪU TẠI ĐỈNH TỐI ƯU (dùng 1_dual.py) ===\n"
            f"Đỉnh tối ưu x* = ({', '.join(fmt(v) for v in x)})\n"
            f"Cơ sở B (ràng buộc active) = {B}   [ràng buộc {len(A) + 1}.. là xj >= 0]\n")
    if mode == "MIN":
        head += "Bài MIN đã đổi thành MAX bằng cách đổi dấu c (F_min = -F_max).\n"
    dual = nap_module("1_dual.py")
    with _chay_trong(tmp) as buf:
        dual.main()
    out = head + "\n" + buf.getvalue()
    dpath = os.path.join(tmp, "dual.txt")
    if os.path.exists(dpath):
        with open(dpath, encoding="utf-8") as f:
            out += "\n" + f.read() + "\n"
    return out


def chay_don_hinh_tung_buoc(mode, c, A, signs, b, x0, max_steps=20):
    n = len(c)
    if x0 is None:
        x0 = [Fraction(0)] * n
        goc = True
    else:
        goc = False
    tmp = tempfile.mkdtemp(prefix="qhtt_")
    data = os.path.join(tmp, "data.txt")
    ghi_data(data, mode, c, A, signs, b, x0=x0, force_max=True)

    start = nap_module("0_start_B.py")
    out = "=== KIỂM TRA ĐIỂM XUẤT PHÁT (dùng 0_start_B.py) ===\n"
    if goc:
        out += "Không nhập x0 -> thử gốc toạ độ (0,...,0).\n"
    if mode == "MIN":
        out += "Bài MIN đã đổi thành MAX bằng cách đổi dấu c.\n"
    with _chay_trong(tmp) as buf:
        try:
            start.solve()
        except SystemExit:
            pass
    out += buf.getvalue()

    sim = nap_module("1_simplex.py")
    sim.OUTPUT_FILE = os.path.join(tmp, "sim_result.txt")
    with open(sim.OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("--- REPORT --- \n")
    with _chay_trong(tmp) as buf:
        cc, xcur, basis, cons = sim.parse_input(data)
    if cc is None or not basis:
        return out + "\nKhông có cơ sở B hợp lệ nên chưa chạy đơn hình. " \
                     "Hãy nhập một đỉnh khả thi vào ô 'Điểm xuất phát x0'.\n"
    if len(basis) != n:
        moi = chon_co_so(mode, c, A, signs, b, x0)

        if moi is None:
            return out + "\nKhông tìm được cơ sở B độc lập tại điểm xuất phát.\n"

        out += f"\n(Đỉnh suy biến: có {len(basis)} ràng buộc active, chọn lại B = {moi})\n"
        basis = moi

    out += "\n=== ĐƠN HÌNH TỪNG BƯỚC (dùng 1_simplex.py) ===\n"
    with _chay_trong(tmp) as buf:
        for k in range(1, max_steps + 1):
            xnew, bnew, xong = sim.solve_step(cc, xcur, basis, cons, k)
            if xong:
                break
            xcur, basis = xnew, bnew
    return out + buf.getvalue()


def chay_nguyen(mode, c, A, signs, b, hoi_cat=None):
    """Nghiệm thư giãn (2_ril.py) rồi cắt Gomory (3_gomory_cut.py)."""
    tmp = tempfile.mkdtemp(prefix="qhtt_")
    data = os.path.join(tmp, "data.txt")
    ghi_data(data, mode, c, A, signs, b, force_max=True)

    ril = nap_module("2_ril.py")
    out = "=== NGHIỆM THƯ GIÃN LIÊN TỤC (dùng 2_ril.py) ===\n"
    with _chay_trong(tmp) as buf:
        A_, b_, c_ = ril.parse_input(data)
        if A_ is not None and len(A_) > 0:
            ril.solve_relaxed(A_, b_, c_)
    out += buf.getvalue()

    out += "\n=== CẮT GOMORY & NGHIỆM NGUYÊN (dùng 3_gomory_cut.py) ===\n"
    try:
        gom = nap_module("3_gomory_cut.py")
    except ModuleNotFoundError as e:
        return out + (f"Thiếu thư viện '{e.name}'. Cài bằng: pip install gurobipy\n"
                      "(2_ril.py ở trên vẫn chạy bình thường.)\n")
    fake = hoi_cat if hoi_cat is not None else (lambda prompt="": "")
    with _chay_trong(tmp, fake_input=fake) as buf:
        params = gom.parse_input(data)
        if params[0] is not None:
            gom.solve_gomory(*params)
    return out + buf.getvalue()