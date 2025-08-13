import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font as tkfont
from ttkthemes import ThemedTk
import paramiko
import os
import stat
import shutil
from threading import Thread

class SshFileExplorer:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH File Explorer")
        self.root.resizable(False, False)

        # --- 폰트 정의 ---
        self.default_font = tkfont.Font(family="Malgun Gothic", size=10)
        self.listbox_font = tkfont.Font(family="Consolas", size=10)
        self.root.option_add("*Font", self.default_font)

        # --- SSH 클라이언트 초기화 ---
        self.ssh_client = None
        self.sftp_client = None

        # --- 위젯 변수 선언 ---
        self.ip_var = tk.StringVar()
        self.port_var = tk.StringVar(value='22')
        self.user_var = tk.StringVar()
        self.pwd_var = tk.StringVar()
        self.root_dir_var = tk.StringVar(value='/home')
        self.local_path_var = tk.StringVar(value=os.path.expanduser('~'))
        self.remote_path_var = tk.StringVar(value='/')
        self.status_var = tk.StringVar(value="상태: 연결 대기 중")

        # --- GUI 빌드 ---
        self.create_widgets()
        self.update_local_listbox()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """메인 GUI 위젯들을 생성하고 배치합니다."""
        style = ttk.Style()
        style.configure(".", font=self.default_font)
        style.configure("TButton", padding=5)
        
        # --- 프레임 생성 및 배치 ---
        conn_frame = ttk.LabelFrame(self.root, text="서버 접속 정보", padding=10)
        conn_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        
        local_frame = ttk.LabelFrame(self.root, text="로컬 컴퓨터", padding=10)
        local_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ns")

        transfer_frame = ttk.Frame(self.root, padding=10)
        transfer_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ns")

        remote_frame = ttk.LabelFrame(self.root, text="원격 서버", padding=10)
        remote_frame.grid(row=1, column=2, padx=10, pady=5, sticky="ns")

        status_frame = ttk.Frame(self.root, padding=(5, 2))
        status_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 5), sticky="ew")

        # --- 서버 접속 정보 위젯 ---
        ttk.Label(conn_frame, text="Server IP:").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.ip_var, width=15).grid(row=0, column=1, padx=5)
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=5).grid(row=0, column=3, padx=5)
        ttk.Label(conn_frame, text="Username:").grid(row=1, column=0, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.user_var, width=15).grid(row=1, column=1, padx=5)
        ttk.Label(conn_frame, text="Password:").grid(row=1, column=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.pwd_var, show="*", width=15).grid(row=1, column=3, padx=5)
        ttk.Label(conn_frame, text="Root Dir:").grid(row=2, column=0, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.root_dir_var, width=20).grid(row=2, column=1, columnspan=3, sticky="ew", padx=5)
        self.connect_btn = ttk.Button(conn_frame, text="연결", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, rowspan=2, padx=10, ipady=10)

        # --- 로컬 파일 탐색기 위젯 ---
        ttk.Entry(local_frame, textvariable=self.local_path_var, state="readonly").pack(fill="x")
        local_list_frame = ttk.Frame(local_frame)
        local_list_frame.pack(fill="both", expand=True)
        local_scrollbar = ttk.Scrollbar(local_list_frame)
        self.local_listbox = tk.Listbox(local_list_frame, yscrollcommand=local_scrollbar.set, selectmode="extended", width=50, height=20, font=self.listbox_font)
        local_scrollbar.config(command=self.local_listbox.yview)
        self.local_listbox.pack(side="left", fill="both", expand=True)
        local_scrollbar.pack(side="right", fill="y")
        self.local_listbox.bind("<Double-1>", self.on_local_double_click)
        
        ttk.Button(local_frame, text="상위 폴더", command=self.go_up_local_dir).pack(fill="x", pady=(5,0))
        local_action_frame = ttk.Frame(local_frame)
        local_action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(local_action_frame, text="새 폴더", command=self.create_local_directory).pack(side="left", expand=True, fill="x")
        ttk.Button(local_action_frame, text="선택 삭제", command=self.delete_local_items).pack(side="left", expand=True, fill="x")

        # --- 원격 파일 탐색기 위젯 ---
        ttk.Entry(remote_frame, textvariable=self.remote_path_var, state="readonly").pack(fill="x")
        remote_list_frame = ttk.Frame(remote_frame)
        remote_list_frame.pack(fill="both", expand=True)
        remote_scrollbar = ttk.Scrollbar(remote_list_frame)
        self.remote_listbox = tk.Listbox(remote_list_frame, yscrollcommand=remote_scrollbar.set, selectmode="extended", width=50, height=20, font=self.listbox_font)
        remote_scrollbar.config(command=self.remote_listbox.yview)
        self.remote_listbox.pack(side="left", fill="both", expand=True)
        remote_scrollbar.pack(side="right", fill="y")
        self.remote_listbox.bind("<Double-1>", self.on_remote_double_click)
        
        ttk.Button(remote_frame, text="상위 폴더", command=self.go_up_remote_dir).pack(fill="x", pady=(5,0))
        remote_action_frame = ttk.Frame(remote_frame)
        remote_action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(remote_action_frame, text="새 폴더", command=self.create_remote_directory).pack(side="left", expand=True, fill="x")
        ttk.Button(remote_action_frame, text="선택 삭제", command=self.delete_remote_items).pack(side="left", expand=True, fill="x")

        # --- 파일 전송 버튼 위젯 ---
        ttk.Label(transfer_frame, text="").pack(pady=50)
        upload_btn = ttk.Button(transfer_frame, text="업로드 >>", command=lambda: self.start_transfer_thread(self.upload_files))
        upload_btn.pack(pady=20, ipady=10, ipadx=10)
        download_btn = ttk.Button(transfer_frame, text="<< 다운로드", command=lambda: self.start_transfer_thread(self.download_files))
        download_btn.pack(pady=20, ipady=10, ipadx=10)
        ttk.Label(transfer_frame, text="").pack(pady=50)

        # --- 상태바 ---
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x")
    
    def on_closing(self):
        if self.ssh_client:
            self.disconnect_ssh()
        self.root.destroy()

    def toggle_connection(self):
        if self.ssh_client: self.disconnect_ssh()
        else: self.connect_ssh()

    def connect_ssh(self):
        try:
            self.update_status("연결 중...", "blue")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=self.ip_var.get(), port=int(self.port_var.get()), username=self.user_var.get(), password=self.pwd_var.get(), timeout=5)
            self.sftp_client = self.ssh_client.open_sftp()
            
            self.connect_btn.config(text="연결 끊기")
            self.remote_path_var.set(self.root_dir_var.get())
            self.update_remote_listbox()
            self.update_status(f"{self.ip_var.get()}에 연결됨", "green")
        except Exception as e:
            self.disconnect_ssh()
            messagebox.showerror("연결 실패", f"서버에 연결할 수 없습니다:\n{e}")

    def disconnect_ssh(self):
        if self.sftp_client: self.sftp_client.close()
        if self.ssh_client: self.ssh_client.close()
        self.ssh_client, self.sftp_client = None, None
        
        self.connect_btn.config(text="연결")
        self.remote_listbox.delete(0, tk.END)
        self.remote_path_var.set("/")
        self.update_status("연결 끊김", "red")

    def update_local_listbox(self, path=None):
        current_path = path if path is not None else self.local_path_var.get()
        self.local_path_var.set(current_path)
        self.local_listbox.delete(0, tk.END)
        try:
            items = os.listdir(current_path)
            dirs = sorted([f"[D] {item}" for item in items if os.path.isdir(os.path.join(current_path, item))])
            files = sorted([f"[F] {item}" for item in items if os.path.isfile(os.path.join(current_path, item))])
            for item in dirs + files: self.local_listbox.insert(tk.END, item)
        except Exception as e: messagebox.showwarning("오류", f"로컬 디렉토리 접근 오류:\n{e}")

    def update_remote_listbox(self, path=None):
        if not self.sftp_client: return
        current_path = path if path is not None else self.remote_path_var.get()
        self.remote_path_var.set(current_path)
        self.remote_listbox.delete(0, tk.END)
        try:
            dir_list, file_list = [], []
            for attr in self.sftp_client.listdir_attr(current_path):
                if stat.S_ISDIR(attr.st_mode): dir_list.append(f"[D] {attr.filename}")
                else: file_list.append(f"[F] {attr.filename}")
            for item in sorted(dir_list) + sorted(file_list): self.remote_listbox.insert(tk.END, item)
        except Exception as e: messagebox.showwarning("오류", f"원격 디렉토리 접근 오류:\n{e}")

    def on_local_double_click(self, event):
        selection_indices = self.local_listbox.curselection()
        if not selection_indices: return
        selected_item = self.local_listbox.get(selection_indices[0])
        if selected_item.startswith('[D]'):
            self.update_local_listbox(os.path.join(self.local_path_var.get(), selected_item[4:]))

    def on_remote_double_click(self, event):
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: return
        selected_item = self.remote_listbox.get(selection_indices[0])
        if selected_item.startswith('[D]'):
            self.update_remote_listbox(os.path.join(self.remote_path_var.get(), selected_item[4:]).replace("\\", "/"))

    def go_up_local_dir(self):
        self.update_local_listbox(os.path.dirname(self.local_path_var.get()))

    def go_up_remote_dir(self):
        if self.remote_path_var.get() != '/':
            self.update_remote_listbox(os.path.dirname(self.remote_path_var.get()).replace("\\", "/"))
    
    def create_local_directory(self):
        dir_name = simpledialog.askstring("새 폴더 생성", "폴더 이름을 입력하세요:", parent=self.root)
        if not dir_name: return
        try:
            os.mkdir(os.path.join(self.local_path_var.get(), dir_name))
            self.update_local_listbox()
            self.update_status(f"'{dir_name}' 폴더 생성 완료")
        except Exception as e: messagebox.showerror("생성 실패", f"폴더를 생성할 수 없습니다:\n{e}")

    def delete_local_items(self):
        selection_indices = self.local_listbox.curselection()
        if not selection_indices:
            messagebox.showinfo("정보", "삭제할 항목을 선택하세요."); return
        if not messagebox.askyesno("삭제 확인", f"{len(selection_indices)}개의 항목을 정말 삭제하시겠습니까?"): return
        
        for index in reversed(selection_indices):
            item_full = self.local_listbox.get(index)
            item_path = os.path.join(self.local_path_var.get(), item_full[4:])
            try:
                if item_full.startswith('[D]'): shutil.rmtree(item_path)
                else: os.remove(item_path)
            except Exception as e:
                messagebox.showerror("삭제 실패", f"{item_full[4:]} 삭제 중 오류 발생:\n{e}"); break
        self.update_local_listbox()

    def create_remote_directory(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        dir_name = simpledialog.askstring("새 폴더 생성 (원격)", "폴더 이름을 입력하세요:", parent=self.root)
        if not dir_name: return
        try:
            new_dir_path = os.path.join(self.remote_path_var.get(), dir_name).replace("\\", "/")
            self.sftp_client.mkdir(new_dir_path)
            self.update_remote_listbox()
            self.update_status(f"원격 폴더 '{dir_name}' 생성 완료")
        except Exception as e: messagebox.showerror("생성 실패", f"원격 폴더를 생성할 수 없습니다:\n{e}")

    def delete_remote_items(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "삭제할 항목을 선택하세요."); return
        if not messagebox.askyesno("삭제 확인 (원격)", f"{len(selection_indices)}개의 원격 항목을 정말 삭제하시겠습니까?"): return

        for index in reversed(selection_indices):
            item_full = self.remote_listbox.get(index)
            item_path = os.path.join(self.remote_path_var.get(), item_full[4:]).replace("\\", "/")
            try:
                if item_full.startswith('[D]'): self.sftp_client.rmdir(item_path)
                else: self.sftp_client.remove(item_path)
            except Exception as e:
                messagebox.showerror("삭제 실패", f"{item_full[4:]} 삭제 중 오류 발생:\n{e}"); break
        self.update_remote_listbox()

    def start_transfer_thread(self, target_func):
        thread = Thread(target=target_func, daemon=True)
        thread.start()

    def upload_files(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.local_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "업로드할 파일을 선택하세요."); return
        
        remote_base_path = self.remote_path_var.get()
        local_base_path = self.local_path_var.get()
        for index in selection_indices:
            item_full = self.local_listbox.get(index)
            if item_full.startswith('[F]'):
                file_name = item_full[4:]
                local_file = os.path.join(local_base_path, file_name)
                remote_file = os.path.join(remote_base_path, file_name).replace("\\", "/")
                try:
                    self.update_status(f"업로드 중: {file_name}", "blue")
                    self.sftp_client.put(local_file, remote_file)
                except Exception as e:
                    messagebox.showerror("업로드 실패", f"{file_name} 업로드 중 오류:\n{e}")
                    self.update_status("업로드 실패", "red"); return
        self.update_status("업로드 완료", "green")
        self.update_remote_listbox()

    def download_files(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "다운로드할 파일을 선택하세요."); return

        remote_base_path = self.remote_path_var.get()
        local_base_path = self.local_path_var.get()
        for index in selection_indices:
            item_full = self.remote_listbox.get(index)
            if item_full.startswith('[F]'):
                file_name = item_full[4:]
                remote_file = os.path.join(remote_base_path, file_name).replace("\\", "/")
                local_file = os.path.join(local_base_path, file_name)
                try:
                    self.update_status(f"다운로드 중: {file_name}", "blue")
                    self.sftp_client.get(remote_file, local_file)
                except Exception as e:
                    messagebox.showerror("다운로드 실패", f"{file_name} 다운로드 중 오류:\n{e}")
                    self.update_status("다운로드 실패", "red"); return
        self.update_status("다운로드 완료", "green")
        self.update_local_listbox()

    def update_status(self, message, color="black"):
        self.status_var.set(f"상태: {message}")
        self.status_label.config(foreground=color)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = ThemedTk(theme="ubuntu")
    app = SshFileExplorer(root)
    root.mainloop()