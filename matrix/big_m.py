from fractions import Fraction

MAX_ITER = 200


# ----------------------------------------------------------------------
#  TIỆN ÍCH ĐỊNH DẠNG
# ----------------------------------------------------------------------
def fmt(x):
    """Phân số -> chuỗi: 3, -2, 11/5 ..."""
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def fmt_dec(x):
    """Phân số kèm số thập phân gần đúng nếu không nguyên."""
    x = Fraction(x)
    if x.denominator == 1:
        return fmt(x)
    return f"{fmt(x)} (≈ {float(x):.4f})"


def parse(s):
    """Chuỗi -> Fraction. Hỗ trợ: 3, -2.5, 1/3, ô trống = 0."""
    s = s.strip().replace(",", ".")
    return Fraction(s) if s else Fraction(0)


def fmt_expr(coefs, names):
    """a1*X1 + a2*X2 ... (bỏ hệ số 0, bỏ hệ số 1)."""
    parts = []
    for c, n in zip(coefs, names):
        if c == 0:
            continue
        mag = abs(c)
        body = n if mag == 1 else f"{fmt(mag)}{n}"
        if not parts:
            parts.append(("-" if c < 0 else "") + body)
        else:
            parts.append((" - " if c < 0 else " + ") + body)
    return "".join(parts) or "0"


def fmt_cost(c, m):
    """Hệ số hàm mục tiêu dạng c + m*M."""
    if m == 0:
        return fmt(c)
    mm = "M" if abs(m) == 1 else f"{fmt(abs(m))}M"
    mm = ("-" if m < 0 else "") + mm
    if c == 0:
        return mm
    return f"{fmt(c)}{'+' if m > 0 else ''}{mm}"


# ----------------------------------------------------------------------
#  BỘ GIẢI ĐƠN HÌNH - PHƯƠNG PHÁP M LỚN (Fraction, không sai số)
# ----------------------------------------------------------------------
def giai_big_m(c, A, signs, b, mode):
    """
    c: hệ số hàm mục tiêu, A: ma trận ràng buộc, signs: '<=', '>=', '='
    b: vế phải, mode: 'MAX' | 'MIN'. Các biến đều >= 0.
    Trả về dict gồm toàn bộ các bước (để vẽ bảng) và kết luận.
    """
    n, m = len(c), len(A)
    A = [row[:] for row in A]
    b = b[:]
    signs = signs[:]

    # Đưa vế phải về >= 0
    for i in range(m):
        if b[i] < 0:
            A[i] = [-v for v in A[i]]
            b[i] = -b[i]
            signs[i] = {"<=": ">=", ">=": "<=", "=": "="}[signs[i]]

    n_phu = sum(1 for s in signs if s != "=")
    n_gia = sum(1 for s in signs if s != "<=")
    total = n + n_phu + n_gia
    names = [f"X{j + 1}" for j in range(total)]

    T = [A[i] + [Fraction(0)] * (n_phu + n_gia) for i in range(m)]
    basis = [0] * m
    phu_idx, gia_idx = [], []
    p, g = n, n + n_phu
    for i in range(m):
        if signs[i] == "<=":
            T[i][p] = Fraction(1)
            basis[i] = p
            phu_idx.append(p)
            p += 1
        elif signs[i] == ">=":
            T[i][p] = Fraction(-1)
            phu_idx.append(p)
            p += 1
            T[i][g] = Fraction(1)
            basis[i] = g
            gia_idx.append(g)
            g += 1
        else:
            T[i][g] = Fraction(1)
            basis[i] = g
            gia_idx.append(g)
            g += 1

    Y = b[:]
    cc = list(c) + [Fraction(0)] * (n_phu + n_gia)       # phần số thực của hệ số
    cm = [Fraction(0)] * total                            # phần hệ số M
    for j in gia_idx:
        cm[j] = Fraction(-1) if mode == "MAX" else Fraction(1)
    s = 1 if mode == "MAX" else -1

    info = {
        "n": n, "m": m, "total": total, "names": names, "mode": mode,
        "signs": signs, "A": [row[:] for row in T], "b": b[:],
        "cc": cc[:], "cm": cm[:], "phu_idx": phu_idx, "gia_idx": gia_idx,
    }

    steps = []
    dropped = set()      # biến giả đã ra khỏi cơ sở -> bỏ cột
    status = "lap"
    for _ in range(MAX_ITER):
        dc = [sum(cc[basis[i]] * T[i][j] for i in range(m)) - cc[j] for j in range(total)]
        dm = [sum(cm[basis[i]] * T[i][j] for i in range(m)) - cm[j] for j in range(total)]
        Fc = sum(cc[basis[i]] * Y[i] for i in range(m))
        Fm = sum(cm[basis[i]] * Y[i] for i in range(m))

        # Biến đưa vào: Delta "xấu" nhất (so sánh M trước, số thực sau)
        key = [(s * dm[j], s * dc[j]) for j in range(total)]
        ent = None
        for j in range(total):
            if j not in dropped and key[j] < (0, 0) and (ent is None or key[j] < key[ent]):
                ent = j

        st = {
            "basis": basis[:], "T": [r[:] for r in T], "Y": Y[:],
            "dc": dc, "dm": dm, "Fc": Fc, "Fm": Fm,
            "ent": ent, "leave": None, "lam": [None] * m, "dropped": set(dropped),
        }
        steps.append(st)

        if ent is None:
            if any(basis[i] in gia_idx and Y[i] != 0 for i in range(m)):
                status = "infeasible"
            else:
                status = "optimal"
                alt = [j for j in range(total)
                       if j not in basis and j not in gia_idx and dc[j] == 0 and dm[j] == 0]
                info["alt"] = alt
            break

        lam = [(Y[i] / T[i][ent]) if T[i][ent] > 0 else None for i in range(m)]
        st["lam"] = lam
        valid = [(lam[i], i) for i in range(m) if lam[i] is not None]
        if not valid:
            # còn biến giả dương trong cơ sở -> thực chất là VÔ NGHIỆM, không phải không bị chặn
            if any(basis[i] in gia_idx and Y[i] != 0 for i in range(m)):
                status = "infeasible"
            else:
                status = "unbounded"
            break
        leave = min(valid)[1]
        st["leave"] = leave

        # Phép xoay
        pv = T[leave][ent]
        T[leave] = [v / pv for v in T[leave]]
        Y[leave] = Y[leave] / pv
        for i in range(m):
            if i != leave and T[i][ent] != 0:
                f = T[i][ent]
                T[i] = [T[i][j] - f * T[leave][j] for j in range(total)]
                Y[i] = Y[i] - f * Y[leave]
        if basis[leave] in gia_idx:
            dropped.add(basis[leave])
        basis[leave] = ent

    # Lấy nghiệm cuối cùng
    x_all = [Fraction(0)] * total
    last = steps[-1]

    for i in range(m):
        x_all[last["basis"][i]] = last["Y"][i]

    # Chỉ lấy các biến quyết định ban đầu
    x_nghiem = [x_all[j] for j in range(len(c))]

    info.update({
        "steps": steps,
        "status": status,
        "x": x_nghiem,
        "x_all": x_all,
        "F": last["Fc"]
    })

    return info




# ----------------------------------------------------------------------
#  DỰNG VĂN BẢN HIỂN THỊ: trả về danh sách (đoạn_văn_bản, tag)
#  tag: note | title | hl | ok | bad
# ----------------------------------------------------------------------
def render(info):
    out = []

    def w(text, tag="note"):
        out.append((text, tag))

    n, m, total, names = info["n"], info["m"], info["total"], info["names"]
    mode = info["mode"]
    has_m = bool(info["gia_idx"])
    cc, cm = info["cc"], info["cm"]

    # --- Bài toán dạng chuẩn
    obj = fmt_expr(cc[:n], names[:n])
    for j in info["gia_idx"]:
        obj += f" {'-' if cm[j] < 0 else '+'} M·{names[j]}"
    w("BÀI TOÁN DẠNG CHUẨN (phương pháp M lớn)\n", "title")
    w(f"F(x) = {obj}  →  {mode}\n\n")
    for i in range(m):
        w(f"  {fmt_expr(info['A'][i], names)} = {fmt(info['b'][i])}\n")
    w("\nTrong đó:\n", "title")
    if info["phu_idx"]:
        w("  " + ", ".join(names[j] for j in info["phu_idx"]) + " là biến phụ\n")
    if has_m:
        w("  " + ", ".join(names[j] for j in info["gia_idx"]) + " là biến giả\n")
    w(f"  {names[0]} ... {names[-1]} >= 0\n\n")

    # --- Từng bảng
    for k, st in enumerate(info["steps"]):
        w(f"BẢNG {k + 1}" + (" (bảng đơn hình ban đầu)" if k == 0 else "") + "\n", "title")
        cols = [j for j in range(total) if j not in st["dropped"]]
        pos = {j: 3 + q for q, j in enumerate(cols)}
        header = ["Ci", "Xi", "Yi"] + [names[j] for j in cols] + ["Lamda"]
        rows = []
        for i in range(m):
            bi = st["basis"][i]
            rows.append([fmt_cost(cc[bi], cm[bi]), names[bi], fmt(st["Y"][i])]
                        + [fmt(st["T"][i][j]) for j in cols]
                        + [fmt(st["lam"][i]) if st["lam"][i] is not None else "-"])
        rows.append(["", "F(x)", fmt(st["Fc"])] + [fmt(st["dc"][j]) for j in cols] + [""])
        if has_m:
            rows.append(["", "M", fmt(st["Fm"])] + [fmt(st["dm"][j]) for j in cols] + [""])

        hl = set()
        if st["ent"] is not None:
            e = pos[st["ent"]]
            hl.add((m, e))
            if has_m:
                hl.add((m + 1, e))
            if st["leave"] is not None:
                hl.add((st["leave"], e))
                hl.add((st["leave"], 3 + len(cols)))

        widths = [len(h) for h in header]
        for r in rows:
            for q, cell in enumerate(r):
                widths[q] = max(widths[q], len(cell))
        sep = "+" + "+".join("-" * (wd + 2) for wd in widths) + "+\n"

        def line(cells, r_idx):
            w("|")
            for q, (cell, wd) in enumerate(zip(cells, widths)):
                w(" " + cell.center(wd) + " ", "hl" if (r_idx, q) in hl else "note")
                w("|")
            w("\n")

        w(sep)
        line(header, -1)
        w(sep)
        for r_idx, r in enumerate(rows):
            line(r, r_idx)
            if r_idx == m - 1:
                w(sep)
        w(sep)

        if st["ent"] is not None:
            e_name = names[st["ent"]]
            if mode == "MAX":
                w("Do còn tồn tại giá trị Delta nhỏ hơn 0 nên chưa có phương án tối ưu, cần tìm biến đưa vào\n"
                  f"Cột có giá trị nhỏ nhất ứng với {e_name}, vậy biến đưa vào là : {e_name}\n")
            else:
                w("Do còn tồn tại giá trị Delta lớn hơn 0 nên chưa có phương án tối ưu, cần tìm biến đưa vào\n"
                  f"Cột có giá trị lớn nhất ứng với {e_name}, vậy biến đưa vào là : {e_name}\n")
            if st["leave"] is not None:
                w(f"Hàng có giá trị Lamda nhỏ nhất ứng với cột đó là hàng {st['leave'] + 1}, "
                  f"vậy biến đưa ra là : {names[st['basis'][st['leave']]]}\n")
        w("\n")

    # --- Kết luận
    status, last = info["status"], info["steps"][-1]
    if status == "optimal":
        dau = "không âm" if mode == "MAX" else "không dương"
        w(f"Mọi giá trị Delta đều {dau} nên phương án hiện tại là TỐI ƯU.\n", "ok")
        if info.get("alt"):
            w("Lưu ý: có biến ngoài cơ sở với Delta = 0 (" + ", ".join(names[j] for j in info["alt"]) +
              ") nên bài toán có thể còn phương án tối ưu khác.\n")
        w("\n" + ket_luan(info)[0] + "\n", "ok")
        w(ket_luan(info)[1] + "\n", "ok")
    elif status == "infeasible":
        bad = [names[last["basis"][i]] for i in range(m)
               if last["basis"][i] in info["gia_idx"] and last["Y"][i] != 0]
        w(f"Đã hết Delta xấu nhưng biến giả {', '.join(bad)} vẫn còn trong cơ sở với giá trị khác 0 "
          "→ bài toán VÔ NGHIỆM (không có phương án).\n", "bad")
    elif status == "unbounded":
        w(f"Cột {names[last['ent']]} không có phần tử dương nào → hàm mục tiêu KHÔNG BỊ CHẶN "
          "(bài toán không có phương án tối ưu hữu hạn).\n", "bad")
    else:
        w(f"Dừng sau {MAX_ITER} vòng lặp (nghi ngờ xoay vòng).\n", "bad")
    return out


def ket_luan(info):
    pa = "(" + ", ".join(
        fmt(v) for v in info["x"]
    ) + ")"

    return (
        f"Phương án tối ưu của bài toán là: {pa}",
        f"Giá trị hàm mục tiêu đạt được là: F(x) = {fmt(info['F'])}"
    )


def tom_tat(info):
    """Các dòng tóm tắt cho ô kết quả nhỏ."""
    tt = {"optimal": "Tối ưu (Optimal)", "infeasible": "Vô nghiệm (Infeasible)",
          "unbounded": "Không bị chặn (Unbounded)", "lap": "Không hội tụ"}[info["status"]]
    lines = [f" Trạng thái: {tt}"]
    if info["status"] == "optimal":
        lines += [" " + s for s in ket_luan(info)]
    return lines


def render_text(info):
    return "".join(t for t, _ in render(info))
