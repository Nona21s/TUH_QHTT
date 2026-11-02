import builtins
import contextlib
import importlib.util
import io
import itertools
import os
import re
import tempfile
from fractions import Fraction
import sys
import numpy as np

from big_m import giai_big_m, fmt

# --- CẬP NHẬT ĐƯỜNG DẪN ĐỂ TÌM ĐÚNG THƯ MỤC CẤP CHA VÀ THƯ MỤC LP ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LP_DIR = os.path.join(BASE_DIR, "lp")
NETWORK_DIR = os.path.join(BASE_DIR, "network_lp")
NLP_DIR = os.path.join(BASE_DIR, "nlp")
TSP_DIR = os.path.join(BASE_DIR, "tsp")
ILP_DIR = os.path.join(BASE_DIR, "ilp")
MATRIX_DIR = os.path.join(BASE_DIR, "matrix")

# Tự động thêm các thư mục vào sys.path để Python nhận diện module dễ dàng
for d in [LP_DIR, NETWORK_DIR, NLP_DIR, TSP_DIR, ILP_DIR, MATRIX_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

_cache = {}


# ----------------------------------------------------------------------
#  Nạp module có tên bắt đầu bằng chữ số (không import thường được)
# ----------------------------------------------------------------------
def nap_module(ten_file):
  if ten_file not in _cache:
    # Xác định đúng thư mục chứa file tùy theo tên module
    if "flow" in ten_file or "dijkstra" in ten_file or "ford" in ten_file:
      target_dir = NETWORK_DIR
    elif "ril" in ten_file or "gomory" in ten_file:
      target_dir = ILP_DIR
    else:
      target_dir = LP_DIR

    path = os.path.join(target_dir, ten_file)
    if not os.path.exists(path):
      # Thử tìm vét cạn ở toàn bộ các thư mục nếu chưa thấy
      found = False
      for d in [LP_DIR, NETWORK_DIR, NLP_DIR, TSP_DIR, ILP_DIR, MATRIX_DIR]:
        p_test = os.path.join(d, ten_file)
        if os.path.exists(p_test):
          path = p_test
          found = True
          break
      if not found:
        raise FileNotFoundError(f"Không thấy {ten_file} trong hệ thống dự án.")

    spec = importlib.util.spec_from_file_location("mod_" + ten_file[:-3], path)
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
    # Dòng "c: [...]" BẮT BUỘC: 1_simplex.py, 2_ril.py, 3_gomory_cut.py đều đọc dòng này.
    L += ["", f"target: {target} {_bieu_thuc(cc)}", "",
          "c: [" + ", ".join(_so(v) for v in cc) + "]", "", "[CONSTRAINTS]"]
    for i in range(m):
        L.append(f"{i + 1} : {_bieu_thuc(A[i])} {signs[i]} {_so(b[i])}")
        L.append("")
    L.append("# Non neg")
    for j in range(n):
        L.append(f"{m + j + 1} : 1*x{j + 1} >= 0")
    # Chỉ ghi B khi đã biết cơ sở thật (đối ngẫu). Không ghi B giả định, vì
    # 1_simplex.py sẽ chạy với B sai nếu 0_start_B.py không xác nhận được đỉnh.
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
    # 1_dual.py đọc/ghi data.txt, dual.txt theo thư mục chứa chính nó (__file__),
    # nên đánh lừa __file__ trỏ vào thư mục tạm để nó dùng đúng data.txt vừa ghi.
    dual.__file__ = os.path.join(tmp, "1_dual.py")
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
  tmp = tempfile.mkdtemp(prefix='qhtt_')
  data = os.path.join(tmp, 'data.txt')
  ghi_data(data, mode, c, A, signs, b, force_max=True)

  ril = nap_module('2_ril.py')
  out = '=== NGHIỆM THƯ GIÃN LIÊN TỤC (dùng 2_ril.py) ===\n'
  with _chay_trong(tmp) as buf:
    # Sửa ở đây: nhận đủ 5 giá trị trả về từ ril.parse_input(data)
    A_ub, b_ub, A_eq, b_eq, c_ = ril.parse_input(data)
    if c_ is not None and len(c_) > 0:
      ril.solve_relaxed(A_ub, b_ub, A_eq, b_eq, c_)
  out += buf.getvalue()

  out += '\n=== CẮT GOMORY & NGHIỆM NGUYÊN (dùng 3_gomory_cut.py) ===\n'
  try:
    gom = nap_module('3_gomory_cut.py')
  except ModuleNotFoundError as e:
    return out + (
        f"Thiếu thư viện '{e.name}'. Cài bằng: pip install gurobipy\n"
        '(2_ril.py ở trên vẫn chạy bình thường.)\n'
    )
  fake = hoi_cat if hoi_cat is not None else (lambda prompt='': '')
  with _chay_trong(tmp, fake_input=fake) as buf:
    params = gom.parse_input(data)
    if params[0] is not None:
      gom.solve_gomory(*params)
  return out + buf.getvalue()

# ======================================================================
#  CÁC HÀM CẦU NỐI CHO QUY HOẠCH TRÊN MẠNG (Tab 2)
# ======================================================================


def chay_dijkstra(graph_text, start_node):
  tmp = tempfile.mkdtemp(prefix='qhtt_net_')
  gpath = os.path.join(tmp, 'graph.txt')
  with open(gpath, 'w', encoding='utf-8') as f:
    f.write(graph_text)

  dij = nap_module('1_dijkstra.py')
  # Tự định nghĩa lại cách đọc file với utf-8 nếu module đọc trực tiếp
  with _chay_trong(tmp, fake_input=lambda prompt='': str(start_node)) as buf:
    try:
      # Mở file trực tiếp với encoding='utf-8' thay vì để mặc định
      edges = {}
      nodes = set()
      balances = {}
      parsing_nodes = False
      with open('graph.txt', 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
          line = line.strip()
          if not line:
            continue
          if 'node costs' in line.lower():
            parsing_nodes = True
            continue
          if not parsing_nodes:
            clean_line = re.sub(r'\[.*?\]', '', line).strip()
            match = re.search(
                r'(\d+)-(\d+):\s*\(\s*(\d+),\s*(\d+)\s*\)', clean_line
            )
            if match:
              u, v, cost, cap = map(int, match.groups())
              edges[(u, v)] = {'cost': cost, 'capacity': cap}
              nodes.add(u)
              nodes.add(v)
          else:
            parts = line.split(':')
            if len(parts) == 2:
              try:
                n = int(parts[0].strip())
                b = int(parts[1].strip())
                balances[n] = b
                nodes.add(n)
              except ValueError:
                pass
      for n in nodes:
        if n not in balances:
          balances[n] = 0
      nodes = sorted(list(nodes))

      demand = 1
      total_supply = -(len(nodes) - 1) * demand
      for n in nodes:
        if n == start_node:
          balances[n] = total_supply
        else:
          balances[n] = demand

      if edges:
        history, final_dist, final_prev = dij.dijkstra_with_history(
            edges, nodes, start_node
        )
        dij.print_matrix_table(nodes, history)
        T = set()
        for v in nodes:
          u = final_prev[v]
          if u is not None and u != v:
            if (u, v) in edges:
              T.add((u, v))
        print(
            '\nShortest path tree T: { '
            + ', '.join([f'({u}, {v})' for u, v in sorted(list(T))])
            + ' }'
        )
        edge_flows = dij.calculate_flow_matrix(edges, nodes, balances, T)
        vector_values = [
            edge_flows.get(e, 0) for e in sorted(edges.keys())
        ]
        print(f"\nx = ({', '.join(map(str, vector_values))})")
    except Exception as e:
      print(f'Lỗi chạy Dijkstra: {e}')
  return buf.getvalue()


def chay_luong_cuc_dai(graph_text, s, t):
    tmp = tempfile.mkdtemp(prefix='qhtt_net_')
    gpath = os.path.join(tmp, 'graph.txt')
    with open(gpath, 'w', encoding='utf-8') as f:
        f.write(graph_text)

    ff = nap_module('2_ford_fulkerson.py')
    inputs = iter([str(s), str(t)])

    # Vá lỗi đọc file bằng cách ép buộc builtins.open mặc định sang utf-8 khi chạy module này
    orig_open = builtins.open

    def safe_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if 'r' in mode and encoding is None:
            encoding = 'utf-8'
        return orig_open(file, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    builtins.open = safe_open
    try:
        with _chay_trong(tmp, fake_input=lambda prompt='': next(inputs, '')) as buf:
            res = ff.run_max_flow_analysis('graph.txt')
            print(res)
    finally:
        builtins.open = orig_open

    return buf.getvalue()


def chay_luong_the(graph_text):
    tmp = tempfile.mkdtemp(prefix='qhtt_net_')
    gpath = os.path.join(tmp, 'graph.txt')
    with open(gpath, 'w', encoding='utf-8') as f:
        f.write(graph_text)

    net = nap_module('0_flow_pot_simplex.py')

    orig_open = builtins.open

    def safe_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if 'r' in mode and encoding is None:
            encoding = 'utf-8'
        return orig_open(file, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    builtins.open = safe_open
    try:
        with _chay_trong(tmp) as buf:
            edges, nodes = net.parse_graph('graph.txt')
            node_costs = net.parse_node_costs('graph.txt')
            T, U = net.parse_partition('graph.txt')
            if edges and node_costs and T is not None:
                flow = net.calculate_flow_tree(edges, nodes, node_costs, T, U)
                potential = net.calculate_potential(edges, nodes, T)
                print('Initial flow calculated successfully.')
                print('Potential calculated successfully.')
    finally:
        builtins.open = orig_open

    return buf.getvalue()


# ======================================================================
#  CÁC HÀM CẦU NỐI CHO QUY HOẠCH PHI TUYẾN (Tab 3 - NLP)
# ======================================================================


# ======================================================================
#  CÁC HÀM CẦU NỐI CHO QUY HOẠCH PHI TUYẾN (Tab 3 - NLP) - ĐÃ FIX HIỂN THỊ
# ======================================================================

# ======================================================================
#  CÁC HÀM CẦU NỐI CHO QUY HOẠCH PHI TUYẾN (Tab 3 - NLP) - FULL FIX
# ======================================================================

@contextlib.contextmanager
def _mo_utf8():
    """Các script NLP mở file không chỉ định encoding; ép UTF-8 để không lỗi trên Windows."""
    orig_open = builtins.open

    def safe_open(file, mode="r", buffering=-1, encoding=None, errors=None,
                  newline=None, closefd=True, opener=None):
        if "b" not in mode and encoding is None:
            encoding = "utf-8"
        return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    builtins.open = safe_open
    try:
        yield
    finally:
        builtins.open = orig_open


def _chay_nlp(ten_module, tieu_de, pnl_text, ham, fake_input=None):
    """Ghi pnl.txt vào thư mục tạm rồi chạy THẬT script NLP, trả về văn bản đầu ra."""
    tmp = tempfile.mkdtemp(prefix="qhtt_nlp_")
    with open(os.path.join(tmp, "pnl.txt"), "w", encoding="utf-8") as f:
        f.write(pnl_text.rstrip() + "\n")
    try:
        mod = nap_module(ten_module)
    except Exception as e:
        return f"Không nạp được {ten_module}: {e}\n"

    loi = ""
    with _mo_utf8(), _chay_trong(tmp, fake_input=fake_input) as buf:
        try:
            ham(mod)
        except SystemExit:
            pass                      # script tự thoát sau khi in thông báo lỗi
        except Exception as e:
            loi = f"\nLỗi khi chạy {ten_module}: {type(e).__name__}: {e}\n"
    return tieu_de + "\n" + buf.getvalue() + loi


def chay_kkt(pnl_text):
    """KKT + phân loại điểm dừng (dùng 1_categorize.py)."""
    return _chay_nlp("1_categorize.py", "=== KKT - PHÂN LOẠI ĐIỂM DỪNG (dùng 1_categorize.py) ===",
                     pnl_text, lambda m: m.solve())


def chay_frank_wolfe(pnl_text, max_steps):
    """Frank-Wolfe (dùng 2_frank_wolfe.py); số bước lấy từ ô nhập của giao diện."""
    def chay(m):
        mode, f_expr, A, b, x0, vars_sym, _ = m.parsing("pnl.txt")
        if len(A) == 0:
            print("LỖI: Frank-Wolfe cần ít nhất một ràng buộc tuyến tính ở dòng 'g:'.")
            return
        ham = m.frank_wolfe_max if mode == "max" else m.frank_wolfe_min
        ham(f_expr, A, b, x0, vars_sym, int(max_steps))

    return _chay_nlp("2_frank_wolfe.py", f"=== FRANK-WOLFE (dùng 2_frank_wolfe.py, {int(max_steps)} bước) ===",
                     pnl_text, chay)


def chay_gradient_chieu(pnl_text, max_steps):
    """Gradient chiếu (dùng 3_projected_gradient.py); script hỏi số bước nên trả lời tự động."""
    return _chay_nlp("3_projected_gradient.py",
                     f"=== GRADIENT CHIẾU (dùng 3_projected_gradient.py, {int(max_steps)} bước) ===",
                     pnl_text, lambda m: m.projected_gradient("pnl.txt"),
                     fake_input=lambda prompt="": str(int(max_steps)))


def chay_tim_rang_buoc(dinh_text):
    tmp = tempfile.mkdtemp(prefix="qhtt_nlp_")
    vpath = os.path.join(tmp, "v.txt")
    with open(vpath, "w", encoding="utf-8") as f:
        f.write(dinh_text)

    try:
        fc = nap_module("0_find_constr.py")
        buf = io.StringIO()
        orig_open = builtins.open

        def safe_open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
            if "r" in mode and encoding is None:
                encoding = "utf-8"
            return orig_open(file, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

        builtins.open = safe_open
        try:
            with contextlib.redirect_stdout(buf), _chay_trong(tmp):
                # Gọi trực tiếp hàm get_constraints với file v.txt trong thư mục tạm
                fc.get_constraints("v.txt")
        finally:
            builtins.open = orig_open

        output_str = buf.getvalue()
        g_str = ""
        for line in output_str.splitlines():
            if line.startswith("g:"):
                g_str = line.split(":", 1)[1].strip()
                break

        # Nếu module in ra chuỗi g:, ta tách lấy phần hiển thị và phần g_str trả về GUI
        return output_str, g_str
    except Exception as e:
        err_msg = f"Lỗi tìm ràng buộc từ đỉnh: {e}"
        return err_msg, ""


def thay_khoa(text, khoa, gia_tri_moi):
    lines = text.splitlines()
    new_lines = []
    found = False
    for l in lines:
        if l.strip().startswith(khoa + ":"):
            new_lines.append(f"{khoa}: {gia_tri_moi}")
            found = True
        else:
            new_lines.append(l)
    if not found:
        new_lines.append(f"{khoa}: {gia_tri_moi}")
    return "\n".join(new_lines) + "\n"

KNAPSACK_DIR = os.path.join(BASE_DIR, "knapsack")


# ======================================================================
#  CÁC HÀM CẦU NỐI CHO QUY HOẠCH BA LÔ (Knapsack)
# ======================================================================

def chay_knapsack(knapsack_text):
    """Ghi nội dung knapsack.txt vào thư mục tạm và chạy knapsack_solver.py."""
    tmp = tempfile.mkdtemp(prefix="qhtt_knap_")
    kpath = os.path.join(tmp, "knapsack.txt")
    with open(kpath, "w", encoding="utf-8") as f:
        f.write(knapsack_text.rstrip() + "\n")

    try:
        ks = nap_module("knapsack_solver.py")
    except Exception as e:
        return f"Không nạp được knapsack_solver.py: {e}\n"

    with _chay_trong(tmp) as buf:
        try:
            ks.main()
        except Exception as e:
            print(f"Lỗi khi chạy knapsack: {e}")
    return buf.getvalue()
