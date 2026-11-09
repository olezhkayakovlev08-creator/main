import os
import sys
import ctypes
import subprocess
import urllib.request
import zipfile
import json
import tempfile
import shutil
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
import winreg

# ==========================================
# 1. ПРАВА АДМИНИСТРАТОРА
# ==========================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def is_running_in_ide():
    try:
        if any(k in os.environ for k in ['VSCODE_PID', 'PYCHARM_HOSTED', 'IDEA_INITIAL_DIRECTORY']):
            return True
        if hasattr(sys, 'ps1') or sys.flags.interactive:
            return True
        return False
    except:
        return False

def request_admin_if_needed():
    if is_admin():
        return True
    if is_running_in_ide():
        print("⚠️ Запущено из IDE без прав админа.")
        return False
    try:
        params = " ".join(['"' + arg + '"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)
    except Exception as e:
        print(f"⚠️ Не удалось запросить права админа: {e}")
        return False

admin_granted = request_admin_if_needed()

# ==========================================
# 2. ПУТИ (теперь динамические)
# ==========================================
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Файл для сохранения пути к Zapret
CONFIG_FILE = os.path.join(APP_DIR, "zapret_path.txt")
DEFAULT_ZAPRET_DIR = os.path.join(APP_DIR, "zapret_files")

# Глобальные переменные путей (обновляются при выборе папки)
ZAPRET_DIR = DEFAULT_ZAPRET_DIR
BIN_DIR = os.path.join(ZAPRET_DIR, "bin")
LISTS_DIR = os.path.join(ZAPRET_DIR, "lists")
UTILS_DIR = os.path.join(ZAPRET_DIR, "utils")

def update_paths(new_zapret_dir):
    """Обновляет все пути при смене папки Zapret"""
    global ZAPRET_DIR, BIN_DIR, LISTS_DIR, UTILS_DIR
    ZAPRET_DIR = new_zapret_dir
    BIN_DIR = os.path.join(ZAPRET_DIR, "bin")
    LISTS_DIR = os.path.join(ZAPRET_DIR, "lists")
    UTILS_DIR = os.path.join(ZAPRET_DIR, "utils")

def save_zapret_path(path):
    """Сохраняет путь к Zapret в конфиг-файл"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(path)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пути: {e}")
        return False

def load_zapret_path():
    """Загружает сохранённый путь к Zapret"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                path = f.read().strip()
                if path and validate_zapret_folder(path):
                    return path
    except:
        pass
    return None

def validate_zapret_folder(path):
    """Проверяет, что в папке есть все необходимые файлы Zapret"""
    if not path or not os.path.exists(path):
        return False
    
    # Обязательные файлы/папки
    required = [
        os.path.join(path, "bin", "winws.exe"),
        os.path.join(path, "bin", "WinDivert64.sys"),
        os.path.join(path, "lists"),
        os.path.join(path, "utils"),
    ]
    
    for item in required:
        if not os.path.exists(item):
            return False
    
    return True

# ==========================================
# 3. МАППИНГ СТРАТЕГИЙ
# ==========================================
strategy_mapping = {}

def get_real_strategy_name(name):
    if not name:
        return name
    return strategy_mapping.get(name, name)

# ==========================================
# 4. ТЕМЫ
# ==========================================
THEMES = {
    "dark": {
        "bg": "#1a1a1a", "panel": "#242424", "panel_hover": "#2d2d2d",
        "fg": "#e5e5e5", "muted": "#737373", "accent": "#3b82f6",
        "accent_hover": "#2563eb", "success": "#22c55e", "success_hover": "#16a34a",
        "danger": "#ef4444", "danger_hover": "#dc2626", "warning": "#f59e0b",
        "border": "#333333", "input": "#0f0f0f", "console_bg": "#0f0f0f",
        "console_fg": "#4ade80", "menu_bg": "#242424", "menu_fg": "#e5e5e5",
        "menu_active_bg": "#3b82f6", "menu_active_fg": "#ffffff",
        "theme_icon": "☀️", "theme_name": "Светлая"
    },
    "light": {
        "bg": "#fafafa", "panel": "#ffffff", "panel_hover": "#f0f0f0",
        "fg": "#171717", "muted": "#737373", "accent": "#2563eb",
        "accent_hover": "#1d4ed8", "success": "#16a34a", "success_hover": "#15803d",
        "danger": "#dc2626", "danger_hover": "#b91c1c", "warning": "#d97706",
        "border": "#e5e5e5", "input": "#ffffff", "console_bg": "#ffffff",
        "console_fg": "#0a6e0a", "menu_bg": "#ffffff", "menu_fg": "#171717",
        "menu_active_bg": "#2563eb", "menu_active_fg": "#ffffff",
        "theme_icon": "🌙", "theme_name": "Тёмная"
    }
}

current_theme = "dark"

def get_theme():
    return THEMES[current_theme]

# ==========================================
# 5. АВТОЗАПУСК
# ==========================================
AUTOSTART_KEY_NAME = "ZapretManager"
AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_app_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    else:
        python_exe = sys.executable
        if python_exe.lower().endswith('python.exe'):
            python_exe = python_exe[:-len('python.exe')] + 'pythonw.exe'
        script_path = os.path.abspath(__file__)
        return f'"{python_exe}" "{script_path}"'

def is_autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, AUTOSTART_KEY_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except:
        return False

def enable_autostart():
    try:
        cmd = get_app_command()
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, AUTOSTART_KEY_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        log(f"✅ Автозапуск включён", "green")
        return True
    except Exception as e:
        log(f"❌ Не удалось включить автозапуск: {e}", "red")
        return False

def disable_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, AUTOSTART_KEY_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        log(f"✅ Автозапуск выключен", "green")
        return True
    except Exception as e:
        log(f"❌ Не удалось выключить автозапуск: {e}", "red")
        return False

def toggle_autostart():
    if is_autostart_enabled():
        disable_autostart()
    else:
        enable_autostart()

# ==========================================
# 6. ДИАЛОГ ВЫБОРА ИСТОЧНИКА ZAPRET
# ==========================================
def show_zapret_setup_dialog():
    """
    Показывает диалог с выбором:
    - Скачать Zapret автоматически
    - Указать путь к уже установленному
    """
    dialog = tk.Toplevel()
    dialog.title("Настройка Zapret")
    dialog.geometry("500x350")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    
    theme = get_theme()
    dialog.configure(bg=theme["bg"])
    
    # Центрируем окно
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - 250
    y = (dialog.winfo_screenheight() // 2) - 175
    dialog.geometry(f"500x350+{x}+{y}")
    
    result = {"action": None, "path": None}
    
    # Заголовок
    tk.Label(dialog, text="🛡️ Настройка Zapret", 
             font=("Segoe UI", 16, "bold"), 
             bg=theme["bg"], fg=theme["fg"]).pack(pady=(20, 10))
    
    tk.Label(dialog, text="Как вы хотите установить Zapret?", 
             font=("Segoe UI", 11), 
             bg=theme["bg"], fg=theme["muted"]).pack(pady=(0, 25))
    
    # Кнопка "Скачать автоматически"
    btn_auto = tk.Button(
        dialog, 
        text="🌐  Скачать автоматически с GitHub",
        font=("Segoe UI", 11, "bold"),
        bg=theme["accent"], fg="#ffffff",
        activebackground=theme["accent_hover"],
        activeforeground="#ffffff",
        relief="flat", cursor="hand2",
        width=40, height=2,
        command=lambda: on_choice("download")
    )
    btn_auto.pack(pady=5)
    
    tk.Label(dialog, text="Будет скачана последняя версия (~10 МБ)", 
             font=("Segoe UI", 9), 
             bg=theme["bg"], fg=theme["muted"]).pack()
    
    tk.Label(dialog, text="", bg=theme["bg"]).pack(pady=5)
    
    # Кнопка "Указать путь"
    btn_manual = tk.Button(
        dialog,
        text="📂  Указать путь к установленному Zapret",
        font=("Segoe UI", 11, "bold"),
        bg=theme["panel"], fg=theme["fg"],
        activebackground=theme["panel_hover"],
        relief="flat", cursor="hand2",
        width=40, height=2,
        command=lambda: on_choice("manual")
    )
    btn_manual.pack(pady=5)
    
    tk.Label(dialog, text="Если Zapret уже скачан на компьютере", 
             font=("Segoe UI", 9), 
             bg=theme["bg"], fg=theme["muted"]).pack()
    
    def on_choice(choice):
        result["action"] = choice
        dialog.destroy()
    
    dialog.protocol("WM_DELETE_WINDOW", lambda: on_choice("download"))
    dialog.grab_set()
    dialog.wait_window()
    
    return result

def choose_zapret_folder():
    """Открывает диалог выбора папки с Zapret"""
    path = filedialog.askdirectory(
        title="Выберите папку с установленным Zapret",
        initialdir=APP_DIR
    )
    
    if not path:
        return None
    
    # Проверяем, что в папке есть все нужные файлы
    if not validate_zapret_folder(path):
        messagebox.showerror(
            "Неверная папка",
            f"В выбранной папке не найдены необходимые файлы Zapret:\n\n"
            f"• bin\\winws.exe\n"
            f"• bin\\WinDivert64.sys\n"
            f"• lists\\\n"
            f"• utils\\\n\n"
            f"Убедитесь, что вы выбрали корневую папку Zapret\n"
            f"(например, 'zapret-discord-youtube-1.10.4').",
            parent=app
        )
        return None
    
    return path

def change_zapret_folder():
    """Пункт меню для смены папки Zapret"""
    path = choose_zapret_folder()
    if path:
        update_paths(path)
        save_zapret_path(path)
        log(f"✅ Путь к Zapret изменён: {path}", "green")
        
        # Обновляем список стратегий
        strategies = get_strategies()
        sorted_strategies = sort_strategies_smart(strategies)
        formatted_strategies = [format_strategy_name(s) for s in sorted_strategies]
        global strategy_mapping
        strategy_mapping = {format_strategy_name(s): s for s in sorted_strategies}
        
        strategy_combo['values'] = formatted_strategies
        if formatted_strategies:
            strategy_combo.current(0)
            update_strategy_info()
        
        messagebox.showinfo(
            "Готово",
            f"✅ Путь к Zapret успешно изменён!\n\n"
            f"📂 {path}\n\n"
            f"Найдено стратегий: {len(formatted_strategies)}",
            parent=app
        )

# ==========================================
# 7. АВТОЗАГРУЗКА ZAPRET (ОБНОВЛЁННАЯ)
# ==========================================
def ensure_zapret_installed(log_func):
    """
    Убеждается, что Zapret установлен.
    Логика:
    1. Проверяем сохранённый путь в конфиге
    2. Если нет — проверяем стандартную папку zapret_files
    3. Если ничего нет — показываем диалог выбора
    """
    global ZAPRET_DIR
    
    # 1. Проверяем сохранённый путь
    saved_path = load_zapret_path()
    if saved_path:
        log_func(f"📂 Используется сохранённый путь: {saved_path}")
        update_paths(saved_path)
        if validate_zapret_folder(saved_path):
            log_func("✅ Zapret найден по сохранённому пути.")
            return True
        else:
            log_func("⚠️ Сохранённый путь невалиден. Ищем другие варианты...", "warning")
    
    # 2. Проверяем стандартную папку
    if os.path.exists(os.path.join(DEFAULT_ZAPRET_DIR, "bin", "winws.exe")):
        log_func(f"📂 Используется стандартная папка: {DEFAULT_ZAPRET_DIR}")
        update_paths(DEFAULT_ZAPRET_DIR)
        log_func("✅ Zapret найден.")
        return True
    
    # 3. Ничего не найдено — показываем диалог выбора
    log_func("⚠️ Zapret не найден. Требуется настройка...", "warning")
    
    dialog_result = show_zapret_setup_dialog()
    
    if dialog_result["action"] == "manual":
        path = choose_zapret_folder()
        if path:
            update_paths(path)
            save_zapret_path(path)
            log_func(f"✅ Zapret подключён: {path}")
            return True
        else:
            log_func("⚠️ Путь не выбран. Переход к автоматической загрузке...", "warning")
            return download_zapret(log_func)
    else:
        return download_zapret(log_func)


def download_zapret(log_func):
    """Скачивает Zapret с GitHub с улучшенной обработкой ошибок"""
    global ZAPRET_DIR
    
    log_func("⏳ Начинаем скачивание Zapret...", "info")
    
    # === ШАГ 1: Получаем URL последней версии ===
    log_func("🔍 Получение информации о последней версии...", "info")
    zip_url = None
    
    try:
        api_url = "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest"
        req = urllib.request.Request(api_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            log_func(f"✅ Найдена версия: {data.get('tag_name', 'неизвестно')}", "green")
        
        # Ищем zip-архив в ассетах релиза
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip"):
                zip_url = asset["browser_download_url"]
                log_func(f"📦 Найден архив: {name}", "info")
                break
        
        # Если не нашли в релизе — используем main.zip
        if not zip_url:
            log_func("⚠️ Zip-архив не найден в релизе. Используем main.zip...", "warning")
            zip_url = "https://github.com/Flowseal/zapret-discord-youtube/archive/refs/heads/main.zip"
            
    except urllib.error.URLError as e:
        log_func(f"❌ Ошибка сети: {e}", "red")
        log_func("💡 Проверьте подключение к интернету", "yellow")
        messagebox.showerror("Ошибка сети", 
            f"Не удалось подключиться к GitHub.\n\n"
            f"Ошибка: {e}\n\n"
            f"Проверьте:\n"
            f"• Подключение к интернету\n"
            f"• Не блокирует ли прокси/VPN доступ к GitHub\n"
            f"• Не заблокирован ли GitHub вашим провайдером")
        return False
    except json.JSONDecodeError as e:
        log_func(f"❌ Ошибка чтения ответа GitHub: {e}", "red")
        return False
    except Exception as e:
        log_func(f"❌ Неожиданная ошибка: {e}", "red")
        zip_url = "https://github.com/Flowseal/zapret-discord-youtube/archive/refs/heads/main.zip"
        log_func("💡 Пробуем альтернативный URL...", "yellow")
    
    # === ШАГ 2: Скачиваем архив ===
    temp_zip = os.path.join(tempfile.gettempdir(), "zapret_temp.zip")
    
    try:
        log_func(f"📥 Скачивание архива...", "info")
        log_func(f"   URL: {zip_url}", "info")
        
        req = urllib.request.Request(zip_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=120) as response:
            # Читаем данные с индикатором прогресса
            total_size = response.getheader('Content-Length')
            if total_size:
                total_size = int(total_size)
                log_func(f"   Размер: {total_size / 1024 / 1024:.1f} МБ", "info")
            
            downloaded = 0
            chunk_size = 64 * 1024  # 64 KB chunks
            data_chunks = []
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                data_chunks.append(chunk)
                downloaded += len(chunk)
                
                if total_size:
                    percent = (downloaded / total_size) * 100
                    # Обновляем лог каждые 10%
                    if int(percent) % 25 == 0 and downloaded % (chunk_size * 10) < chunk_size:
                        log_func(f"   ⏳ Загружено: {percent:.0f}%", "info")
            
            # Сохраняем в файл
            with open(temp_zip, 'wb') as out_file:
                for chunk in data_chunks:
                    out_file.write(chunk)
        
        # Проверяем размер скачанного файла
        file_size = os.path.getsize(temp_zip)
        if file_size < 1000:  # Меньше 1 КБ — явно что-то не так
            log_func(f"❌ Скачанный файл слишком мал ({file_size} байт)", "red")
            log_func("💡 Возможно, сервер вернул ошибку вместо архива", "yellow")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False
        
        log_func(f"✅ Архив скачан: {file_size / 1024 / 1024:.1f} МБ", "green")
        
    except urllib.error.URLError as e:
        log_func(f"❌ Ошибка скачивания: {e}", "red")
        messagebox.showerror("Ошибка скачивания", 
            f"Не удалось скачать архив.\n\nОшибка: {e}")
        return False
    except Exception as e:
        log_func(f"❌ Ошибка при скачивании: {e}", "red")
        import traceback
        traceback.print_exc()
        return False
    
    # === ШАГ 3: Распаковка ===
    log_func("📦 Распаковка файлов...", "info")
    
    try:
        # Удаляем старую папку, если есть
        if os.path.exists(DEFAULT_ZAPRET_DIR):
            try:
                shutil.rmtree(DEFAULT_ZAPRET_DIR)
                log_func("   🗑️ Старая папка удалена", "info")
            except PermissionError as e:
                log_func(f"⚠️ Не удалось удалить старую папку: {e}", "yellow")
                log_func("💡 Закройте другие программы, которые могут использовать эти файлы", "yellow")
                return False
        
        os.makedirs(DEFAULT_ZAPRET_DIR, exist_ok=True)
        
        # Распаковываем во временную папку
        extract_path = tempfile.mkdtemp(prefix="zapret_extract_")
        
        try:
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                # Проверяем структуру архива
                all_files = zip_ref.namelist()
                log_func(f"   📋 Файлов в архиве: {len(all_files)}", "info")
                
                # Ищем корневую папку в архиве
                root_folders = set()
                for name in all_files:
                    parts = name.split('/')
                    if len(parts) > 1 and parts[0]:
                        root_folders.add(parts[0])
                
                log_func(f"   📁 Корневые папки в архиве: {list(root_folders)[:3]}", "info")
                
                # Распаковываем
                zip_ref.extractall(extract_path)
                log_func("   ✅ Архив распакован во временную папку", "green")
                
        except zipfile.BadZipFile:
            log_func("❌ Скачанный файл не является валидным ZIP-архивом!", "red")
            log_func("💡 Возможно, скачивание было прервано", "yellow")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False
        except Exception as e:
            log_func(f"❌ Ошибка распаковки: {e}", "red")
            return False
        
        # Находим распакованную папку с Zapret
        extracted_folders = [f for f in os.listdir(extract_path) 
                            if os.path.isdir(os.path.join(extract_path, f))]
        
        source_folder = None
        
        # Сначала ищем папку с winws.exe напрямую
        for folder in extracted_folders:
            folder_path = os.path.join(extract_path, folder)
            if os.path.exists(os.path.join(folder_path, "bin", "winws.exe")):
                source_folder = folder_path
                log_func(f"   📂 Найдена папка Zapret: {folder}", "info")
                break
        
        # Если не нашли — возможно, файлы в корне
        if not source_folder:
            if os.path.exists(os.path.join(extract_path, "bin", "winws.exe")):
                source_folder = extract_path
                log_func("   📂 Файлы Zapret в корне архива", "info")
            else:
                # Ищем любую папку с bin\winws.exe рекурсивно
                for folder in extracted_folders:
                    folder_path = os.path.join(extract_path, folder)
                    for root, dirs, files in os.walk(folder_path):
                        if "winws.exe" in files and os.path.basename(root) == "bin":
                            source_folder = os.path.dirname(root)
                            log_func(f"   📂 Найдена папка Zapret: {os.path.basename(source_folder)}", "info")
                            break
                    if source_folder:
                        break
        
        if not source_folder:
            log_func("❌ Не удалось найти файлы Zapret в архиве!", "red")
            log_func("💡 Структура архива может отличаться от ожидаемой", "yellow")
            log_func(f"   Содержимое: {os.listdir(extract_path)}", "info")
            return False
        
        # Копируем файлы в целевую папку
        log_func("   📋 Копирование файлов...", "info")
        copied_count = 0
        
        for item in os.listdir(source_folder):
            s = os.path.join(source_folder, item)
            d = os.path.join(DEFAULT_ZAPRET_DIR, item)
            try:
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
                copied_count += 1
            except Exception as e:
                log_func(f"   ⚠️ Не удалось скопировать {item}: {e}", "yellow")
        
        log_func(f"   ✅ Скопировано элементов: {copied_count}", "green")
        
        # Очищаем временные файлы
        try:
            shutil.rmtree(extract_path, ignore_errors=True)
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except:
            pass
        
        # Проверяем, что всё на месте
        if not validate_zapret_folder(DEFAULT_ZAPRET_DIR):
            log_func("❌ После распаковки не найдены обязательные файлы!", "red")
            log_func("💡 Возможно, архив повреждён или имеет нестандартную структуру", "yellow")
            return False
        
        # Обновляем пути
        update_paths(DEFAULT_ZAPRET_DIR)
        save_zapret_path(DEFAULT_ZAPRET_DIR)
        
        log_func("✅ Zapret успешно установлен!", "green")
        log_func(f"📂 Путь: {DEFAULT_ZAPRET_DIR}", "info")
        return True
        
    except PermissionError as e:
        log_func(f"❌ Ошибка прав доступа: {e}", "red")
        log_func("💡 Закройте антивирус или добавьте папку в исключения", "yellow")
        return False
    except Exception as e:
        log_func(f"❌ Критическая ошибка распаковки: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# 8. ЛОГИКА УПРАВЛЕНИЯ
# ==========================================
def run_command(command, capture=True, timeout=30):
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        result = subprocess.run(command, shell=True, capture_output=capture, text=True, 
                               cwd=ZAPRET_DIR, creationflags=creation_flags, timeout=timeout)
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Таймаут"
    except Exception as e:
        return str(e)

def get_strategies():
    strategies = []
    if os.path.exists(ZAPRET_DIR):
        for f in os.listdir(ZAPRET_DIR):
            if f.endswith('.bat') and not f.startswith('service') and not f.startswith('uninstall'):
                strategies.append(f)
    return sorted(strategies)

def resolve_game_filter():
    gf_file = os.path.join(UTILS_DIR, "game_filter.enabled")
    tcp_range, udp_range = "1024-65535", "1024-65535"
    if os.path.exists(gf_file):
        try:
            with open(gf_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("tcp="): tcp_range = line.split("=", 1)[1].strip()
                    elif line.startswith("udp="): udp_range = line.split("=", 1)[1].strip()
        except: pass
    return tcp_range, udp_range

def get_winws_args(bat_file):
    try:
        with open(bat_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        args_lines = []
        in_args = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(('::', 'rem', 'echo', '@echo', 'set ', 'cd ', 'title ', 'call ', 'pause', 'if ')):
                continue
            
            if not in_args:
                if 'winws.exe' in line.lower() or stripped.startswith('--'):
                    in_args = True
                    if 'winws.exe' in line.lower():
                        match = re.search(r'winws\.exe["\s]*(.*)', line, flags=re.IGNORECASE)
                        if match:
                            rest = match.group(1).strip()
                            if rest.endswith('^'):
                                rest = rest[:-1].strip()
                            if rest:
                                args_lines.append(rest)
                    else:
                        if stripped.endswith('^'):
                            args_lines.append(stripped[:-1].strip())
                        else:
                            args_lines.append(stripped)
            else:
                if stripped.endswith('^'):
                    args_lines.append(stripped[:-1].strip())
                else:
                    args_lines.append(stripped)
                    break
                    
        if not args_lines:
            return ""
        
        args = " ".join(args_lines)
        tcp_range, udp_range = resolve_game_filter()
        
        bin_dir = BIN_DIR.replace('/', '\\')
        if not bin_dir.endswith('\\'):
            bin_dir += '\\'
            
        lists_dir = LISTS_DIR.replace('/', '\\')
        if not lists_dir.endswith('\\'):
            lists_dir += '\\'
        
        args = args.replace('"%BIN%"', f'"{bin_dir}"')
        args = args.replace('"%LISTS%"', f'"{lists_dir}"')
        args = args.replace('%BIN%', bin_dir)
        args = args.replace('%LISTS%', lists_dir)
        args = args.replace('""', '"')
        
        args = args.replace('%GameFilterTCP%', tcp_range)
        args = args.replace('%GameFilterUDP%', udp_range)
        
        args = re.sub(r'\s+', ' ', args).strip()
        return args
        
    except Exception as e:
        print(f"❌ Ошибка парсинга {bat_file}: {e}")
        return ""

def is_service_running():
    try:
        out = run_command('sc query zapret', timeout=5)
        return "RUNNING" in out
    except:
        return False

# ==========================================
# 9. ЛОГИРОВАНИЕ
# ==========================================
def log(msg, color=None):
    def _log():
        try:
            console.configure(state="normal")
            if color == "green":
                console.insert("end", msg + "\n", "success")
            elif color == "red":
                console.insert("end", msg + "\n", "error")
            elif color == "yellow":
                console.insert("end", msg + "\n", "warning")
            elif color == "cyan":
                console.insert("end", msg + "\n", "info")
            else:
                console.insert("end", msg + "\n")
            console.see("end")
            console.configure(state="disabled")
            app.update_idletasks()
        except:
            print(msg)
    
    if threading.current_thread() is threading.main_thread():
        _log()
    else:
        app.after(0, _log)

def toggle_console():
    if console_frame.winfo_ismapped():
        console_frame.pack_forget()
        btn_toggle_console.config(text="📋 Журнал")
    else:
        console_frame.pack(fill="x", padx=40, pady=(0, 20))
        btn_toggle_console.config(text="📋 Скрыть журнал")

# ==========================================
# 10. УСТАНОВКА / ОСТАНОВКА / УДАЛЕНИЕ
# ==========================================
is_operation_in_progress = False

def install_service():
    global is_operation_in_progress
    if not is_admin():
        messagebox.showwarning("Нет прав", "ПКМ по файлу → Запуск от имени администратора")
        return
    
    selected_display = strategy_var.get()
    selected = get_real_strategy_name(selected_display)
    
    if not selected:
        log("❌ Выберите стратегию!", "red")
        return
    
    is_operation_in_progress = True
    theme = get_theme()
    btn_main.config(text="⏳ Запускаем...", bg=theme["warning"], state="disabled", cursor="watch")
    status_indicator.config(text="● Запуск...", fg=theme["warning"])
    app.update_idletasks()
    
    log(f"⚙️ Установка: {selected}", "cyan")
    
    args = get_winws_args(os.path.join(ZAPRET_DIR, selected))
    if not args:
        log("❌ Не удалось извлечь аргументы из файла", "red")
        is_operation_in_progress = False
        update_install_button()
        return
    
    winws_path = os.path.join(BIN_DIR, "winws.exe")
    escaped_args = args.replace('"', '\\"')
    bin_path_value = f'\\"{winws_path}\\" {escaped_args}'
    
    log(f"📝 Длина аргументов: {len(args)} символов", "info")
    
    log("🔄 Остановка старой службы...", "cyan")
    run_command('net stop zapret >nul 2>&1')
    run_command('sc delete zapret >nul 2>&1')
    run_command('taskkill /IM winws.exe /F >nul 2>&1')
    time.sleep(1)
    
    log("🔧 Создание службы...", "cyan")
    cmd = f'sc create zapret binPath= "{bin_path_value}" DisplayName= "zapret" start= auto'
    result = run_command(cmd)
    
    if "ERROR" in result.upper() or "FAILED" in result.upper() or "1072" in result or "1073" in result:
        log(f"❌ Ошибка создания службы!", "red")
        log(f"💡 Ответ системы: {result.strip()}", "yellow")
        is_operation_in_progress = False
        update_install_button()
        return
    
    run_command('sc description zapret "Zapret DPI bypass"')
    log("▶ Запуск службы...", "cyan")
    
    start_result = run_command('sc start zapret')
    log(f"📋 Результат запуска: {start_result.strip()}", "info")
    
    reg_cmd = f'reg add "HKLM\\System\\CurrentControlSet\\Services\\zapret" /v zapret-discord-youtube /t REG_SZ /d "{selected}" /f >nul 2>&1'
    run_command(reg_cmd)
    
    time.sleep(2)
    log("✅ Готово! Проверка статуса...", "green")
    
    is_operation_in_progress = False
    update_install_button()
    check_status(detailed=True)

def stop_service():
    global is_operation_in_progress
    if not is_admin():
        messagebox.showwarning("Нет прав", "Требуются права администратора.")
        return
    
    is_operation_in_progress = True
    theme = get_theme()
    btn_main.config(text="⏳ Останавливаем...", bg=theme["warning"], state="disabled", cursor="watch")
    status_indicator.config(text="● Остановка...", fg=theme["warning"])
    app.update_idletasks()
    
    log("⏹ Остановка службы...", "cyan")
    run_command('net stop zapret >nul 2>&1')
    run_command('taskkill /IM winws.exe /F >nul 2>&1')
    time.sleep(1)
    log("✅ Служба остановлена.", "green")
    
    is_operation_in_progress = False
    update_install_button()
    check_status()

def remove_service():
    if not is_admin():
        messagebox.showwarning("Нет прав", "Требуются права администратора.")
        return
    
    log("🗑️ Удаление служб...", "cyan")
    run_command('taskkill /IM winws.exe /F >nul 2>&1')
    run_command('net stop zapret >nul 2>&1')
    run_command('sc delete zapret >nul 2>&1')
    run_command('net stop WinDivert >nul 2>&1')
    run_command('sc delete WinDivert >nul 2>&1')
    run_command('sc delete WinDivert14 >nul 2>&1')
    log("✅ Удалено.", "green")
    update_install_button()
    check_status()

def check_status(detailed=False):
    log("--- 🔍 Статус ---", "cyan")
    out = run_command('sc query zapret')
    if "RUNNING" in out:
        log("🟢 zapret: РАБОТАЕТ", "green")
    else:
        log("🔴 zapret: ОСТАНОВЛЕНА", "red")
        if "STOPPED" in out:
            log("   💡 Служба создана, но остановлена. Проверьте журнал Windows или антивирус.", "yellow")
    
    if "RUNNING" in run_command('sc query WinDivert'):
        log("🟢 WinDivert: РАБОТАЕТ", "green")
    else:
        log("🔴 WinDivert: ОСТАНОВЛЕН или не установлен", "red")
        log("   💡 Добавьте папку в исключения антивируса!", "yellow")
    
    if "winws.exe" in run_command('tasklist /FI "IMAGENAME eq winws.exe"'):
        log("🟢 winws.exe: ЗАПУЩЕН", "green")
    else:
        log("🔴 winws.exe: НЕ ЗАПУЩЕН", "red")
        if "RUNNING" in out:
            log("   ⚠️ Служба работает, но процесс упал.", "red")

    if detailed:
        log("\n📊 Детальная информация:", "info")
        log(f"   📂 Папка Zapret: {ZAPRET_DIR}", "info")
        
        sys_file = os.path.join(BIN_DIR, "WinDivert64.sys")
        if os.path.exists(sys_file):
            log(f"   ✅ WinDivert64.sys найден ({os.path.getsize(sys_file)} байт)", "green")
        else:
            log(f"   ❌ WinDivert64.sys отсутствует!", "red")
        
        if re.search(r'[\u0430-\u044f\u0410-\u042f\u0451\u0401]', ZAPRET_DIR):
            log(f"   ⚠️ Путь содержит кириллицу", "yellow")
        
        selected_display = strategy_var.get()
        selected = get_real_strategy_name(selected_display)
        if selected:
            args = get_winws_args(os.path.join(ZAPRET_DIR, selected))
            winws_path = os.path.join(BIN_DIR, "winws.exe")
            total_len = len(f'"{winws_path}" {args}')
            if total_len > 4000:
                log(f"   ⚠️ Команда очень длинная ({total_len} символов)!", "yellow")
            else:
                log(f"   ✅ Длина команды: {total_len} символов (норма)", "green")
    log("------------------------", "cyan")

# ==========================================
# 11. ДИНАМИЧЕСКАЯ КНОПКА
# ==========================================
def update_install_button():
    try:
        if is_operation_in_progress:
            return
        
        running = is_service_running()
        theme = get_theme()
        
        if running:
            btn_main.config(text="⏹  Остановить", bg=theme["danger"], activebackground=theme["danger_hover"], command=stop_service, state="normal", cursor="hand2")
            status_indicator.config(text="● Работает", fg=theme["success"])
        else:
            btn_main.config(text="▶  Запустить", bg=theme["success"], activebackground=theme["success_hover"], command=install_service, state="normal", cursor="hand2")
            status_indicator.config(text="● Остановлено", fg=theme["muted"])
    except:
        pass

def monitor_service_status():
    try:
        update_install_button()
    except:
        pass
    app.after(3000, monitor_service_status)

# ==========================================
# 12. ИНСТРУМЕНТЫ
# ==========================================
def update_ipset():
    log("🔄 Обновление IPSet...", "cyan")
    url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt"
    dest = os.path.join(LISTS_DIR, "ipset-all.txt")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response, open(dest, 'wb') as out_file:
            out_file.write(response.read())
        log("✅ IPSet обновлён.", "green")
    except Exception as e:
        log(f"❌ {e}", "red")

def update_hosts():
    log("🔄 Обновление Hosts...", "cyan")
    url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/hosts"
    temp_file = os.path.join(tempfile.gettempdir(), "zapret_hosts_new.txt")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
        with open(temp_file, 'wb') as out_file:
            out_file.write(data)
        hosts_file = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
        subprocess.Popen(['notepad.exe', temp_file])
        subprocess.Popen(['notepad.exe', hosts_file])
        log("📂 Скопируйте содержимое нового файла в конец системного hosts.", "cyan")
    except Exception as e:
        log(f"❌ {e}", "red")

def run_diagnostics():
    log("🩺 Диагностика...", "cyan")
    issues = []
    if not os.path.exists(os.path.join(BIN_DIR, "WinDivert64.sys")):
        issues.append("❌ Нет WinDivert64.sys")
    if re.search(r'[\u0430-\u044f\u0410-\u042f\u0451\u0401]', ZAPRET_DIR):
        issues.append("⚠️ Кириллица в пути")
    if "OneDrive" in ZAPRET_DIR:
        issues.append("⚠️ Папка в OneDrive")
    if not issues:
        log("✅ Проблем не найдено.", "green")
    else:
        for i in issues: log(i, "red")

def open_domain_editor():
    editor = tk.Toplevel(app)
    editor.title("Домены")
    editor.geometry("500x450")
    theme = get_theme()
    editor.configure(bg=theme["bg"])
    editor.attributes("-topmost", True)
    
    user_list_file = os.path.join(LISTS_DIR, "list-general-user.txt")
    if not os.path.exists(user_list_file):
        try:
            with open(user_list_file, 'w', encoding='utf-8') as f:
                f.write("# Домены для обхода\n# Пример: discord.com\n")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

    tk.Label(editor, text="Список доменов", font=("Segoe UI", 13, "bold"), bg=theme["bg"], fg=theme["fg"]).pack(pady=15)
    text_box = tk.Text(editor, width=55, height=15, font=("Consolas", 11), bg=theme["input"], fg=theme["fg"], insertbackground=theme["fg"], relief="flat", borderwidth=0, highlightbackground=theme["border"], highlightthickness=1)
    text_box.pack(pady=15, padx=20)
    
    try:
        with open(user_list_file, 'r', encoding='utf-8') as f:
            text_box.insert("1.0", f.read())
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))
        editor.destroy()
        return

    def save_domains():
        try:
            content = text_box.get("1.0", "end").strip()
            with open(user_list_file, 'w', encoding='utf-8') as f:
                f.write(content + "\n")
            log("✅ Домены сохранены.", "green")
            editor.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    btn_frame = tk.Frame(editor, bg=theme["bg"])
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Сохранить", command=save_domains, width=15, height=1, bg=theme["success"], fg="#ffffff", font=("Segoe UI", 10), relief="flat", cursor="hand2", activebackground=theme["success_hover"]).grid(row=0, column=0, padx=5)
    tk.Button(btn_frame, text="Отмена", command=editor.destroy, width=15, height=1, bg=theme["panel"], fg=theme["fg"], font=("Segoe UI", 10), relief="flat", cursor="hand2", activebackground=theme["panel_hover"]).grid(row=0, column=1, padx=5)

# ==========================================
# 13. СТРАТЕГИИ
# ==========================================
def get_strategy_info(strategy_name):
    name_lower = strategy_name.lower()
    if 'exp' in name_lower: return ("⚡ Экспериментальная", "#ff6b6b", "Новейшая стратегия.")
    elif 'fake tls' in name_lower: return ("🔥 FAKE TLS", "#ffa94d", "Подмена TLS-рукопожатия.")
    elif 'simple fake' in name_lower: return ("🔥 SIMPLE FAKE", "#ffa94d", "Упрощённая FAKE.")
    elif 'alt' in name_lower: return ("🔸 Альтернативная", "#74c0fc", "Альтернативные параметры.")
    elif 'general' in name_lower: return ("🔹 Базовая", "#69db7c", "Стандартная стратегия.")
    return ("📄 Другая", "#aaaaaa", "Специальная стратегия.")

def format_strategy_name(name):
    name_lower = name.lower()
    if 'exp' in name_lower: return f"⚡ {name}"
    elif 'fake tls' in name_lower: return f"🔥 {name}"
    elif 'simple fake' in name_lower: return f"🔥 {name}"
    elif 'alt' in name_lower: return f"🔸 {name}"
    elif 'general' in name_lower: return f"🔹 {name}"
    return f"📄 {name}"

def sort_strategies_smart(strategies):
    def get_priority(name):
        name_lower = name.lower()
        if 'exp' in name_lower: return (4, name)
        elif 'fake tls' in name_lower: return (3, name)
        elif 'simple fake' in name_lower: return (3, name)
        elif 'alt' in name_lower:
            match = re.search(r'alt\s*(\d+)', name_lower)
            if match: return (2, int(match.group(1)), name)
            return (2, 0, name)
        elif 'general' in name_lower: return (1, name)
        return (5, name)
    return sorted(strategies, key=get_priority)

def update_strategy_info(*args):
    selected_display = strategy_var.get()
    selected = get_real_strategy_name(selected_display)
    theme = get_theme()
    if not selected:
        strategy_type_label.config(text="Стратегия не выбрана", fg=theme["muted"])
        strategy_desc_label.config(text="")
        return
    strategy_type, color, description = get_strategy_info(selected)
    strategy_type_label.config(text=strategy_type, fg=color)
    strategy_desc_label.config(text=description, fg=theme["muted"])

def set_strategy_by_name(strategy_name):
    formatted = format_strategy_name(strategy_name)
    values = list(strategy_combo['values'])
    if formatted in values:
        strategy_combo.current(values.index(formatted))
    strategy_var.set(formatted)
    update_strategy_info()

# ==========================================
# 14. POPUP МЕНЮ (С НОВЫМ ПУНКТОМ)
# ==========================================
def show_settings_menu():
    theme = get_theme()
    menu = tk.Menu(app, tearoff=0, bg=theme["menu_bg"], fg=theme["menu_fg"], 
                   activebackground=theme["menu_active_bg"], activeforeground=theme["menu_active_fg"], 
                   borderwidth=1, relief="solid", font=("Segoe UI", 10))
    
    autostart_on = is_autostart_enabled()
    autostart_label = "🚫  Убрать из автозапуска" if autostart_on else "🚀  Добавить в автозапуск"
    
    menu.add_command(label="📂  Сменить путь к Zapret", command=change_zapret_folder)
    menu.add_command(label="📝  Списки доменов", command=open_domain_editor)
    menu.add_command(label=autostart_label, command=on_autostart_click)
    menu.add_command(label="🔄  Обновить IPSet", command=update_ipset)
    menu.add_command(label="🌐  Обновить Hosts", command=update_hosts)
    menu.add_command(label="🩺  Диагностика", command=run_diagnostics)
    menu.add_separator()
    menu.add_command(label="📊  Проверить статус", command=check_status)
    menu.add_command(label="🗑️  Удалить службу", command=remove_service)
    menu.add_separator()
    menu.add_command(label="📋  Журнал", command=toggle_console)
    
    app.update_idletasks()
    try:
        menu.post(btn_settings.winfo_rootx(), btn_settings.winfo_rooty() + btn_settings.winfo_height() + 2)
    except Exception as e:
        print(f"Ошибка меню: {e}")

def on_autostart_click():
    was_enabled = is_autostart_enabled()
    toggle_autostart()
    
    if was_enabled:
        messagebox.showinfo("Автозапуск", "✅ Приложение убрано из автозапуска.")
    else:
        messagebox.showinfo("Автозапуск", "✅ Приложение добавлено в автозапуск.")

# ==========================================
# 15. ПЕРЕКЛЮЧЕНИЕ ТЕМЫ
# ==========================================
def switch_theme():
    global current_theme
    current_theme = "light" if current_theme == "dark" else "dark"
    apply_theme()
    log(f"🎨 Тема: {get_theme()['theme_name']}", "info")

def apply_theme():
    theme = get_theme()
    app.configure(bg=theme["bg"])
    top_bar.configure(bg=theme["bg"])
    title_label.configure(bg=theme["bg"], fg=theme["fg"])
    
    btn_theme.config(bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"], activeforeground=theme["fg"], text=theme["theme_icon"])
    btn_settings.config(bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"], activeforeground=theme["fg"])
    
    center_wrapper.configure(bg=theme["bg"])
    center_frame.configure(bg=theme["bg"])
    main_title.configure(bg=theme["bg"], fg=theme["fg"])
    subtitle.configure(bg=theme["bg"], fg=theme["muted"])
    strategy_label.configure(bg=theme["bg"], fg=theme["muted"])
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Minimal.TCombobox', fieldbackground=theme["input"], background=theme["input"], foreground=theme["fg"], arrowcolor=theme["muted"], bordercolor=theme["border"], lightcolor=theme["border"], darkcolor=theme["border"], selectbackground=theme["accent"], selectforeground="#ffffff", padding=5)
    style.map('Minimal.TCombobox', fieldbackground=[('readonly', theme["input"])], foreground=[('readonly', theme["fg"])])
    strategy_combo.configure(style='Minimal.TCombobox')
    
    combo_container.configure(bg=theme["border"])
    combo_inner.configure(bg=theme["input"])
    strategy_info_frame.configure(bg=theme["panel"], highlightbackground=theme["border"])
    strategy_type_label.configure(bg=theme["panel"])
    strategy_desc_label.configure(bg=theme["panel"], fg=theme["muted"])
    status_indicator.configure(bg=theme["bg"])
    
    btn_toggle_console.configure(bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"])
    console_frame.configure(bg=theme["panel"])
    console.configure(bg=theme["console_bg"], fg=theme["console_fg"], insertbackground=theme["fg"])
    
    update_install_button()
    update_strategy_info()
    app.update_idletasks()

# ==========================================
# 16. ПОСТРОЕНИЕ UI
# ==========================================
try:
    app = tk.Tk()
    app.title("Zapret Manager")
    app.geometry("600x650")
    app.minsize(500, 600)
    theme = get_theme()
    app.configure(bg=theme["bg"])
except Exception as e:
    print(f"❌ Ошибка: {e}")
    input("Нажмите Enter...")
    sys.exit(1)

style = ttk.Style()
style.theme_use('clam')
style.configure('Minimal.TCombobox', fieldbackground=theme["input"], background=theme["input"], foreground=theme["fg"], arrowcolor=theme["muted"], bordercolor=theme["border"], lightcolor=theme["border"], darkcolor=theme["border"], selectbackground=theme["accent"], selectforeground="#ffffff", padding=5)
style.map('Minimal.TCombobox', fieldbackground=[('readonly', theme["input"])], foreground=[('readonly', theme["fg"])])

top_bar = tk.Frame(app, bg=theme["bg"])
top_bar.pack(fill="x", padx=30, pady=(20, 0))
title_label = tk.Label(top_bar, text="Zapret Manager", font=("Segoe UI", 14), bg=theme["bg"], fg=theme["fg"])
title_label.pack(side="left")

icon_btn_style = {"font": ("Segoe UI", 12), "relief": "flat", "cursor": "hand2", "width": 2, "height": 1, "bd": 0, "padx": 8, "pady": 4}
btn_settings = tk.Button(top_bar, text="⚙", command=show_settings_menu, bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"], **icon_btn_style)
btn_settings.pack(side="right", padx=(5, 0))
btn_theme = tk.Button(top_bar, text=theme["theme_icon"], command=switch_theme, bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"], **icon_btn_style)
btn_theme.pack(side="right")

center_wrapper = tk.Frame(app, bg=theme["bg"])
center_wrapper.pack(fill="both", expand=True)
center_frame = tk.Frame(center_wrapper, bg=theme["bg"])
center_frame.place(relx=0.5, rely=0.5, anchor="center")

main_title = tk.Label(center_frame, text="Обход DPI", font=("Segoe UI", 22, "bold"), bg=theme["bg"], fg=theme["fg"])
main_title.pack(pady=(0, 5))
subtitle = tk.Label(center_frame, text="Выберите стратегию и запустите", font=("Segoe UI", 10), bg=theme["bg"], fg=theme["muted"])
subtitle.pack(pady=(0, 30))

strategy_label = tk.Label(center_frame, text="Стратегия", font=("Segoe UI", 9), bg=theme["bg"], fg=theme["muted"], anchor="w")
strategy_label.pack(fill="x", pady=(0, 5))

combo_container = tk.Frame(center_frame, bg=theme["border"], padx=1, pady=1)
combo_container.pack(fill="x", pady=(0, 15))
combo_inner = tk.Frame(combo_container, bg=theme["input"])
combo_inner.pack(fill="x")

strategy_var = tk.StringVar()
strategy_combo = ttk.Combobox(combo_inner, textvariable=strategy_var, state="readonly", font=("Segoe UI", 11), style='Minimal.TCombobox', height=15)
strategy_combo.pack(fill="x", ipady=6, padx=1, pady=1)
strategy_var.trace_add("write", update_strategy_info)

strategy_info_frame = tk.Frame(center_frame, bg=theme["panel"], padx=15, pady=10, highlightbackground=theme["border"], highlightthickness=1)
strategy_info_frame.pack(fill="x", pady=(0, 25))
strategy_type_label = tk.Label(strategy_info_frame, text="Стратегия не выбрана", font=("Segoe UI", 10, "bold"), bg=theme["panel"], fg=theme["muted"], anchor="w")
strategy_type_label.pack(fill="x")
strategy_desc_label = tk.Label(strategy_info_frame, text="", font=("Segoe UI", 9), bg=theme["panel"], fg=theme["muted"], anchor="w", wraplength=400, justify="left")
strategy_desc_label.pack(fill="x", pady=(3, 0))

btn_main = tk.Button(center_frame, text="▶  Запустить", command=install_service, bg=theme["success"], fg="#ffffff", activebackground=theme["success_hover"], activeforeground="#ffffff", font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2", width=20, height=2, bd=0)
btn_main.pack(pady=(0, 10))

status_indicator = tk.Label(center_frame, text="● Остановлено", font=("Segoe UI", 9), bg=theme["bg"], fg=theme["muted"])
status_indicator.pack(pady=(0, 20))

btn_toggle_console = tk.Button(app, text="📋 Журнал", command=toggle_console, bg=theme["panel"], fg=theme["fg"], activebackground=theme["panel_hover"], font=("Segoe UI", 9), relief="flat", cursor="hand2", bd=0, padx=15, pady=5)
btn_toggle_console.pack(side="bottom", pady=(0, 10))

console_frame = tk.LabelFrame(app, text="", font=("Segoe UI", 10), bg=theme["panel"], fg=theme["fg"], relief="flat", bd=0, highlightbackground=theme["border"], highlightthickness=1)
console = scrolledtext.ScrolledText(console_frame, height=8, font=("Consolas", 9), bg=theme["console_bg"], fg=theme["console_fg"], insertbackground=theme["fg"], relief="flat", bd=0, padx=10, pady=10)
console.pack(fill="both", expand=True, padx=1, pady=1)
console.configure(state="disabled")

console.tag_config("success", foreground="#22c55e")
console.tag_config("error", foreground="#ef4444")
console.tag_config("warning", foreground="#f59e0b")
console.tag_config("info", foreground="#60a5fa")

# ==========================================
# 17. ИНИЦИАЛИЗАЦИЯ
# ==========================================
def on_startup():
    global strategy_mapping
    log("🔄 Запуск...", "info")
    if not is_admin():
        log("⚠️ Запущено без прав админа.", "yellow")
    
    if is_autostart_enabled():
        log("🚀 Автозапуск: ВКЛЮЧЁН", "green")
    else:
        log("🚫 Автозапуск: выключен", "info")
    
    if ensure_zapret_installed(log):
        log(f"📂 Путь к Zapret: {ZAPRET_DIR}", "info")
        
        strategies = get_strategies()
        sorted_strategies = sort_strategies_smart(strategies)
        formatted_strategies = [format_strategy_name(s) for s in sorted_strategies]
        strategy_mapping = {format_strategy_name(s): s for s in sorted_strategies}
        
        strategy_combo['values'] = formatted_strategies
        if formatted_strategies:
            strategy_combo.current(0)
            update_strategy_info()
            log(f"✅ Найдено стратегий: {len(formatted_strategies)}", "green")
        else:
            log("⚠️ Стратегии не найдены в папке Zapret.", "yellow")
        
        update_install_button()
        monitor_service_status()
        log("✅ Готово к работе", "green")

app.after(100, on_startup)
app.mainloop()