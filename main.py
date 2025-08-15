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
import tempfile

# --- 설정 파일 경로 정의 ---
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.SshFileExplorer', 'config')

class ProfileEditDialog(tk.Toplevel):
    """프로필을 새로 추가하는 대화상자 클래스"""
    def __init__(self, parent_window, server_frame_ref, initial_data=None):
        super().__init__(parent_window)
        self.transient(parent_window); self.grab_set(); self.server_frame = server_frame_ref
        self.title("새 프로필 추가" if not initial_data else "프로필 편집")
        self.geometry("350x230")
        self.ip_var = tk.StringVar(); self.port_var = tk.StringVar(value='22'); self.user_var = tk.StringVar()
        self.pwd_var = tk.StringVar(); self.root_dir_var = tk.StringVar(value='/home')
        frame = ttk.Frame(self, padding=15); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="서버 IP:").grid(row=0, column=0, sticky="w", pady=4); ttk.Entry(frame, textvariable=self.ip_var, width=30).grid(row=0, column=1, sticky="ew")
        ttk.Label(frame, text="포트:").grid(row=1, column=0, sticky="w", pady=4); ttk.Entry(frame, textvariable=self.port_var, width=30).grid(row=1, column=1, sticky="ew")
        ttk.Label(frame, text="사용자 이름:").grid(row=2, column=0, sticky="w", pady=4); ttk.Entry(frame, textvariable=self.user_var, width=30).grid(row=2, column=1, sticky="ew")
        ttk.Label(frame, text="비밀번호:").grid(row=3, column=0, sticky="w", pady=4); ttk.Entry(frame, textvariable=self.pwd_var, show="*", width=30).grid(row=3, column=1, sticky="ew")
        ttk.Label(frame, text="시작 디렉토리:").grid(row=4, column=0, sticky="w", pady=4); ttk.Entry(frame, textvariable=self.root_dir_var, width=30).grid(row=4, column=1, sticky="ew")
        btn_frame = ttk.Frame(self, padding=(0, 10, 0, 0)); btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="저장", command=self.save).pack(side="right", padx=15); ttk.Button(btn_frame, text="취소", command=self.destroy).pack(side="right")
        if initial_data:
            self.ip_var.set(initial_data.get('ip', '')); self.port_var.set(initial_data.get('port', '22'))
            self.user_var.set(initial_data.get('user', '')); self.pwd_var.set(initial_data.get('pwd', ''))
            self.root_dir_var.set(initial_data.get('root_dir', '/home'))

    def save(self):
        ip = self.ip_var.get().strip(); user = self.user_var.get().strip(); port = self.port_var.get().strip()
        if not (ip and user and port): messagebox.showerror("입력 오류", "IP, 포트, 사용자 이름은 필수입니다.", parent=self); return
        config_data = {'ip': ip, 'port': port, 'user': user, 'pwd': self.pwd_var.get(), 'root_dir': self.root_dir_var.get()}
        filename = f"{user}@{ip}_{port}.json"; filepath = os.path.join(CONFIG_DIR, filename)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
            self.server_frame.load_profiles_to_listbox(); self.destroy()
        except Exception as e: messagebox.showerror("저장 실패", f"프로필 저장 중 오류 발생:\n{e}", parent=self)

class ServerFrame(ttk.Frame):
    def __init__(self, parent, title, main_app):
        super().__init__(parent)
        self.main_app = main_app; self.title = title
        self.ssh_client = None; self.sftp_client = None; self.profile_map = {}
        self.ip_var = tk.StringVar(); self.port_var = tk.StringVar(value='22'); self.user_var = tk.StringVar()
        self.pwd_var = tk.StringVar(); self.root_dir_var = tk.StringVar(value='/home'); self.path_var = tk.StringVar(value='/')
        self.create_widgets()
        # --- [버그 수정] 생성 시 프로필을 즉시 불러옵니다. ---
        self.load_profiles_to_listbox()

    def create_widgets(self):
        frame = ttk.LabelFrame(self, text=self.title, padding=10); frame.pack(fill="both", expand=True)
        conn_frame = ttk.Frame(frame, padding=(0,0,0,10)); conn_frame.pack(fill="x", expand=True)
        conn_frame.columnconfigure(0, weight=1); conn_frame.columnconfigure(1, weight=1)
        input_panel = ttk.Frame(conn_frame); input_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        input_panel.columnconfigure(1, weight=1)
        ttk.Label(input_panel, text="Server IP:").grid(row=0, column=0, sticky="w", pady=1); ttk.Entry(input_panel, textvariable=self.ip_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Port:").grid(row=1, column=0, sticky="w", pady=1); ttk.Entry(input_panel, textvariable=self.port_var).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Username:").grid(row=2, column=0, sticky="w", pady=1); ttk.Entry(input_panel, textvariable=self.user_var).grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Label(input_panel, text="Password:").grid(row=3, column=0, sticky="w", pady=1); ttk.Entry(input_panel, textvariable=self.pwd_var, show="*").grid(row=3, column=1, sticky="ew", padx=5)
        self.connect_btn = ttk.Button(input_panel, text="연결", command=self.toggle_connection); self.connect_btn.grid(row=4, column=0, columnspan=2, pady=(5,0), sticky="ew")
        profile_panel = ttk.Frame(conn_frame); profile_panel.grid(row=0, column=1, sticky="nsew", padx=(10,0))
        profile_list_frame = ttk.Frame(profile_panel); profile_list_frame.pack(fill="both", expand=True, pady=(0,5))
        profile_scrollbar = ttk.Scrollbar(profile_list_frame)
        self.profile_listbox = tk.Listbox(profile_list_frame, yscrollcommand=profile_scrollbar.set, exportselection=False, height=4)
        profile_scrollbar.config(command=self.profile_listbox.yview); profile_scrollbar.pack(side="right", fill="y")
        self.profile_listbox.pack(side="left", fill="both", expand=True); self.profile_listbox.bind("<<ListboxSelect>>", self.on_profile_selected)
        profile_btn_frame = ttk.Frame(profile_panel); profile_btn_frame.pack(fill="x")
        ttk.Button(profile_btn_frame, text="+", width=3, command=self._add_new_profile).pack(side="left", expand=True, fill="x")
        ttk.Button(profile_btn_frame, text="-", width=3, command=self._delete_selected_profile).pack(side="left", expand=True, fill="x")
        path_frame = ttk.Frame(frame); path_frame.pack(fill="x", pady=(0, 5))
        path_frame.columnconfigure(0, weight=1)
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var); path_entry.grid(row=0, column=0, sticky="ew"); path_entry.bind("<Return>", self.on_path_enter)
        ttk.Button(path_frame, text="..", width=4, command=self.go_up_dir).grid(row=0, column=1, sticky="e", padx=(5,0))
        list_frame = ttk.Frame(frame); list_frame.pack(fill="both", expand=True)
        list_scrollbar = ttk.Scrollbar(list_frame)
        self.listbox = tk.Listbox(list_frame, yscrollcommand=list_scrollbar.set, selectmode="extended", font=self.main_app.listbox_font, height=25)
        list_scrollbar.config(command=self.listbox.yview); self.listbox.pack(side="left", fill="both", expand=True); list_scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<Double-1>", self.on_double_click)
        action_frame = ttk.Frame(frame); action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(action_frame, text="삭제", command=self.delete_remote_items).pack(fill="x")

    def load_profiles_to_listbox(self):
        self.profile_listbox.delete(0, tk.END); self.profile_map.clear(); os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            for filename in sorted(os.listdir(CONFIG_DIR)):
                if filename.endswith('.json'):
                    filepath = os.path.join(CONFIG_DIR, filename)
                    with open(filepath, 'r', encoding='utf-8') as f: config = json.load(f)
                    display_text = f"{config.get('user')}@{config.get('ip')}:{config.get('port')}"
                    self.profile_listbox.insert(tk.END, display_text); self.profile_map[display_text] = filename
        except Exception as e: messagebox.showwarning("오류", f"프로필 목록 로드 실패:\n{e}", parent=self)
            
    def on_profile_selected(self, event=None):
        indices = self.profile_listbox.curselection();
        if not indices: return
        display_text = self.profile_listbox.get(indices[0]); filename = self.profile_map.get(display_text)
        if filename:
            filepath = os.path.join(CONFIG_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f: config = json.load(f)
                self.load_connection_profile(config)
            except Exception as e: messagebox.showerror("오류", f"프로필 로드 실패:\n{e}", parent=self)

    def load_connection_profile(self, config):
        self.ip_var.set(config.get('ip', '')); self.port_var.set(config.get('port', '22'))
        self.user_var.set(config.get('user', '')); self.pwd_var.set(config.get('pwd', ''))
        self.root_dir_var.set(config.get('root_dir', '/home'))
        
    def _add_new_profile(self): ProfileEditDialog(self, self)
    def _delete_selected_profile(self):
        indices = self.profile_listbox.curselection();
        if not indices: messagebox.showinfo("정보", "삭제할 프로필을 선택하세요.", parent=self); return
        display_text = self.profile_listbox.get(indices[0])
        if not messagebox.askyesno("삭제 확인", f"'{display_text}' 프로필을 삭제하시겠습니까?", parent=self): return
        filename = self.profile_map.get(display_text)
        if filename:
            filepath = os.path.join(CONFIG_DIR, filename)
            try: os.remove(filepath); self.load_profiles_to_listbox()
            except Exception as e: messagebox.showerror("삭제 실패", f"프로필 삭제 실패:\n{e}", parent=self)

    def _prompt_and_save_profile(self):
        ip=self.ip_var.get().strip(); user=self.user_var.get().strip(); port=self.port_var.get().strip()
        if not(ip and user and port): return
        filename = f"{user}@{ip}_{port}.json"; filepath = os.path.join(CONFIG_DIR, filename)
        if not os.path.exists(filepath):
            if messagebox.askyesno("프로필 저장", f"{self.title}: 이 연결 정보를 프로필에 저장하시겠습니까?", parent=self):
                config_data = {'ip':ip, 'port':port, 'user':user, 'pwd':self.pwd_var.get(), 'root_dir':self.root_dir_var.get()}
                try:
                    with open(filepath, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
                    self.load_profiles_to_listbox()
                except Exception as e: messagebox.showerror("저장 실패", f"프로필 저장 실패:\n{e}", parent=self)

    def connect_ssh(self):
        self.main_app.update_status(f"{self.title}: 연결 중...", "blue")
        try:
            self.ssh_client = paramiko.SSHClient(); self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=self.ip_var.get(), port=int(self.port_var.get()), username=self.user_var.get(), password=self.pwd_var.get(), timeout=5)
            self.sftp_client = self.ssh_client.open_sftp(); self.connect_btn.config(text="연결 끊기")
            self.path_var.set(self.root_dir_var.get()); self.update_listbox()
            self.main_app.update_status(f"{self.title}: {self.ip_var.get()}에 연결됨", "green")
        except Exception as e: self.disconnect_ssh(); messagebox.showerror("연결 실패", f"{self.title} 연결 실패:\n{e}", parent=self)
            
    def disconnect_ssh(self):
        if self.sftp_client: self.sftp_client.close()
        if self.ssh_client: self.ssh_client.close()
        self.ssh_client, self.sftp_client = None, None
        self.connect_btn.config(text="연결"); self.listbox.delete(0, tk.END); self.path_var.set("/")
        self.main_app.update_status(f"{self.title}: 연결 끊김", "red")

    def toggle_connection(self):
        if self.ssh_client:
            self.disconnect_ssh()
        else:
            self._prompt_and_save_profile()
            self.connect_ssh()

    def update_listbox(self, path=None):
        if not self.sftp_client: return
        current_path = path if path is not None else self.path_var.get()
        original_path = self.path_var.get(); self.path_var.set(current_path); self.listbox.delete(0, tk.END)
        try:
            dir_list, file_list = [], []
            for attr in self.sftp_client.listdir_attr(current_path):
                mtime = datetime.fromtimestamp(attr.st_mtime).strftime('%Y-%m-%d %H:%M')
                display_name = f" [D] {attr.filename}" if stat.S_ISDIR(attr.st_mode) else f" [F] {attr.filename}"
                formatted_item = f"{display_name:<50}{mtime}"
                if stat.S_ISDIR(attr.st_mode): dir_list.append(formatted_item)
                else: file_list.append(formatted_item)
            for item in sorted(dir_list) + sorted(file_list): self.listbox.insert(tk.END, item)
        except Exception as e: self.path_var.set(original_path); messagebox.showwarning("오류", f"{self.title} 디렉토리 접근 오류:\n{e}", parent=self)
    
    def on_path_enter(self, event): self.update_listbox(self.path_var.get().replace("\\", "/"))
    def on_double_click(self, event):
        indices = self.listbox.curselection();
        if not indices: return
        selected_item = self.listbox.get(indices[0])
        if selected_item.strip().startswith('[D]'):
            dir_name = self.main_app._parse_item_name(selected_item)
            if dir_name:
                new_path = os.path.join(self.path_var.get(), dir_name).replace("\\", "/")
                self.update_listbox(new_path)
    def go_up_dir(self):
        if self.path_var.get() != '/': self.update_listbox(os.path.dirname(self.path_var.get()).replace("\\", "/"))

    def delete_remote_items(self):
        if not self.sftp_client: messagebox.showerror("오류", f"{self.title}에 연결되지 않았습니다.", parent=self); return
        indices = self.listbox.curselection();
        if not indices: messagebox.showinfo("정보", "삭제할 항목을 선택하세요.", parent=self); return
        if not messagebox.askyesno("삭제 확인", f"{self.title}에서 선택한 {len(indices)}개 항목을 정말 삭제하시겠습니까?\n(폴더는 내용과 함께 삭제됩니다)", parent=self): return
        
        for index in reversed(sorted(indices)):
            item_full = self.listbox.get(index); item_name = self.main_app._parse_item_name(item_full)
            if not item_name: continue
            item_path = os.path.join(self.path_var.get(), item_name).replace("\\", "/")
            try:
                if item_full.strip().startswith('[D]'): self._delete_remote_directory_recursive(item_path)
                else: self.sftp_client.remove(item_path)
            except Exception as e: messagebox.showerror("삭제 실패", f"{item_name} 삭제 실패:\n{e}", parent=self); break
        self.update_listbox()

    def _delete_remote_directory_recursive(self, path):
        for item in self.sftp_client.listdir_attr(path):
            item_path = f"{path}/{item.filename}"
            if stat.S_ISDIR(item.st_mode): self._delete_remote_directory_recursive(item_path)
            else: self.sftp_client.remove(item_path)
        self.sftp_client.rmdir(path)

class SshFileExplorer:
    def __init__(self, root):
        self.root = root; self.root.title("SSH File Explorer"); self.root.resizable(True, True)
        self.default_font = tkfont.Font(family="Malgun Gothic", size=10); self.listbox_font = tkfont.Font(family="Consolas", size=10)
        self.root.option_add("*Font", self.default_font)
        self.status_var = tk.StringVar(value="상태: 대기 중")
        self.create_widgets(); self.update_local_listbox(); self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        style = ttk.Style(); style.configure(".", font=self.default_font); style.configure("TButton", padding=5)
        main_panels_frame = ttk.Frame(self.root); main_panels_frame.pack(fill="both", expand=True, padx=10, pady=5)
        main_panels_frame.columnconfigure(0, weight=1); main_panels_frame.columnconfigure(1, weight=1); main_panels_frame.columnconfigure(2, weight=1)
        
        local_panel = ttk.LabelFrame(main_panels_frame, text="local", padding=10)
        local_panel.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        self.local_path_var = tk.StringVar(value=os.path.expanduser('~'))
        local_path_frame = ttk.Frame(local_panel); local_path_frame.pack(fill="x", pady=(0, 5))
        local_path_frame.columnconfigure(0, weight=1)
        local_path_entry = ttk.Entry(local_path_frame, textvariable=self.local_path_var)
        local_path_entry.grid(row=0, column=0, sticky="ew"); local_path_entry.bind("<Return>", self.on_local_path_enter)
        ttk.Button(local_path_frame, text="..", width=4, command=self.go_up_local_dir).grid(row=0, column=1, sticky="e", padx=(5,0))
        local_list_frame = ttk.Frame(local_panel); local_list_frame.pack(fill="both", expand=True)
        local_scrollbar = ttk.Scrollbar(local_list_frame)
        self.local_listbox = tk.Listbox(local_list_frame, yscrollcommand=local_scrollbar.set, selectmode="extended", font=self.listbox_font, height=25)
        local_scrollbar.config(command=self.local_listbox.yview); self.local_listbox.pack(side="left", fill="both", expand=True); local_scrollbar.pack(side="right", fill="y")
        self.local_listbox.bind("<Double-1>", self.on_local_double_click)
        local_action_frame = ttk.Frame(local_panel); local_action_frame.pack(fill="x", pady=(5,0))
        ttk.Button(local_action_frame, text="삭제", command=self.delete_local_items).pack(fill="x")

        self.source_server_frame = ServerFrame(main_panels_frame, "Server", self)
        self.source_server_frame.grid(row=0, column=1, sticky="nsew", padx=(5,5))
        self.dest_server_frame = ServerFrame(main_panels_frame, "Destination", self)
        self.dest_server_frame.grid(row=0, column=2, sticky="nsew", padx=(5,0))

        transfer_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5)); transfer_frame.pack(fill="x", expand=False)
        ttk.Button(transfer_frame, text="local → server", command=lambda: self.start_transfer_thread(self.upload_to_source)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(transfer_frame, text="server → local", command=lambda: self.start_transfer_thread(self.download_from_source)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(transfer_frame, text="server → destination", command=lambda: self.start_transfer_thread(self.transfer_server_to_server)).pack(side="left", expand=True, fill="x", padx=2)
        
        status_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5)); status_frame.pack(side="bottom", fill="x", expand=False)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w"); self.status_label.pack(fill="x")

    def start_transfer_thread(self, target_func): thread = Thread(target=target_func, daemon=True); thread.start()
    def _parse_item_name(self, item_string):
        if not isinstance(item_string, str) or len(item_string) < 4: return None
        name_part = item_string[4:50].strip(); return name_part if name_part else None
    def on_closing(self):
        if self.source_server_frame.ssh_client: self.source_server_frame.disconnect_ssh()
        if self.dest_server_frame.ssh_client: self.dest_server_frame.disconnect_ssh()
        self.root.destroy()
    def on_local_path_enter(self, event): self.update_local_listbox(self.local_path_var.get())
    def on_local_double_click(self, event):
        indices = self.local_listbox.curselection();
        if not indices: return
        selected_item = self.local_listbox.get(indices[0])
        if selected_item.strip().startswith('[D]'):
            dir_name = self._parse_item_name(selected_item)
            if dir_name: self.update_local_listbox(os.path.join(self.local_path_var.get(), dir_name))
    def go_up_local_dir(self): self.update_local_listbox(os.path.dirname(self.local_path_var.get()))
    
    def delete_local_items(self):
        indices = self.local_listbox.curselection()
        if not indices: messagebox.showinfo("정보", "삭제할 항목을 선택하세요."); return
        if not messagebox.askyesno("삭제 확인", f"로컬 컴퓨터에서 선택한 {len(indices)}개 항목을 정말 삭제하시겠습니까?\n(폴더는 내용과 함께 삭제됩니다)"): return
        for index in reversed(sorted(indices)):
            item_full = self.local_listbox.get(index); item_name = self._parse_item_name(item_full)
            if not item_name: continue
            item_path = os.path.join(self.local_path_var.get(), item_name)
            try:
                if item_full.strip().startswith('[D]'): shutil.rmtree(item_path)
                else: os.remove(item_path)
            except Exception as e: messagebox.showerror("삭제 실패", f"{item_name} 삭제 실패:\n{e}"); break
        self.update_local_listbox()
    
    def update_local_listbox(self, path=None):
        current_path = path if path is not None else self.local_path_var.get()
        self.local_path_var.set(current_path); self.local_listbox.delete(0, tk.END)
        try:
            items = os.listdir(current_path); dir_list, file_list = [], []
            for item in items:
                try:
                    full_path = os.path.join(current_path, item)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M')
                    display_name = f" [D] {item}" if os.path.isdir(full_path) else f" [F] {item}"
                    formatted_item = f"{display_name:<50}{mtime}"
                    if os.path.isdir(full_path): dir_list.append(formatted_item)
                    else: file_list.append(formatted_item)
                except OSError: continue
            for item in sorted(dir_list) + sorted(file_list): self.local_listbox.insert(tk.END, item)
        except Exception as e: messagebox.showwarning("오류", f"로컬 디렉토리 접근 오류:\n{e}", parent=self.root)

    def upload_to_source(self):
        if not self.source_server_frame.sftp_client: messagebox.showerror("오류", "Source Server에 연결하세요."); return
        indices = self.local_listbox.curselection();
        if not indices: messagebox.showinfo("정보", "업로드할 항목을 선택하세요."); return
        remote_base = self.source_server_frame.path_var.get(); local_base = self.local_path_var.get(); sftp = self.source_server_frame.sftp_client
        for index in indices:
            item_full = self.local_listbox.get(index); item_name = self._parse_item_name(item_full)
            if not item_name: continue
            local_path = os.path.join(local_base, item_name); remote_path = os.path.join(remote_base, item_name).replace("\\", "/")
            try:
                if item_full.strip().startswith('[D]'): self._upload_dir_recursive(sftp, local_path, remote_path, "Source Server")
                else: self.update_status(f"업로드 중: {item_name} -> Source", "blue"); sftp.put(local_path, remote_path)
            except Exception as e: messagebox.showerror("업로드 실패", f"{item_name} 업로드 실패:\n{e}"); self.update_status("업로드 실패", "red"); return
        self.update_status("업로드 완료", "green"); self.source_server_frame.update_listbox()
    
    def _upload_dir_recursive(self, sftp, local_parent, remote_parent, server_name):
        self.update_status(f"폴더 생성: {remote_parent} on {server_name}", "blue")
        try: sftp.mkdir(remote_parent)
        except Exception: pass
        for item_name in os.listdir(local_parent):
            local_path = os.path.join(local_parent, item_name); remote_path = os.path.join(remote_parent, item_name).replace("\\", "/")
            if os.path.isdir(local_path): self._upload_dir_recursive(sftp, local_path, remote_path, server_name)
            else: self.update_status(f"업로드 중: {item_name} -> {server_name}", "blue"); sftp.put(local_path, remote_path)
            
    def download_from_source(self):
        if not self.source_server_frame.sftp_client: messagebox.showerror("오류", "Source Server에 연결하세요."); return
        indices = self.source_server_frame.listbox.curselection();
        if not indices: messagebox.showinfo("정보", "다운로드할 항목을 선택하세요."); return
        remote_base = self.source_server_frame.path_var.get(); local_base = self.local_path_var.get(); sftp = self.source_server_frame.sftp_client
        for index in indices:
            item_full = self.source_server_frame.listbox.get(index); item_name = self._parse_item_name(item_full)
            if not item_name: continue
            remote_path = os.path.join(remote_base, item_name).replace("\\", "/"); local_path = os.path.join(local_base, item_name)
            try:
                if item_full.strip().startswith('[D]'): self._download_dir_recursive(sftp, remote_path, local_path, "Source Server")
                else: self.update_status(f"다운로드 중: {item_name} from Source", "blue"); sftp.get(remote_path, local_path)
            except Exception as e: messagebox.showerror("다운로드 실패", f"{item_name} 다운로드 실패:\n{e}"); self.update_status("다운로드 실패", "red"); return
        self.update_status("다운로드 완료", "green"); self.update_local_listbox()

    def _download_dir_recursive(self, sftp, remote_parent, local_parent, server_name):
        self.update_status(f"폴더 생성: {local_parent}", "blue"); os.makedirs(local_parent, exist_ok=True)
        for attr in sftp.listdir_attr(remote_parent):
            remote_path = f"{remote_parent}/{attr.filename}".replace("\\", "/"); local_path = os.path.join(local_parent, attr.filename)
            if stat.S_ISDIR(attr.st_mode): self._download_dir_recursive(sftp, remote_path, local_path, server_name)
            else: self.update_status(f"다운로드 중: {attr.filename} from {server_name}", "blue"); sftp.get(remote_path, local_path)

    def transfer_server_to_server(self):
        source_frame = self.source_server_frame; dest_frame = self.dest_server_frame
        if not source_frame.sftp_client: messagebox.showerror("오류", "Source Server에 연결하세요."); return
        if not dest_frame.sftp_client: messagebox.showerror("오류", "Destination Server에 연결하세요."); return
        indices = source_frame.listbox.curselection()
        if not indices: messagebox.showinfo("정보", "전송할 항목을 Source Server에서 선택하세요."); return
        temp_dir = tempfile.mkdtemp(prefix="sftp-transfer-"); self.update_status("임시 디렉토리 생성: " + temp_dir, "blue")
        try:
            remote_base = source_frame.path_var.get(); sftp_source = source_frame.sftp_client
            for index in indices:
                item_full = source_frame.listbox.get(index); item_name = self._parse_item_name(item_full)
                if not item_name: continue
                remote_path = os.path.join(remote_base, item_name).replace("\\", "/"); local_path = os.path.join(temp_dir, item_name)
                if item_full.strip().startswith('[D]'): self._download_dir_recursive(sftp_source, remote_path, local_path, "Source")
                else: self.update_status(f"임시 다운로드: {item_name}", "blue"); sftp_source.get(remote_path, local_path)
            dest_base = dest_frame.path_var.get(); sftp_dest = dest_frame.sftp_client
            for item_name in os.listdir(temp_dir):
                local_path = os.path.join(temp_dir, item_name); remote_path = os.path.join(dest_base, item_name).replace("\\", "/")
                if os.path.isdir(local_path): self._upload_dir_recursive(sftp_dest, local_path, remote_path, "Destination")
                else: self.update_status(f"서버로 업로드: {item_name}", "blue"); sftp_dest.put(local_path, remote_path)
            self.update_status("서버 간 전송 완료", "green"); dest_frame.update_listbox()
        except Exception as e: messagebox.showerror("전송 실패", f"서버 간 전송 실패:\n{e}"); self.update_status("서버 간 전송 실패", "red")
        finally: shutil.rmtree(temp_dir); self.update_status("임시 디렉토리 삭제", "blue")

    def update_status(self, message, color="black"):
        self.status_var.set(f"상태: {message}"); self.status_label.config(foreground=color); self.root.update_idletasks()

if __name__ == "__main__":
    root = ThemedTk(theme="ubuntu")
    root.geometry("2000x800")
    app = SshFileExplorer(root)
    root.mainloop()
