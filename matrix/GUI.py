import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lp_bridge                                            # noqa: E402
from big_m import giai_big_m, render, tom_tat, fmt, parse   # noqa: E402

MAX_DIM = 8


class QHTTApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Phần Mềm Quy Hoạch Tuyến Tính - QHTT")
        self.root.geometry("1050x850")

        self._tao_menu()

        tk.Label(root, text="HỆ THỐNG GIẢI TOÁN TỐI ƯU - MA TRẬN HỆ SỐ", font=("Arial", 12, "bold"),
                 fg="#1E3A8A").pack(pady=8)

        # ---- Cấu hình bài toán
        cf = tk.LabelFrame(root, text=" Cấu hình bài toán ", font=("Arial", 10, "bold"), padx=10, pady=8)
        cf.pack(fill="x", padx=15, pady=5)

        tk.Label(cf, text="Số biến X:").grid(row=0, column=0, sticky="w")
        self.spin_vars = tk.Spinbox(cf, from_=1, to=MAX_DIM, width=5)
        self.spin_vars.delete(0, "end")
        self.spin_vars.insert(0, "6")
        self.spin_vars.grid(row=0, column=1, padx=5)

        tk.Label(cf, text="Số ràng buộc:").grid(row=0, column=2, sticky="w", padx=15)
        self.spin_cons = tk.Spinbox(cf, from_=1, to=MAX_DIM, width=5)
        self.spin_cons.delete(0, "end")
        self.spin_cons.insert(0, "3")
        self.spin_cons.grid(row=0, column=3, padx=5)

        tk.Label(cf, text="Mục tiêu:").grid(row=0, column=4, sticky="w", padx=15)
        self.combo_mode = ttk.Combobox(cf, values=["MAX", "MIN"], width=8, state="readonly")
        self.combo_mode.set("MAX")
        self.combo_mode.grid(row=0, column=5, padx=5)

        tk.Button(cf, text="Tạo/Làm mới Bảng", bg="#3B82F6", fg="white", font=("Arial", 9, "bold"),
                  command=self.tao_bang).grid(row=0, column=6, padx=15)

        # ---- Bảng nhập liệu
        self.table_frame = tk.LabelFrame(
            root, text=" Bảng Ma Trận Nhập Liệu (ô trống = 0, cho phép phân số như 1/3; mọi biến Xj >= 0) ",
            font=("Arial", 10, "bold"), padx=10, pady=8)
        self.table_frame.pack(fill="x", padx=15, pady=5)

        # ---- Nút giải bài toán
        bf = tk.Frame(root)
        bf.pack(pady=10)
        tk.Button(bf, text="▶ GIẢI BÀI TOÁN (M LỚN)", bg="#10B981", fg="white",
                  font=("Arial", 11, "bold"), width=30, height=2, command=self.giai_toan).pack()

        # ---- Tóm tắt kết quả
        self.lbl_kq = tk.Label(root, text="Kết quả sẽ hiển thị ở đây sau khi tính...", justify="left",
                               anchor="w", font=("Consolas", 10), bg="#F3F4F6", fg="#1F2937",
                               relief="solid", bd=1, width=120, height=3)
        self.lbl_kq.pack(padx=15, pady=5)

        # ---- Vùng hiển thị chi tiết
        out = tk.LabelFrame(root, text=" Chi tiết các bước giải ", font=("Arial", 10, "bold"), padx=4, pady=4)
        out.pack(fill="both", expand=True, padx=15, pady=6)
        out.rowconfigure(0, weight=1)
        out.columnconfigure(0, weight=1)

        self.txt = tk.Text(out, wrap="none", font=("Consolas", 10), bg="white", state="disabled", height=12)
        sy = ttk.Scrollbar(out, orient="vertical", command=self.txt.yview)
        sx = ttk.Scrollbar(out, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.txt.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")

        self.txt.tag_configure("title", font=("Consolas", 11, "bold"), foreground="#1E3A8A")
        self.txt.tag_configure("note", foreground="#111827")
        self.txt.tag_configure("hl", background="#FDE68A", font=("Consolas", 10, "bold", "underline"))
        self.txt.tag_configure("ok", font=("Consolas", 10, "bold"), foreground="#047857")
        self.txt.tag_configure("bad", font=("Consolas", 10, "bold"), foreground="#B91C1C")

        self.tao_bang()

    # ------------------------------------------------------------------
    #  Menu
    # ------------------------------------------------------------------
    def _tao_menu(self):
        menubar = tk.Menu(self.root)
        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="Mở data.txt...", command=self.mo_file)
        fm.add_command(label="Lưu thành data.txt...", command=self.luu_file)
        fm.add_separator()
        fm.add_command(label="Thoát", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=fm)
        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    #  Tạo bảng ma trận
    # ------------------------------------------------------------------
    def tao_bang(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.entries_c, self.entries_a, self.entries_b, self.sign_vars = [], [], [], []

        try:
            n = int(self.spin_vars.get())
            m = int(self.spin_cons.get())
            if not (1 <= n <= MAX_DIM and 1 <= m <= MAX_DIM):
                raise ValueError
            self.n_vars = n
            self.n_cons = m
        except ValueError:
            messagebox.showerror("Lỗi cấu hình", f"Số biến và số ràng buộc phải từ 1 đến {MAX_DIM}.")
            self.n_vars = 3
            self.n_cons = 3
            self.spin_vars.delete(0, "end")
            self.spin_vars.insert(0, "3")
            self.spin_cons.delete(0, "end")
            self.spin_cons.insert(0, "3")

        hdr = dict(font=("Arial", 9, "bold"), relief="ridge", bg="#E5E7EB")
        tk.Label(self.table_frame, text="Hàm/R.Buộc", width=12, **hdr).grid(row=0, column=0, padx=1, pady=1)
        for j in range(self.n_vars):
            tk.Label(self.table_frame, text=f"X{j + 1}", width=8, **hdr).grid(row=0, column=j + 1, padx=1, pady=1)
        tk.Label(self.table_frame, text="Dấu", width=8, **hdr).grid(row=0, column=self.n_vars + 1, padx=1, pady=1)
        tk.Label(self.table_frame, text="Vế Phải (b)", width=10, **hdr).grid(row=0, column=self.n_vars + 2,
                                                                             padx=1, pady=1)

        # Hàm mục tiêu
        tk.Label(self.table_frame, text="F(x) [Hệ số]", font=("Arial", 9, "bold"), fg="navy",
                 relief="ridge").grid(row=1, column=0, sticky="nsew", padx=1, pady=1)
        for j in range(self.n_vars):
            e = tk.Entry(self.table_frame, width=8, font=("Arial", 10), justify="center")
            e.insert(0, "2" if j == 0 else ("4" if j == 1 else "0"))
            e.grid(row=1, column=j + 1, padx=1, pady=1)
            self.entries_c.append(e)

        # Các ràng buộc
        for i in range(self.n_cons):
            r = i + 2
            tk.Label(self.table_frame, text=f"R. buộc {i + 1}", font=("Arial", 9),
                     relief="ridge").grid(row=r, column=0, sticky="nsew", padx=1, pady=1)

            row_a = []
            for j in range(self.n_vars):
                e = tk.Entry(self.table_frame, width=8, font=("Arial", 10), justify="center")
                e.insert(0, "1")
                e.grid(row=r, column=j + 1, padx=1, pady=1)
                row_a.append(e)
            self.entries_a.append(row_a)

            sg = ttk.Combobox(self.table_frame, values=["<=", ">=", "="], width=5, state="readonly")
            sg.set("<=")
            sg.grid(row=r, column=self.n_vars + 1, padx=1, pady=1)
            self.sign_vars.append(sg)

            eb = tk.Entry(self.table_frame, width=10, font=("Arial", 10), justify="center")
            eb.insert(0, "10")
            eb.grid(row=r, column=self.n_vars + 2, padx=1, pady=1)
            self.entries_b.append(eb)

    # ------------------------------------------------------------------
    #  Đọc dữ liệu
    # ------------------------------------------------------------------
    @staticmethod
    def _dat(entry, text):
        entry.delete(0, "end")
        entry.insert(0, text)

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

    # ------------------------------------------------------------------
    #  Mở / lưu file
    # ------------------------------------------------------------------
    def mo_file(self):
        path = filedialog.askopenfilename(title="Mở data.txt", initialdir=lp_bridge.LP_DIR,
                                          filetypes=[("Text", "*.txt"), ("Tất cả", "*.*")])
        if not path:
            return

        try:
            mode, c, A, signs, b, x0 = lp_bridge.doc_data(path)
            n, m = len(c), len(A)

            if not (1 <= n <= MAX_DIM and 1 <= m <= MAX_DIM):
                raise ValueError(f"Giao diện hỗ trợ tối đa {MAX_DIM} biến và {MAX_DIM} ràng buộc.")

            if (len(signs) != m
                    or len(b) != m
                    or any(len(row) != n for row in A)
                    or any(s not in ["<=", ">=", "="] for s in signs)):
                raise ValueError("Cấu trúc dữ liệu trong file không hợp lệ.")

            if mode not in ["MAX", "MIN"]:
                raise ValueError("Chế độ bài toán trong file không hợp lệ.")
        except Exception as e:
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
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", str(e))

    # ------------------------------------------------------------------
    #  Hiển thị kết quả
    # ------------------------------------------------------------------
    def _xuat(self, segments):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        for text, tag in segments:
            self.txt.insert("end", text, tag)
        self.txt.config(state="disabled")
        self.txt.yview_moveto(0)
        self.txt.xview_moveto(0)

    def _tom_tat(self, lines):
        self.lbl_kq.config(text="\n".join(lines), height=max(3, len(lines)), fg="#1F2937")

    # ------------------------------------------------------------------
    #  Giải bài toán M lớn
    # ------------------------------------------------------------------
    def giai_toan(self):
        prob = self._doc_bai_toan()
        if prob is None:
            return

        try:
            mode, c, A, signs, b = prob
            info = giai_big_m(c, A, signs, b, mode)
            self._xuat(render(info))
            self._tom_tat(tom_tat(info))
        except Exception as e:
            messagebox.showerror("Lỗi khi giải", f"Đã xảy ra lỗi:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = QHTTApp(root)
    root.mainloop()