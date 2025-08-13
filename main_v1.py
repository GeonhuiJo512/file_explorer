import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font as tkfont
from ttkthemes import ThemedTk
import paramiko
import os
import stat
import shutil
from threading import Thread
from datetime import datetime
import json

# --- 설정 파일 경로 정의 ---
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.SshFileExplorer', 'config')

class ProfileEditDialog(tk.Toplevel):
    """프로필을 새로 추가하거나 편집하는 대화상자 클래스"""
    def __init__(self, parent_window, main_app_ref, initial_data=None):
        super().__init__(parent_window)
        self.transient(parent_window)
        self.grab_set()
        self.main_app = main_app_ref
        
        self.title("새 프로필 추가" if not initial_data else "프로필 편집")
        self.geometry("350x230")

        self.ip_var = tk.StringVar()
        self.port_var = tk.StringVar(value='22')
        self.user_var = tk.StringVar()
        self.pwd_var = tk.StringVar()
        self.root_dir_var = tk.StringVar(value='/home')

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="서버 IP:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.ip_var, width=30).grid(row=0, column=1, sticky="ew")
        ttk.Label(frame, text="포트:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.port_var, width=30).grid(row=1, column=1, sticky="ew")
        ttk.Label(frame, text="사용자 이름:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.user_var, width=30).grid(row=2, column=1, sticky="ew")
        ttk.Label(frame, text="비밀번호:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.pwd_var, show="*", width=30).grid(row=3, column=1, sticky="ew")
        ttk.Label(frame, text="시작 디렉토리:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.root_dir_var, width=30).grid(row=4, column=1, sticky="ew")
        
        btn_frame = ttk.Frame(self, padding=(0, 10, 0, 0))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="저장", command=self.save).pack(side="right", padx=15)
        ttk.Button(btn_frame, text="취소", command=self.destroy).pack(side="right")
        
        if initial_data:
            self.ip_var.set(initial_data.get('ip', ''))
            self.port_var.set(initial_data.get('port', '22'))
            self.user_var.set(initial_data.get('user', ''))
            self.pwd_var.set(initial_data.get('pwd', ''))
            self.root_dir_var.set(initial_data.get('root_dir', '/home'))

    def save(self):
        ip = self.ip_var.get().strip()
        user = self.user_var.get().strip()
        port = self.port_var.get().strip()
        if not (ip and user and port):
            messagebox.showerror("입력 오류", "IP, 포트, 사용자 이름은 필수입니다.", parent=self)
            return
        config_data = {'ip': ip, 'port': port, 'user': user, 'pwd': self.pwd_var.get(), 'root_dir': self.root_dir_var.get()}
        filename = f"{user}@{ip}_{port}.json"
        filepath = os.path.join(CONFIG_DIR, filename)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.main_app.load_profiles_to_listbox()
            self.destroy()
        except Exception as e:
            messagebox.showerror("저장 실패", f"프로필 저장 중 오류 발생:\n{e}", parent=self)

class SshFileExplorer:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH File Explorer")
        self.root.resizable(False, False)

        self.default_font = tkfont.Font(family="Malgun Gothic", size=10)
        self.listbox_font = tkfont.Font(family="Consolas", size=10)
        self.root.option_add("*Font", self.default_font)

        self.ssh_client = None
        self.sftp_client = None
        self.profile_map = {}

        self.ip_var = tk.StringVar()
        self.port_var = tk.StringVar(value='22')
        self.user_var = tk.StringVar()
        self.pwd_var = tk.StringVar()
        self.root_dir_var = tk.StringVar(value='/home')
        self.local_path_var = tk.StringVar(value=os.path.expanduser('~'))
        self.remote_path_var = tk.StringVar(value='/')
        self.status_var = tk.StringVar(value="상태: 연결 대기 중")

        self.create_widgets()
        self.load_profiles_to_listbox()
        self.update_local_listbox()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        style = ttk.Style()
        style.configure(".", font=self.default_font)
        style.configure("TButton", padding=5)
        
        conn_frame = ttk.LabelFrame(self.root, text="서버 접속 정보", padding=10)
        conn_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        
        conn_frame.columnconfigure(0, weight=1)
        conn_frame.columnconfigure(1, weight=1)

        input_panel = ttk.Frame(conn_frame)
        input_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ttk.Label(input_panel, text="Server IP:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(input_panel, textvariable=self.ip_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Port:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(input_panel, textvariable=self.port_var).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Username:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(input_panel, textvariable=self.user_var).grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Password:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(input_panel, textvariable=self.pwd_var, show="*").grid(row=3, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Root Dir:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(input_panel, textvariable=self.root_dir_var).grid(row=4, column=1, sticky="ew", padx=5)
        self.connect_btn = ttk.Button(input_panel, text="연결", command=self.toggle_connection)
        self.connect_btn.grid(row=5, column=0, columnspan=2, pady=(10,0), sticky="ew")
        input_panel.columnconfigure(1, weight=1)

        # LabelFrame을 일반 Frame으로 변경하여 테두리와 제목 제거
        profile_panel = ttk.Frame(conn_frame)
        profile_panel.grid(row=0, column=1, sticky="nsew", padx=(10,0))
        
        profile_list_frame = ttk.Frame(profile_panel)
        profile_list_frame.pack(fill="both", expand=True, pady=(0,5))
        profile_scrollbar = ttk.Scrollbar(profile_list_frame)
        self.profile_listbox = tk.Listbox(profile_list_frame, yscrollcommand=profile_scrollbar.set, exportselection=False, height=6) # 높이 축소 (8->6)
        profile_scrollbar.config(command=self.profile_listbox.yview)
        profile_scrollbar.pack(side="right", fill="y")
        self.profile_listbox.pack(side="left", fill="both", expand=True)
        self.profile_listbox.bind("<<ListboxSelect>>", self.on_profile_selected)

        profile_btn_frame = ttk.Frame(profile_panel)
        profile_btn_frame.pack(fill="x")
        ttk.Button(profile_btn_frame, text="추가 (+)", command=self._add_new_profile).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(profile_btn_frame, text="삭제 (-)", command=self._delete_selected_profile).pack(side="left", expand=True, fill="x", padx=(2, 0))

        # --- 나머지 프레임들 ---
        local_frame = ttk.LabelFrame(self.root, text="로컬 컴퓨터", padding=10)
        local_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ns")
        transfer_frame = ttk.Frame(self.root, padding=10)
        transfer_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ns")
        remote_frame = ttk.LabelFrame(self.root, text="원격 서버", padding=10)
        remote_frame.grid(row=1, column=2, padx=10, pady=5, sticky="ns")
        status_frame = ttk.Frame(self.root, padding=(5, 2))
        status_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 5), sticky="ew")
        
        local_path_entry = ttk.Entry(local_frame, textvariable=self.local_path_var)
        local_path_entry.pack(fill="x")
        local_path_entry.bind("<Return>", self.on_local_path_enter)
        local_list_frame = ttk.Frame(local_frame)
        local_list_frame.pack(fill="both", expand=True)
        local_scrollbar = ttk.Scrollbar(local_list_frame)
        # 리스트박스 높이 축소 (20 -> 16)
        self.local_listbox = tk.Listbox(local_list_frame, yscrollcommand=local_scrollbar.set, selectmode="extended", width=70, height=16, font=self.listbox_font)
        local_scrollbar.config(command=self.local_listbox.yview)
        self.local_listbox.pack(side="left", fill="both", expand=True)
        local_scrollbar.pack(side="right", fill="y")
        self.local_listbox.bind("<Double-1>", self.on_local_double_click)
        ttk.Button(local_frame, text="상위 폴더", command=self.go_up_local_dir).pack(fill="x", pady=(5,0))
        local_action_frame = ttk.Frame(local_frame)
        local_action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(local_action_frame, text="새 폴더", command=self.create_local_directory).pack(side="left", expand=True, fill="x")
        ttk.Button(local_action_frame, text="선택 삭제", command=self.delete_local_items).pack(side="left", expand=True, fill="x")
        
        remote_path_entry = ttk.Entry(remote_frame, textvariable=self.remote_path_var)
        remote_path_entry.pack(fill="x")
        remote_path_entry.bind("<Return>", self.on_remote_path_enter)
        remote_list_frame = ttk.Frame(remote_frame)
        remote_list_frame.pack(fill="both", expand=True)
        remote_scrollbar = ttk.Scrollbar(remote_list_frame)
        # 리스트박스 높이 축소 (20 -> 16)
        self.remote_listbox = tk.Listbox(remote_list_frame, yscrollcommand=remote_scrollbar.set, selectmode="extended", width=70, height=16, font=self.listbox_font)
        remote_scrollbar.config(command=self.remote_listbox.yview)
        self.remote_listbox.pack(side="left", fill="both", expand=True)
        remote_scrollbar.pack(side="right", fill="y")
        self.remote_listbox.bind("<Double-1>", self.on_remote_double_click)
        ttk.Button(remote_frame, text="상위 폴더", command=self.go_up_remote_dir).pack(fill="x", pady=(5,0))
        remote_action_frame = ttk.Frame(remote_frame)
        remote_action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(remote_action_frame, text="새 폴더", command=self.create_remote_directory).pack(side="left", expand=True, fill="x")
        ttk.Button(remote_action_frame, text="선택 삭제", command=self.delete_remote_items).pack(side="left", expand=True, fill="x")
        
        # 전송 프레임의 상하 여백 축소 (50 -> 30)
        ttk.Label(transfer_frame, text="").pack(pady=30)
        upload_btn = ttk.Button(transfer_frame, text="업로드 >>", command=lambda: self.start_transfer_thread(self.upload_items))
        upload_btn.pack(pady=10, ipady=10, ipadx=10)
        download_btn = ttk.Button(transfer_frame, text="<< 다운로드", command=lambda: self.start_transfer_thread(self.download_items))
        download_btn.pack(pady=10, ipady=10, ipadx=10)
        ttk.Label(transfer_frame, text="").pack(pady=30)
        
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x")

    def _get_profile_filename(self, ip, user, port):
        return f"{user}@{ip}_{port}.json"

    def load_profiles_to_listbox(self):
        self.profile_listbox.delete(0, tk.END)
        self.profile_map.clear()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            for filename in sorted(os.listdir(CONFIG_DIR)):
                if filename.endswith('.json'):
                    filepath = os.path.join(CONFIG_DIR, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    display_text = f"{config.get('user')}@{config.get('ip')}:{config.get('port')}"
                    self.profile_listbox.insert(tk.END, display_text)
                    self.profile_map[display_text] = filename
        except Exception as e:
            messagebox.showwarning("오류", f"프로필 목록을 불러오는 중 오류 발생:\n{e}")
            
    def on_profile_selected(self, event=None):
        selection_indices = self.profile_listbox.curselection()
        if not selection_indices: return
        display_text = self.profile_listbox.get(selection_indices[0])
        filename = self.profile_map.get(display_text)
        if filename:
            filepath = os.path.join(CONFIG_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.load_connection_profile(config)
            except Exception as e:
                messagebox.showerror("오류", f"프로필 파일을 읽는 중 오류 발생:\n{e}")

    def _add_new_profile(self):
        ProfileEditDialog(self.root, self)

    def _delete_selected_profile(self):
        selection_indices = self.profile_listbox.curselection()
        if not selection_indices:
            messagebox.showinfo("정보", "삭제할 프로필을 목록에서 선택하세요.", parent=self.root)
            return
        display_text = self.profile_listbox.get(selection_indices[0])
        if not messagebox.askyesno("삭제 확인", f"'{display_text}' 프로필을 정말 삭제하시겠습니까?", parent=self.root):
            return
        filename = self.profile_map.get(display_text)
        if filename:
            filepath = os.path.join(CONFIG_DIR, filename)
            try:
                os.remove(filepath)
                self.load_profiles_to_listbox()
                self.update_status(f"'{display_text}' 프로필을 삭제했습니다.", "blue")
            except Exception as e:
                messagebox.showerror("삭제 실패", f"프로필 삭제 중 오류 발생:\n{e}", parent=self.root)

    def _prompt_and_save_profile(self):
        ip = self.ip_var.get().strip(); user = self.user_var.get().strip(); port = self.port_var.get().strip()
        if not (ip and user and port): return
        filename = self._get_profile_filename(ip, user, port)
        filepath = os.path.join(CONFIG_DIR, filename)
        if not os.path.exists(filepath):
            if messagebox.askyesno("프로필 저장", "이 연결 정보를 프로필에 저장하시겠습니까?", parent=self.root):
                config_data = {'ip': ip, 'port': port, 'user': user, 'pwd': self.pwd_var.get(), 'root_dir': self.root_dir_var.get()}
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=4)
                    self.load_profiles_to_listbox()
                    self.update_status(f"'{user}@{ip}' 프로필을 저장했습니다.", "blue")
                except Exception as e:
                    messagebox.showerror("저장 실패", f"프로필 저장 중 오류 발생:\n{e}", parent=self.root)

    def connect_ssh(self):
        self._prompt_and_save_profile()
        try:
            self.update_status("연결 중...", "blue"); self.root.update_idletasks()
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
            
    def load_connection_profile(self, config):
        self.ip_var.set(config.get('ip', '')); self.port_var.set(config.get('port', '22'))
        self.user_var.set(config.get('user', '')); self.pwd_var.set(config.get('pwd', ''))
        self.root_dir_var.set(config.get('root_dir', '/home'))
        display_text = f"{config.get('user')}@{config.get('ip')}:{config.get('port')}"
        self.update_status(f"'{display_text}' 프로필을 불러왔습니다.", "blue")
        
    def _parse_item_name(self, item_string):
        if not item_string: return ""
        return item_string[4:50].strip()
    def on_closing(self):
        if self.ssh_client: self.disconnect_ssh()
        self.root.destroy()
    def toggle_connection(self):
        if self.ssh_client: self.disconnect_ssh()
        else: self.connect_ssh()
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
            dir_list, file_list = [], []
            for item in items:
                try:
                    full_path = os.path.join(current_path, item)
                    mtime = os.path.getmtime(full_path)
                    dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    display_name = f" [D] {item}" if os.path.isdir(full_path) else f" [F] {item}"
                    formatted_item = f"{display_name:<50}{dt_str}"
                    if os.path.isdir(full_path): dir_list.append(formatted_item)
                    else: file_list.append(formatted_item)
                except OSError: continue
            for item in sorted(dir_list) + sorted(file_list): self.local_listbox.insert(tk.END, item)
        except Exception as e: messagebox.showwarning("오류", f"로컬 디렉토리 접근 오류:\n{e}")
    def update_remote_listbox(self, path=None):
        if not self.sftp_client: return
        current_path = path if path is not None else self.remote_path_var.get()
        original_path = self.remote_path_var.get()
        self.remote_path_var.set(current_path)
        self.remote_listbox.delete(0, tk.END)
        try:
            dir_list, file_list = [], []
            for attr in self.sftp_client.listdir_attr(current_path):
                mtime = attr.st_mtime
                dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                display_name = f" [D] {attr.filename}" if stat.S_ISDIR(attr.st_mode) else f" [F] {attr.filename}"
                formatted_item = f"{display_name:<50}{dt_str}"
                if stat.S_ISDIR(attr.st_mode): dir_list.append(formatted_item)
                else: file_list.append(formatted_item)
            for item in sorted(dir_list) + sorted(file_list): self.remote_listbox.insert(tk.END, item)
        except Exception as e:
             messagebox.showwarning("오류", f"원격 디렉토리 접근 오류:\n{e}")
             self.remote_path_var.set(original_path)
    def on_local_path_enter(self, event):
        new_path = self.local_path_var.get()
        if not os.path.isdir(new_path): messagebox.showwarning("경로 오류", f"존재하지 않거나 디렉터리가 아닌 경로입니다:\n{new_path}"); return
        self.update_local_listbox(new_path)
    def on_remote_path_enter(self, event):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        new_path = self.remote_path_var.get().replace("\\", "/")
        self.update_remote_listbox(new_path)
    def on_local_double_click(self, event):
        selection_indices = self.local_listbox.curselection()
        if not selection_indices: return
        selected_item = self.local_listbox.get(selection_indices[0])
        if selected_item.strip().startswith('[D]'):
            dir_name = self._parse_item_name(selected_item)
            self.update_local_listbox(os.path.join(self.local_path_var.get(), dir_name))
    def on_remote_double_click(self, event):
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: return
        selected_item = self.remote_listbox.get(selection_indices[0])
        if selected_item.strip().startswith('[D]'):
            dir_name = self._parse_item_name(selected_item)
            new_path = os.path.join(self.remote_path_var.get(), dir_name).replace("\\", "/")
            self.update_remote_listbox(new_path)
    def go_up_local_dir(self): self.update_local_listbox(os.path.dirname(self.local_path_var.get()))
    def go_up_remote_dir(self):
        if self.remote_path_var.get() != '/': self.update_remote_listbox(os.path.dirname(self.remote_path_var.get()).replace("\\", "/"))
    def create_local_directory(self):
        dir_name = simpledialog.askstring("새 폴더 생성", "폴더 이름을 입력하세요:", parent=self.root)
        if not dir_name: return
        try:
            os.mkdir(os.path.join(self.local_path_var.get(), dir_name))
            self.update_local_listbox(); self.update_status(f"'{dir_name}' 폴더 생성 완료")
        except Exception as e: messagebox.showerror("생성 실패", f"폴더를 생성할 수 없습니다:\n{e}")
    def delete_local_items(self):
        selection_indices = self.local_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "삭제할 항목을 선택하세요."); return
        if not messagebox.askyesno("삭제 확인", f"{len(selection_indices)}개의 항목을 정말 삭제하시겠습니까?"): return
        for index in reversed(selection_indices):
            item_full = self.local_listbox.get(index)
            item_name = self._parse_item_name(item_full)
            item_path = os.path.join(self.local_path_var.get(), item_name)
            try:
                if item_full.strip().startswith('[D]'): shutil.rmtree(item_path)
                else: os.remove(item_path)
            except Exception as e: messagebox.showerror("삭제 실패", f"{item_name} 삭제 중 오류 발생:\n{e}"); break
        self.update_local_listbox()
    def create_remote_directory(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        dir_name = simpledialog.askstring("새 폴더 생성 (원격)", "폴더 이름을 입력하세요:", parent=self.root)
        if not dir_name: return
        try:
            new_dir_path = os.path.join(self.remote_path_var.get(), dir_name).replace("\\", "/")
            self.sftp_client.mkdir(new_dir_path)
            self.update_remote_listbox(); self.update_status(f"원격 폴더 '{dir_name}' 생성 완료")
        except Exception as e: messagebox.showerror("생성 실패", f"원격 폴더를 생성할 수 없습니다:\n{e}")
    def delete_remote_items(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "삭제할 항목을 선택하세요."); return
        if not messagebox.askyesno("삭제 확인 (원격)", f"{len(selection_indices)}개의 원격 항목을 정말 삭제하시겠습니까?"): return
        for index in reversed(selection_indices):
            item_full = self.remote_listbox.get(index)
            item_name = self._parse_item_name(item_full)
            item_path = os.path.join(self.remote_path_var.get(), item_name).replace("\\", "/")
            try:
                if item_full.strip().startswith('[D]'): self._delete_remote_directory_recursive(item_path)
                else: self.sftp_client.remove(item_path)
            except Exception as e: messagebox.showerror("삭제 실패", f"{item_name} 삭제 중 오류 발생:\n{e}"); break
        self.update_remote_listbox()
    def _delete_remote_directory_recursive(self, path):
        for item in self.sftp_client.listdir_attr(path):
            item_path = f"{path}/{item.filename}"
            if stat.S_ISDIR(item.st_mode): self._delete_remote_directory_recursive(item_path)
            else: self.sftp_client.remove(item_path)
        self.sftp_client.rmdir(path)
    def start_transfer_thread(self, target_func): thread = Thread(target=target_func, daemon=True); thread.start()
    def upload_items(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.local_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "업로드할 항목을 선택하세요."); return
        remote_base_path = self.remote_path_var.get()
        local_base_path = self.local_path_var.get()
        for index in selection_indices:
            item_full = self.local_listbox.get(index)
            item_name = self._parse_item_name(item_full)
            local_path = os.path.join(local_base_path, item_name)
            remote_path = os.path.join(remote_base_path, item_name).replace("\\", "/")
            try:
                if item_full.strip().startswith('[D]'):
                    self.update_status(f"폴더 업로드 시작: {item_name}", "blue")
                    self.sftp_client.mkdir(remote_path)
                    self._upload_dir_recursive(local_path, remote_path)
                else:
                    self.update_status(f"업로드 중: {item_name}", "blue")
                    self.sftp_client.put(local_path, remote_path)
            except Exception as e: messagebox.showerror("업로드 실패", f"{item_name} 업로드 중 오류:\n{e}"); self.update_status("업로드 실패", "red"); return
        self.update_status("업로드 완료", "green"); self.update_remote_listbox()
    def _upload_dir_recursive(self, local_parent_path, remote_parent_path):
        for item_name in os.listdir(local_parent_path):
            local_path = os.path.join(local_parent_path, item_name)
            remote_path = os.path.join(remote_parent_path, item_name).replace("\\", "/")
            if os.path.isdir(local_path):
                self.sftp_client.mkdir(remote_path)
                self._upload_dir_recursive(local_path, remote_path)
            else: self.update_status(f"업로드 중: {local_path}", "blue"); self.sftp_client.put(local_path, remote_path)
    def download_items(self):
        if not self.sftp_client: messagebox.showerror("오류", "서버에 먼저 연결하세요."); return
        selection_indices = self.remote_listbox.curselection()
        if not selection_indices: messagebox.showinfo("정보", "다운로드할 항목을 선택하세요."); return
        remote_base_path = self.remote_path_var.get()
        local_base_path = self.local_path_var.get()
        for index in selection_indices:
            item_full = self.remote_listbox.get(index)
            item_name = self._parse_item_name(item_full)
            remote_path = os.path.join(remote_base_path, item_name).replace("\\", "/")
            local_path = os.path.join(local_base_path, item_name)
            try:
                if item_full.strip().startswith('[D]'):
                    self.update_status(f"폴더 다운로드 시작: {item_name}", "blue")
                    self._download_dir_recursive(remote_path, local_path)
                else:
                    self.update_status(f"다운로드 중: {item_name}", "blue")
                    self.sftp_client.get(remote_path, local_path)
            except Exception as e: messagebox.showerror("다운로드 실패", f"{item_name} 다운로드 중 오류:\n{e}"); self.update_status("다운로드 실패", "red"); return
        self.update_status("다운로드 완료", "green"); self.update_local_listbox()
    def _download_dir_recursive(self, remote_parent_path, local_parent_path):
        os.makedirs(local_parent_path, exist_ok=True)
        for item_attr in self.sftp_client.listdir_attr(remote_parent_path):
            remote_path = os.path.join(remote_parent_path, item_attr.filename).replace("\\", "/")
            local_path = os.path.join(local_parent_path, item_attr.filename)
            if stat.S_ISDIR(item_attr.st_mode): self._download_dir_recursive(remote_path, local_path)
            else: self.update_status(f"다운로드 중: {remote_path}", "blue"); self.sftp_client.get(remote_path, local_path)
    def update_status(self, message, color="black"):
        self.status_var.set(f"상태: {message}")
        self.status_label.config(foreground=color)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = ThemedTk(theme="ubuntu")
    app = SshFileExplorer(root)
    root.mainloop()
