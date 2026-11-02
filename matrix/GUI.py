
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lp_bridge                                            # noqa: E402
from big_m import giai_big_m, render, tom_tat, fmt, parse   # noqa: E402

MAX_VARS = 12
MAX_CONS = 12
MONO = ("Consolas", 10)

# ----------------------------------------------------------------------
#  DỮ LIỆU MẪU
# ----------------------------------------------------------------------
def _vi_du_van_tai():
    c = [8, 6, 10, 9, 12, 13, 14, 9, 16]
    rows, b = [], [20, 30, 25, 10, 35, 30]
    for i in range(3):                                     # 3 kho (cung)
        r = [0] * 9
        for j in range(3):
            r[3 * i + j] = 1
        rows.append(r)
    for j in range(3):                                     # 3 cửa hàng (cầu)
        r = [0] * 9
        for i in range(3):
            r[3 * i + j] = 1
        rows.append(r)
    return {"mode": "MIN", "c": c, "A": rows, "signs": ["="] * 6, "b": b}


VI_DU_LP = {
    "Sản xuất 2 biến (báo cáo, Chương 7)": {
        "mode": "MAX", "c": [3, 2], "A": [[1, 1], [1, 0], [0, 1]],
        "signs": ["<=", "<=", "<="], "b": [4, 2, 3]},
    "Vận tải 3 kho - 3 cửa hàng (báo cáo, Chương 8)": _vi_du_van_tai(),
    "Quy hoạch nguyên (dùng cắt Gomory)": {
        "mode": "MAX", "c": [5, 4], "A": [[6, 4], [1, 2]],
        "signs": ["<=", "<="], "b": [24, 6]},
}

MAU_DO_THI = """# Định dạng cung:  u-v: (chi_phi, dung_luong)
1-2: (2, 4)
1-3: (4, 3)
2-3: (1, 2)
2-4: (6, 3)
3-4: (3, 5)

node costs:
1: -5
2: 0
3: 0
4: 5

# Phân hoạch cơ sở cho đơn hình mạng (T: cây cơ sở, U: cung bão hòa)
T = {(1, 2), (2, 4), (3, 4)}
U = {(1, 3)}
"""

MAU_PNL = {
    "Min: (x1-2)^2 + (x2-1)^2, ràng buộc tuyến tính": """min
vars: x1, x2
f: (x1-2)^2 + (x2-1)^2
g: x1 + x2 - 2, -x1, -x2
x0: 0, 0
step_size: 5
""",
    "Max: -(x1-2)^2 - (x2-1)^2 + 4": """max
vars: x1, x2
f: -(x1-2)^2 - (x2-1)^2 + 4
g: x1 + x2 - 2, -x1, -x2
x0: 0, 0
step_size: 5
""",
}

MAU_DINH = "0, 0\n4, 0\n4, 3\n0, 3\n"

HUONG_DAN = """HƯỚNG DẪN SỬ DỤNG

1) QUY HOẠCH TUYẾN TÍNH / NGUYÊN
   - Chọn số biến, số ràng buộc, MAX/MIN rồi bấm "Tạo/Làm mới bảng" (mọi biến xj >= 0).
   - Ô trống = 0; cho phép phân số (1/3) và số thập phân (2.5).
   - "Giải bằng M lớn": đơn hình bảng với phân số chính xác, vẽ từng bảng.
   - "Đơn hình từng bước": đơn hình theo đỉnh/cơ sở B. Nhập x0 (đỉnh khả thi) hoặc để trống = gốc tọa độ.
   - "Đối ngẫu": lập bài toán đối ngẫu và kiểm tra tối ưu tại đỉnh tối ưu của M lớn.
   - "Nguyên (thư giãn + Gomory)": nghiệm thư giãn + lát cắt Gomory (cần hệ số nguyên và gurobipy).
     Ô "Lát cắt số" = số thứ tự lát cắt muốn kiểm chứng (bỏ trống = bỏ qua).

2) QUY HOẠCH TRÊN MẠNG  (nội dung graph.txt)
   u-v: (chi_phi, dung_luong)      mỗi cung một dòng
   node costs:                      rồi mỗi nút một dòng  nút: cân_bằng   (vào - ra)
   T = {(u,v), ...}   U = {(u,v), ...}   phân hoạch cơ sở cho "Luồng & thế"
   - Dijkstra: nhập nút xuất phát.  - Luồng cực đại: nhập nút nguồn s và nút đích t.

3) QUY HOẠCH PHI TUYẾN  (nội dung pnl.txt)
   min  hoặc  max                   (một dòng riêng)
   vars: x1, x2
   f: biểu thức (dùng ^ cho lũy thừa)
   g: g1, g2, ...                   các ràng buộc dạng g(x) <= 0, cách nhau bằng dấu phẩy (cũng nhận <=, >=)
   x0: điểm xuất phát              step_size: số bước lặp (GUI ghi đè theo ô "Số bước")
   - "Tìm ràng buộc từ các đỉnh": nhập các đỉnh của miền khả thi (mỗi dòng "x, y") để sinh dòng g:.

Mẹo: kết quả hiển thị ở khung bên dưới; dùng nút "Lưu kết quả" để ghi ra file .txt.
"""


class QHTTApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Phần Mềm Tối Ưu Hóa Quy Hoạch Toán Học - QHTT")
        self.root.geometry("1180x900")
        self.root.minsize(980, 700)
        self._busy = False
        self.entries_c, self.entries_a, self.entries_b, self.sign_vars = [], [], [], []
        self.n_vars, self.n_cons = 2, 3

        self._tao_menu()
        tk.Label(root, text="HỆ THỐNG GIẢI TOÁN TỐI ƯU - QUY HOẠCH TOÁN HỌC", font=("Arial", 13, "bold"),
                 fg="#1E3A8A").pack(pady=(8, 2))

        # thanh trạng thái phải pack TRƯỚC khung co giãn để không bị che khi thu nhỏ cửa sổ
        self.lbl_status = tk.Label(root, text="Sẵn sàng", anchor="w", bd=1, relief="sunken", padx=6)
        self.lbl_status.pack(fill="x", side="bottom")

        self.paned = ttk.PanedWindow(root, orient="vertical")
        self.paned.pack(fill="both", expand=True, padx=10, pady=4)
        top = ttk.Frame(self.paned)
        self.paned.add(top, weight=3)
        self.nb = ttk.Notebook(top)
        self.nb.pack(fill="both", expand=True)
        self._tab_lp()
        self._tab_mang()
        self._tab_nlp()
        self._tab_huong_dan()

        bottom = ttk.Frame(self.paned)
        self.paned.add(bottom, weight=2)
        self._khung_ket_qua(bottom)

        self.nap_vi_du_lp(next(iter(VI_DU_LP)))

    # ------------------------------------------------------------------
    #  Menu
    # ------------------------------------------------------------------
    def _tao_menu(self):
        menubar = tk.Menu(self.root)
        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="Mở bài toán LP (data.txt)...", command=self.mo_file)
        fm.add_command(label="Lưu bài toán LP (data.txt)...", command=self.luu_file)
        fm.add_separator()
        fm.add_command(label="Mở đồ thị (graph.txt)...", command=lambda: self._mo_vao_text(self.txt_graph, "graph.txt"))
        fm.add_command(label="Lưu đồ thị (graph.txt)...", command=lambda: self._luu_tu_text(self.txt_graph, "graph.txt"))
        fm.add_separator()
        fm.add_command(label="Mở bài phi tuyến (pnl.txt)...", command=lambda: self._mo_vao_text(self.txt_pnl, "pnl.txt"))
        fm.add_command(label="Lưu bài phi tuyến (pnl.txt)...", command=lambda: self._luu_tu_text(self.txt_pnl, "pnl.txt"))
        fm.add_separator()
        fm.add_command(label="Lưu kết quả đang hiển thị...", command=self.luu_ket_qua)
        fm.add_separator()
        fm.add_command(label="Thoát", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=fm)

        hm = tk.Menu(menubar, tearoff=0)
        hm.add_command(label="Kiểm tra module / thư viện", command=self.kiem_tra_module)
        menubar.add_cascade(label="Trợ giúp", menu=hm)
        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    #  TAB 1: QUY HOẠCH TUYẾN TÍNH / NGUYÊN
    # ------------------------------------------------------------------
    def _tab_lp(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Quy hoạch tuyến tính / nguyên  ")

        cf = tk.LabelFrame(tab, text=" Cấu hình bài toán ", font=("Arial", 10, "bold"), padx=8, pady=6)
        cf.pack(fill="x", padx=8, pady=(6, 3))

        tk.Label(cf, text="Số biến X:").grid(row=0, column=0, sticky="w")
        self.spin_vars = tk.Spinbox(cf, from_=1, to=MAX_VARS, width=4)
        self.spin_vars.grid(row=0, column=1, padx=4)
        tk.Label(cf, text="Số ràng buộc:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.spin_cons = tk.Spinbox(cf, from_=1, to=MAX_CONS, width=4)
        self.spin_cons.grid(row=0, column=3, padx=4)
        tk.Label(cf, text="Mục tiêu:").grid(row=0, column=4, sticky="w", padx=(12, 0))
        self.combo_mode = ttk.Combobox(cf, values=["MAX", "MIN"], width=6, state="readonly")
        self.combo_mode.set("MAX")
        self.combo_mode.grid(row=0, column=5, padx=4)
        tk.Button(cf, text="Tạo/Làm mới bảng", bg="#3B82F6", fg="white", font=("Arial", 9, "bold"),
                  command=self.tao_bang).grid(row=0, column=6, padx=10)
        tk.Label(cf, text="Ví dụ:").grid(row=0, column=7, sticky="w", padx=(12, 0))
        self.combo_vidu = ttk.Combobox(cf, values=list(VI_DU_LP), width=40, state="readonly")
        self.combo_vidu.set(next(iter(VI_DU_LP)))
        self.combo_vidu.grid(row=0, column=8, padx=4)
        tk.Button(cf, text="Nạp ví dụ", command=lambda: self.nap_vi_du_lp(self.combo_vidu.get())
                  ).grid(row=0, column=9, padx=4)

        tf = tk.LabelFrame(tab, text=" Bảng ma trận nhập liệu (ô trống = 0; cho phép phân số 1/3; mọi biến Xj >= 0) ",
                           font=("Arial", 10, "bold"), padx=4, pady=4)
        tf.pack(fill="both", expand=True, padx=8, pady=3)
        canvas = tk.Canvas(tf, height=150, highlightthickness=0)
        sy = ttk.Scrollbar(tf, orient="vertical", command=canvas.yview)
        sx = ttk.Scrollbar(tf, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        self.table_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=self.table_frame, anchor="nw")
        self.table_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        of = tk.Frame(tab)
        of.pack(fill="x", padx=8, pady=2)
        tk.Label(of, text="Điểm xuất phát x0 (đơn hình từng bước):").pack(side="left")
        self.ent_x0 = tk.Entry(of, width=24)
        self.ent_x0.pack(side="left", padx=4)
        tk.Label(of, text="Số bước tối đa:").pack(side="left", padx=(12, 0))
        self.spin_steps = tk.Spinbox(of, from_=1, to=100, width=4)
        self.spin_steps.delete(0, "end")
        self.spin_steps.insert(0, "20")
        self.spin_steps.pack(side="left", padx=4)
        tk.Label(of, text="Lát cắt Gomory số:").pack(side="left", padx=(12, 0))
        self.ent_cut = tk.Entry(of, width=4)
        self.ent_cut.pack(side="left", padx=4)

        bf = tk.Frame(tab)
        bf.pack(pady=4)
        tk.Button(bf, text="▶ GIẢI BẰNG M LỚN", bg="#10B981", fg="white", font=("Arial", 10, "bold"),
                  width=22, height=2, command=self.giai_toan).grid(row=0, column=0, padx=4)
        tk.Button(bf, text="Đơn hình từng bước", bg="#6366F1", fg="white", font=("Arial", 10, "bold"),
                  width=20, height=2, command=self.don_hinh_tung_buoc).grid(row=0, column=1, padx=4)
        tk.Button(bf, text="Bài toán đối ngẫu", bg="#F59E0B", fg="white", font=("Arial", 10, "bold"),
                  width=20, height=2, command=self.doi_ngau).grid(row=0, column=2, padx=4)
        tk.Button(bf, text="Nguyên: thư giãn + Gomory", bg="#EF4444", fg="white", font=("Arial", 10, "bold"),
                  width=24, height=2, command=self.giai_nguyen).grid(row=0, column=3, padx=4)

        self.lbl_kq = tk.Label(tab, text="Kết quả M lớn sẽ hiển thị ở đây sau khi tính...", justify="left",
                               anchor="w", font=MONO, bg="#F3F4F6", fg="#1F2937", relief="solid", bd=1, height=3)
        self.lbl_kq.pack(fill="x", padx=8, pady=(2, 6))

    @staticmethod
    def _dat(entry, text):
        entry.delete(0, "end")
        entry.insert(0, text)

    def tao_bang(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.entries_c, self.entries_a, self.entries_b, self.sign_vars = [], [], [], []

        try:
            n = int(self.spin_vars.get())
            m = int(self.spin_cons.get())
            if not (1 <= n <= MAX_VARS and 1 <= m <= MAX_CONS):
                raise ValueError
            self.n_vars, self.n_cons = n, m
        except ValueError:
            messagebox.showerror("Lỗi cấu hình",
                                 f"Số biến phải từ 1 đến {MAX_VARS}, số ràng buộc từ 1 đến {MAX_CONS}.")
            self.n_vars, self.n_cons = 2, 3
            self._dat(self.spin_vars, "2")
            self._dat(self.spin_cons, "3")

        hdr = dict(font=("Arial", 9, "bold"), relief="ridge", bg="#E5E7EB")
        tk.Label(self.table_frame, text="Hàm/R.Buộc", width=12, **hdr).grid(row=0, column=0, padx=1, pady=1)
        for j in range(self.n_vars):
            tk.Label(self.table_frame, text=f"X{j + 1}", width=8, **hdr).grid(row=0, column=j + 1, padx=1, pady=1)
        tk.Label(self.table_frame, text="Dấu", width=8, **hdr).grid(row=0, column=self.n_vars + 1, padx=1, pady=1)
        tk.Label(self.table_frame, text="Vế Phải (b)", width=10, **hdr).grid(row=0, column=self.n_vars + 2,
                                                                             padx=1, pady=1)

        tk.Label(self.table_frame, text="F(x) [Hệ số]", font=("Arial", 9, "bold"), fg="navy",
                 relief="ridge").grid(row=1, column=0, sticky="nsew", padx=1, pady=1)
        for j in range(self.n_vars):
            e = tk.Entry(self.table_frame, width=8, font=("Arial", 10), justify="center")
            e.insert(0, "0")
            e.grid(row=1, column=j + 1, padx=1, pady=1)
            self.entries_c.append(e)

        for i in range(self.n_cons):
            r = i + 2
            tk.Label(self.table_frame, text=f"R. buộc {i + 1}", font=("Arial", 9),
                     relief="ridge").grid(row=r, column=0, sticky="nsew", padx=1, pady=1)
            row_a = []
            for j in range(self.n_vars):
                e = tk.Entry(self.table_frame, width=8, font=("Arial", 10), justify="center")
                e.insert(0, "0")
                e.grid(row=r, column=j + 1, padx=1, pady=1)
                row_a.append(e)
            self.entries_a.append(row_a)
            sg = ttk.Combobox(self.table_frame, values=["<=", ">=", "="], width=5, state="readonly")
            sg.set("<=")
            sg.grid(row=r, column=self.n_vars + 1, padx=1, pady=1)
            self.sign_vars.append(sg)
            eb = tk.Entry(self.table_frame, width=10, font=("Arial", 10), justify="center")
            eb.insert(0, "0")
            eb.grid(row=r, column=self.n_vars + 2, padx=1, pady=1)
            self.entries_b.append(eb)

    def nap_vi_du_lp(self, ten):
        vd = VI_DU_LP.get(ten)
        if vd is None:
            return
        n, m = len(vd["c"]), len(vd["A"])
        self._dat(self.spin_vars, str(n))
        self._dat(self.spin_cons, str(m))
        self.combo_mode.set(vd["mode"])
        self.tao_bang()
        for j in range(n):
            self._dat(self.entries_c[j], str(vd["c"][j]))
        for i in range(m):
            for j in range(n):
                self._dat(self.entries_a[i][j], str(vd["A"][i][j]))
            self.sign_vars[i].set(vd["signs"][i])
            self._dat(self.entries_b[i], str(vd["b"][i]))
        self._dat(self.ent_x0, "")

    def _doc_bai_toan(self):
        """Trả về (mode, c, A, signs, b) hoặc None nếu dữ liệu không hợp lệ."""
        try:
            mode = self.combo_mode.get()
            if mode not in ["MAX", "MIN"]:
                raise ValueError("Chưa chọn MAX hoặc MIN.")
            c = [parse(e.get()) for e in self.entries_c]
            A = [[parse(self.entries_a[i][j].get()) for j in range(self.n_vars)] for i in range(self.n_cons)]
            signs = [s.get() for s in self.sign_vars]
            b = [parse(e.get()) for e in self.entries_b]
            if any(s not in ["<=", ">=", "="] for s in signs):
                raise ValueError("Vui lòng chọn dấu cho tất cả ràng buộc.")
            return mode, c, A, signs, b
        except (ValueError, ZeroDivisionError) as e:
            messagebox.showerror("Lỗi nhập liệu", "Có dữ liệu không hợp lệ.\n"
                                                  "Ví dụ hợp lệ: 3, -2.5, 1/3.\n\n"
                                                  f"Chi tiết: {e}")
            return None

    # ---- mở / lưu data.txt
    def mo_file(self):
        path = filedialog.askopenfilename(title="Mở data.txt", initialdir=lp_bridge.LP_DIR,
                                          filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            mode, c, A, signs, b, x0 = lp_bridge.doc_data(path)
            n, m = len(c), len(A)
            if not (1 <= n <= MAX_VARS and 1 <= m <= MAX_CONS):
                raise ValueError(f"Giao diện hỗ trợ tối đa {MAX_VARS} biến và {MAX_CONS} ràng buộc.")
            if (len(signs) != m or len(b) != m or any(len(row) != n for row in A)
                    or any(s not in ["<=", ">=", "="] for s in signs)):
                raise ValueError("Cấu trúc dữ liệu trong file không hợp lệ.")
            if mode not in ["MAX", "MIN"]:
                raise ValueError("Chế độ bài toán trong file không hợp lệ.")
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Không đọc được file", str(e))
            return
        self._dat(self.spin_vars, str(n))
        self._dat(self.spin_cons, str(m))
        self.combo_mode.set(mode)
        self.tao_bang()
        for j in range(n):
            self._dat(self.entries_c[j], fmt(c[j]))
        for i in range(m):
            for j in range(n):
                self._dat(self.entries_a[i][j], fmt(A[i][j]))
            self.sign_vars[i].set(signs[i])
            self._dat(self.entries_b[i], fmt(b[i]))
        self._dat(self.ent_x0, ", ".join(fmt(v) for v in x0) if x0 else "")
        messagebox.showinfo("Thành công", "Đã mở dữ liệu bài toán thành công.")

    def luu_file(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return
        path = filedialog.asksaveasfilename(title="Lưu ma trận", initialdir=lp_bridge.LP_DIR,
                                            initialfile="data.txt", defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            lp_bridge.ghi_data(path, *prob)
            messagebox.showinfo("Đã lưu", f"Đã ghi dữ liệu vào:\n{path}")
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Lỗi lưu file", str(e))

    # ---- các nút giải
    def giai_toan(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return
        try:
            mode, c, A, signs, b = prob
            info = giai_big_m(c, A, signs, b, mode)
            self._xuat(render(info))
            self._tom_tat(tom_tat(info))
            self._status("Đã giải xong bằng phương pháp M lớn.")
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Lỗi khi giải", f"Đã xảy ra lỗi:\n{e}")

    def don_hinh_tung_buoc(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return
        mode, c, A, signs, b = prob
        try:
            x0 = lp_bridge.doc_diem(self.ent_x0.get(), len(c))
            buoc = int(self.spin_steps.get())
        except (ValueError, ZeroDivisionError) as e:
            messagebox.showerror("Lỗi nhập liệu", f"Điểm xuất phát hoặc số bước không hợp lệ.\n\n{e}")
            return
        self._chay_nen(lp_bridge.chay_don_hinh_tung_buoc, (mode, c, A, signs, b, x0, buoc))

    def doi_ngau(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return
        self._chay_nen(lp_bridge.chay_doi_ngau, prob)

    def giai_nguyen(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return
        self._chay_nen(lp_bridge.chay_nguyen, (*prob, self.ent_cut.get().strip()))

    # ------------------------------------------------------------------
    #  TAB 2: QUY HOẠCH TRÊN MẠNG
    # ------------------------------------------------------------------
    def _tab_mang(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Quy hoạch trên mạng  ")
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        lf = tk.LabelFrame(tab, text=" Đồ thị (nội dung graph.txt) ", font=("Arial", 10, "bold"), padx=4, pady=4)
        lf.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=6)
        self.txt_graph = self._o_soan_thao(lf)
        self.txt_graph.insert("1.0", MAU_DO_THI)
        bar = tk.Frame(lf)
        bar.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tk.Button(bar, text="Nạp ví dụ", command=lambda: self._dat_text(self.txt_graph, MAU_DO_THI)).pack(side="left", padx=2)
        tk.Button(bar, text="Mở graph.txt...", command=lambda: self._mo_vao_text(self.txt_graph, "graph.txt")).pack(side="left", padx=2)
        tk.Button(bar, text="Lưu graph.txt...", command=lambda: self._luu_tu_text(self.txt_graph, "graph.txt")).pack(side="left", padx=2)

        rf = tk.LabelFrame(tab, text=" Thuật toán ", font=("Arial", 10, "bold"), padx=8, pady=6)
        rf.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=6)
        tk.Label(rf, text="Dijkstra - nút xuất phát:").grid(row=0, column=0, sticky="w")
        self.ent_start = tk.Entry(rf, width=6, justify="center")
        self.ent_start.insert(0, "1")
        self.ent_start.grid(row=0, column=1, padx=4)
        tk.Button(rf, text="Đường đi ngắn nhất (Dijkstra)", bg="#3B82F6", fg="white", width=30,
                  command=self.chay_dijkstra).grid(row=1, column=0, columnspan=2, pady=(2, 12))

        tk.Label(rf, text="Luồng cực đại - nguồn s:").grid(row=2, column=0, sticky="w")
        self.ent_s = tk.Entry(rf, width=6, justify="center")
        self.ent_s.insert(0, "1")
        self.ent_s.grid(row=2, column=1, padx=4)
        tk.Label(rf, text="đích t:").grid(row=3, column=0, sticky="e")
        self.ent_t = tk.Entry(rf, width=6, justify="center")
        self.ent_t.insert(0, "4")
        self.ent_t.grid(row=3, column=1, padx=4)
        tk.Button(rf, text="Luồng cực đại - lát cắt cực tiểu", bg="#10B981", fg="white", width=30,
                  command=self.chay_luong_cuc_dai).grid(row=4, column=0, columnspan=2, pady=(2, 12))

        tk.Button(rf, text="Luồng và thế (đơn hình mạng)", bg="#F59E0B", fg="white", width=30,
                  command=self.chay_luong_the).grid(row=5, column=0, columnspan=2, pady=2)
        tk.Label(rf, text="Cần có node costs, T và U\ntrong nội dung đồ thị.", fg="#6B7280",
                 justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _so_nguyen(self, text, ten):
        try:
            return int(text.strip())
        except ValueError:
            messagebox.showerror("Lỗi nhập liệu", f"{ten} phải là một số nguyên.")
            return None

    def chay_dijkstra(self):
        s = self._so_nguyen(self.ent_start.get(), "Nút xuất phát")
        if s is not None:
            self._chay_nen(lp_bridge.chay_dijkstra, (self._lay_text(self.txt_graph), s))

    def chay_luong_cuc_dai(self):
        s = self._so_nguyen(self.ent_s.get(), "Nút nguồn s")
        t = self._so_nguyen(self.ent_t.get(), "Nút đích t")
        if s is not None and t is not None:
            self._chay_nen(lp_bridge.chay_luong_cuc_dai, (self._lay_text(self.txt_graph), s, t))

    def chay_luong_the(self):
        self._chay_nen(lp_bridge.chay_luong_the, (self._lay_text(self.txt_graph),))

    # ------------------------------------------------------------------
    #  TAB 3: QUY HOẠCH PHI TUYẾN
    # ------------------------------------------------------------------
    def _tab_nlp(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Quy hoạch phi tuyến  ")
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        lf = tk.LabelFrame(tab, text=" Bài toán (nội dung pnl.txt) ", font=("Arial", 10, "bold"), padx=4, pady=4)
        lf.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=6)
        self.txt_pnl = self._o_soan_thao(lf)
        self.txt_pnl.insert("1.0", MAU_PNL[next(iter(MAU_PNL))])
        bar = tk.Frame(lf)
        bar.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.combo_pnl = ttk.Combobox(bar, values=list(MAU_PNL), width=44, state="readonly")
        self.combo_pnl.set(next(iter(MAU_PNL)))
        self.combo_pnl.pack(side="left", padx=2)
        tk.Button(bar, text="Nạp ví dụ", command=lambda: self._dat_text(self.txt_pnl, MAU_PNL[self.combo_pnl.get()])
                  ).pack(side="left", padx=2)
        tk.Button(bar, text="Mở pnl.txt...", command=lambda: self._mo_vao_text(self.txt_pnl, "pnl.txt")).pack(side="left", padx=2)
        tk.Button(bar, text="Lưu pnl.txt...", command=lambda: self._luu_tu_text(self.txt_pnl, "pnl.txt")).pack(side="left", padx=2)

        rf = tk.LabelFrame(tab, text=" Thuật toán ", font=("Arial", 10, "bold"), padx=8, pady=6)
        rf.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=6)
        tk.Label(rf, text="Số bước lặp:").grid(row=0, column=0, sticky="w")
        self.spin_nlp = tk.Spinbox(rf, from_=1, to=100, width=5)
        self._dat(self.spin_nlp, "5")
        self.spin_nlp.grid(row=0, column=1, padx=4)
        tk.Button(rf, text="KKT - phân loại điểm dừng", bg="#3B82F6", fg="white", width=30,
                  command=self.chay_kkt).grid(row=1, column=0, columnspan=2, pady=(6, 3))
        tk.Button(rf, text="Phương pháp Frank-Wolfe", bg="#10B981", fg="white", width=30,
                  command=self.chay_frank_wolfe).grid(row=2, column=0, columnspan=2, pady=3)
        tk.Button(rf, text="Gradient chiếu", bg="#F59E0B", fg="white", width=30,
                  command=self.chay_gradient_chieu).grid(row=3, column=0, columnspan=2, pady=3)

        tk.Label(rf, text="Đỉnh miền khả thi (mỗi dòng: x, y):", anchor="w").grid(row=4, column=0, columnspan=2,
                                                                                  sticky="w", pady=(12, 0))
        self.txt_dinh = tk.Text(rf, width=24, height=5, font=MONO)
        self.txt_dinh.insert("1.0", MAU_DINH)
        self.txt_dinh.grid(row=5, column=0, columnspan=2, sticky="ew")
        tk.Button(rf, text="Tìm ràng buộc từ các đỉnh", width=30,
                  command=self.chay_tim_rang_buoc).grid(row=6, column=0, columnspan=2, pady=4)

    def _so_buoc_nlp(self):
        try:
            n = int(self.spin_nlp.get())
            if n < 1:
                raise ValueError
            return n
        except ValueError:
            messagebox.showerror("Lỗi nhập liệu", "Số bước lặp phải là số nguyên dương.")
            return None

    def chay_kkt(self):
        self._chay_nen(lp_bridge.chay_kkt, (self._lay_text(self.txt_pnl),))

    def chay_frank_wolfe(self):
        n = self._so_buoc_nlp()
        if n is not None:
            self._chay_nen(lp_bridge.chay_frank_wolfe, (self._lay_text(self.txt_pnl), n))

    def chay_gradient_chieu(self):
        n = self._so_buoc_nlp()
        if n is not None:
            self._chay_nen(lp_bridge.chay_gradient_chieu, (self._lay_text(self.txt_pnl), n))

    def chay_tim_rang_buoc(self):
        self._chay_nen(lp_bridge.chay_tim_rang_buoc, (self._lay_text(self.txt_dinh),),
                       sau=self._sau_tim_rang_buoc)

    def _sau_tim_rang_buoc(self, kq):
        van_ban, g = kq
        self._xuat_van_ban(van_ban)
        if g and messagebox.askyesno("Cập nhật pnl.txt",
                                     f"Tìm được các ràng buộc:\n{g}\n\nGhi vào dòng 'g:' của pnl.txt?"):
            self._dat_text(self.txt_pnl, lp_bridge.thay_khoa(self._lay_text(self.txt_pnl), "g", g))

    # ------------------------------------------------------------------
    #  TAB 4: HƯỚNG DẪN
    # ------------------------------------------------------------------
    def _tab_huong_dan(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Hướng dẫn  ")
        t = tk.Text(tab, wrap="word", font=("Arial", 10), padx=10, pady=8)
        t.insert("1.0", HUONG_DAN)
        t.config(state="disabled")
        t.pack(fill="both", expand=True, side="top")
        tk.Button(tab, text="Kiểm tra module / thư viện", command=self.kiem_tra_module).pack(pady=6)

    def kiem_tra_module(self):
        self._xuat_van_ban(lp_bridge.trang_thai_module())

    # ------------------------------------------------------------------
    #  Ô soạn thảo văn bản (graph.txt / pnl.txt) và mở/lưu file
    # ------------------------------------------------------------------
    def _o_soan_thao(self, parent):
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        txt = tk.Text(parent, wrap="none", font=MONO, height=12, undo=True)
        sy = ttk.Scrollbar(parent, orient="vertical", command=txt.yview)
        sx = ttk.Scrollbar(parent, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        txt.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        return txt

    @staticmethod
    def _lay_text(widget):
        return widget.get("1.0", "end").rstrip("\n") + "\n"

    @staticmethod
    def _dat_text(widget, noi_dung):
        widget.delete("1.0", "end")
        widget.insert("1.0", noi_dung)

    def _mo_vao_text(self, widget, ten_goc):
        path = filedialog.askopenfilename(title=f"Mở {ten_goc}", initialdir=lp_bridge.LP_DIR,
                                          filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self._dat_text(widget, f.read())
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Không đọc được file", str(e))

    def _luu_tu_text(self, widget, ten_goc):
        path = filedialog.asksaveasfilename(title=f"Lưu {ten_goc}", initialdir=lp_bridge.LP_DIR,
                                            initialfile=ten_goc, defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._lay_text(widget))
            messagebox.showinfo("Đã lưu", f"Đã ghi vào:\n{path}")
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Lỗi lưu file", str(e))

    # ------------------------------------------------------------------
    #  Khung kết quả dùng chung
    # ------------------------------------------------------------------
    def _khung_ket_qua(self, parent):
        out = tk.LabelFrame(parent, text=" Kết quả / chi tiết các bước giải ", font=("Arial", 10, "bold"),
                            padx=4, pady=4)
        out.pack(fill="both", expand=True)
        out.rowconfigure(1, weight=1)
        out.columnconfigure(0, weight=1)

        bar = tk.Frame(out)
        bar.grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Button(bar, text="Lưu kết quả...", command=self.luu_ket_qua).pack(side="left", padx=2)
        tk.Button(bar, text="Xóa", command=self.xoa_ket_qua).pack(side="left", padx=2)

        self.txt = tk.Text(out, wrap="none", font=MONO, bg="white", state="disabled", height=12)
        sy = ttk.Scrollbar(out, orient="vertical", command=self.txt.yview)
        sx = ttk.Scrollbar(out, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.txt.grid(row=1, column=0, sticky="nsew")
        sy.grid(row=1, column=1, sticky="ns")
        sx.grid(row=2, column=0, sticky="ew")

        self.txt.tag_configure("title", font=("Consolas", 11, "bold"), foreground="#1E3A8A")
        self.txt.tag_configure("note", foreground="#111827")
        self.txt.tag_configure("hl", background="#FDE68A", font=("Consolas", 10, "bold", "underline"))
        self.txt.tag_configure("ok", font=("Consolas", 10, "bold"), foreground="#047857")
        self.txt.tag_configure("bad", font=("Consolas", 10, "bold"), foreground="#B91C1C")

    def _xuat(self, segments):
        """Hiển thị danh sách (đoạn_văn_bản, tag) - dùng cho bộ giải M lớn."""
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        for text, tag in segments:
            self.txt.insert("end", text, tag)
        self.txt.config(state="disabled")
        self.txt.yview_moveto(0)
        self.txt.xview_moveto(0)

    @staticmethod
    def _tag_dong(dong):
        s = dong.strip()
        low = s.lower()
        if s.startswith(("===", ">>>")):
            return "title"
        if any(k in low for k in ("error", "lỗi", "violat", "infeasible", "unbounded", "not optimal",
                                  "thiếu thư viện", "[thiếu]", "not valid", "not found")):
            return "bad"
        if "not" not in low and any(k in low for k in ("optimal", "success", "stationary point",
                                                       "feasibility: yes", "vertex: yes", "[ok]")):
            return "ok"
        return "note"

    def _xuat_van_ban(self, text):
        """Hiển thị văn bản thuần của script (tự tô màu theo từ khóa)."""
        self._xuat([(dong + "\n", self._tag_dong(dong)) for dong in text.splitlines()])

    def _tom_tat(self, lines):
        self.lbl_kq.config(text="\n".join(lines), height=max(3, len(lines)), fg="#1F2937")

    def luu_ket_qua(self):
        noi_dung = self.txt.get("1.0", "end").rstrip("\n")
        if not noi_dung.strip():
            messagebox.showinfo("Chưa có kết quả", "Khung kết quả đang trống.")
            return
        path = filedialog.asksaveasfilename(title="Lưu kết quả", initialdir=lp_bridge.LP_DIR,
                                            initialfile="ket_qua.txt", defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(noi_dung + "\n")
            messagebox.showinfo("Đã lưu", f"Đã ghi kết quả vào:\n{path}")
        except Exception as e:                                       # noqa: BLE001
            messagebox.showerror("Lỗi lưu file", str(e))

    def xoa_ket_qua(self):
        self._xuat([])

    # ------------------------------------------------------------------
    #  Chạy tác vụ nặng ở luồng nền để giao diện không bị treo
    # ------------------------------------------------------------------
    def _status(self, text):
        self.lbl_status.config(text=text)

    def _chay_nen(self, ham, args=(), sau=None):
        if self._busy:
            messagebox.showinfo(
                "Đang tính", "Một phép tính khác đang chạy, vui lòng đợi."
            )
            return
        self._busy = True
        self._status("Đang tính...")
        q = queue.Queue()

        def lam_viec():
            try:
                # Gọi hàm thực thi và bắt toàn bộ kết quả trả về
                res = ham(*args)
                q.put(("ok", res))
            except Exception as e:  # noqa: BLE001
                q.put((
                    "err",
                    f"LỖI: {type(e).__name__}: {e}\n\n{traceback.format_exc()}",
                ))

        threading.Thread(target=lam_viec, daemon=True).start()
        self._cho_ket_qua(q, sau)

    def _cho_ket_qua(self, q, sau):
        try:
            loai, gia_tri = q.get_nowait()
        except queue.Empty:
            self.root.after(100, lambda: self._cho_ket_qua(q, sau))
            return
        self._busy = False
        if loai == "err":
            # Hiển thị trực tiếp lỗi đỏ lên khung kết quả để dễ debug
            self._xuat_van_ban(gia_tri)
            self._status("Có lỗi khi chạy.")
            return
        if sau is not None:
            sau(gia_tri)
        else:
            # Nếu hàm trả về chuỗi hoặc kết quả văn bản, tự động in ra khung kết quả
            if isinstance(gia_tri, str):
                self._xuat_van_ban(gia_tri)
            else:
                self._xuat_van_ban(str(gia_tri))
        self._status("Hoàn thành.")


if __name__ == "__main__":
    root = tk.Tk()
    app = QHTTApp(root)
    root.mainloop()
