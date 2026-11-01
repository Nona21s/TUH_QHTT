# TỐI ƯU HÓA QUY HOẠCH TOÁN HỌC (MATHEMATICAL PROGRAMMING OPTIMIZATION)

## 1. Giới thiệu

Dự án **Tối ưu hóa Quy hoạch toán học (QHTT)** được xây dựng nhằm nghiên cứu, triển khai và ứng dụng các thuật toán giải quyết bài toán tối ưu trong lĩnh vực Quy hoạch toán học.

Hệ thống tập trung vào việc triển khai các phương pháp tối ưu hóa, hỗ trợ tính toán, tìm kiếm nghiệm và trình bày kết quả giải bài toán. Qua đó, dự án góp phần vận dụng kiến thức lý thuyết vào thực hành lập trình và giải quyết các bài toán tối ưu thực tế.

## 2. Nội dung triển khai

Dự án được chia thành bốn nhóm nội dung chính:

### 2.1. Quy hoạch tuyến tính (Linear Programming - LP)

- Phương pháp đơn hình (Simplex Method).
- Phương pháp Big-M.
- Bài toán đối ngẫu (Dual Problem).
- Phương pháp cắt Gomory (Gomory Cutting Plane).

### 2.2. Quy hoạch nguyên (Integer Linear Programming - ILP)

- Bài toán cái túi (Knapsack Problem).
- Bài toán người du lịch (Traveling Salesman Problem - TSP).
- Phương pháp nhánh và cận (Branch and Bound).

### 2.3. Quy hoạch tuyến tính trên mạng (Network Linear Programming)

- Bài toán luồng và thế (Flow and Potential).
- Thuật toán tìm đường đi ngắn nhất Dijkstra.
- Thuật toán luồng cực đại Ford-Fulkerson.

### 2.4. Quy hoạch phi tuyến (Nonlinear Programming - NLP)

- Điều kiện Karush-Kuhn-Tucker (KKT).
- Phương pháp Frank-Wolfe.
- Phương pháp Gradient chiếu (Projected Gradient).
- Xác định và phân loại các điểm dừng.

## 3. Công nghệ sử dụng

| Công nghệ | Mục đích |
|---|---|
| Python | Ngôn ngữ lập trình chính |
| Tkinter | Xây dựng giao diện đồ họa |
| NumPy | Xử lý dữ liệu và ma trận |
| SciPy | Tính toán khoa học và tối ưu hóa |
| SymPy | Tính toán đại số ký hiệu |
| mpmath | Tính toán số học chính xác cao |
| Gurobi | Hỗ trợ giải các bài toán tối ưu |

## 4. Cấu trúc dự án

```text
QHTT_TUH/
│
├── ilp/                 # Quy hoạch nguyên
│   ├── knapsack/
│   └── tsp/
│
├── lp/                  # Quy hoạch tuyến tính
│
├── matrix/              # Giao diện và xử lý ma trận
│   ├── GUI.py
│   ├── big_m.py
│   └── lp_bridge.py
│
├── network_lp/          # Quy hoạch tuyến tính trên mạng
│
├── nlp/                 # Quy hoạch phi tuyến
│
├── requirements.txt     # Danh sách thư viện
└── README.md            # Tài liệu dự án
```

## 5. Cài đặt và sử dụng

**Yêu cầu:** Python và các thư viện cần thiết được khai báo trong `requirements.txt`.

Cài đặt thư viện:

```bash
pip install -r requirements.txt
```

Khởi chạy chương trình giao diện:

```bash
python matrix/GUI.py
```

Người dùng có thể nhập dữ liệu bài toán, lựa chọn dạng tối ưu và thực hiện tính toán thông qua giao diện chương trình.

## 6. Mục tiêu dự án

- Nghiên cứu và vận dụng các phương pháp tối ưu hóa trong Quy hoạch toán học.
- Xây dựng chương trình giải các dạng bài toán tối ưu bằng Python.
- Phân chia và tổ chức mã nguồn theo từng nhóm thuật toán.
- Hỗ trợ quá trình học tập, thực hành và kiểm chứng kết quả tính toán.

## 7. Định hướng phát triển

- Hoàn thiện và mở rộng các thuật toán tối ưu hóa.
- Cải thiện giao diện và khả năng tương tác với người dùng.
- Bổ sung chức năng trực quan hóa quá trình giải.
- Nâng cao khả năng xử lý dữ liệu và kiểm tra kết quả.

---

**Lĩnh vực:** Quy hoạch toán học và Tối ưu hóa  
**Ngôn ngữ lập trình:** Python  
**Mục đích:** Học tập, nghiên cứu và thực hành.
