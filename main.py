#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巡检自动化助手 - 安卓 App 主程序
====================================
把 kimi.py（巡检自动化脚本）包装成带界面的安卓应用：
  1. 启动需要密码登录（默认密码: 12138，可在 buildozer.spec / 下方常量修改）
  2. 登录后自动申请存储权限（Android 11+ 引导授予"所有文件访问"）
  3. 输入用户名 / 用户代码，一键执行巡检自动化
  4. 实时滚动显示执行日志

业务逻辑与 kimi.py 保持 1:1（TimeUtil / IOUtil / InspectionAutomator），
仅把 input()/print() 替换为界面交互与日志回调。
"""

from __future__ import annotations

import json
import os
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ============================================================
# 配置区（按需修改）
# ============================================================
APP_PASSWORD = "12138"                       # 登录密码
DATA_DIR = "/storage/emulated/0/widgetone/apps/NormalPIM/data"   # 巡检数据目录

# 数据目录不存在时，让用户手动填写（默认同上）
IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or os.path.exists("/system/build.prop")

# ============================================================
# 中文字体注册（SimHei 子集，APK 内置）
# ============================================================
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "fonts", "cjk.ttf")
if os.path.exists(FONT_PATH):
    LabelBase.register(name="Cjk",
                       fn_regular=FONT_PATH,
                       fn_bold=FONT_PATH,
                       fn_italic=FONT_PATH,
                       fn_bolditalic=FONT_PATH)

try:  # Kivy >= 2.1 支持全局缺省字体
    from kivy.core.window import Window
    if os.path.exists(FONT_PATH):
        Window.set_title("巡检助手")
except Exception:
    pass


# ============================================================
# 业务核心（与 kimi.py 完全一致）
# ============================================================
class TimeUtil:
    """时间解析/格式化/随机偏移"""
    FMT = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def parse(dt_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(dt_str, TimeUtil.FMT)
        except ValueError:
            return None

    @staticmethod
    def format(dt: datetime) -> str:
        return dt.strftime(TimeUtil.FMT)

    @staticmethod
    def rand_sec(max_sec: int = 59) -> timedelta:
        return timedelta(seconds=random.randint(0, max_sec))


class IOUtil:
    """JSON 读/写，带目录自动创建；log 为日志回调"""
    @staticmethod
    def load(parent: Path, filename: str, log=print) -> Optional[List[Dict]]:
        path = parent / filename
        try:
            with path.open(encoding="utf-8") as f:
                data = json.loads(f.read().strip())
            log(f"✓ 成功加载 {filename}，共 {len(data)} 条记录")
            return data
        except FileNotFoundError:
            log(f"✗ 文件不存在: {filename}")
        except json.JSONDecodeError as e:
            log(f"✗ {filename} JSON 解析失败: {e}")
        except OSError as e:
            log(f"✗ 读取 {filename} 失败: {e}")
        return None

    @staticmethod
    def save(parent: Path, filename: str, data: List[Dict], log=print) -> bool:
        path = parent / filename
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            json_str = json.dumps(data, ensure_ascii=False, indent=None,
                                  separators=(",", ":"))
            path.write_text(json_str, encoding="utf-8")
            log(f"✓ 成功保存 {filename}")
            return True
        except (OSError, TypeError) as e:
            log(f"✗ 保存 {filename} 失败: {e}")
            return False


class InspectionAutomator:
    def __init__(self, data_dir: str | Path, log=print):
        self.data_dir = Path(data_dir)
        self.log = log
        self.checker_list: List[Dict] = []
        self.task_list: List[Dict] = []
        self.user_info: Dict[str, str] = {}

    # ---- 数据加载 ----
    def load_checker_list(self) -> bool:
        self.checker_list = IOUtil.load(self.data_dir, "CHECKERLIST.txt", self.log) or []
        return bool(self.checker_list)

    def load_task_list(self) -> bool:
        self.task_list = IOUtil.load(self.data_dir, "TASK.txt", self.log) or []
        return bool(self.task_list)

    # ---- ID 匹配 ----
    def find_user_id(self) -> bool:
        for chk in self.checker_list:
            if (chk.get("username") == self.user_info.get("username")
                    and chk.get("usercode") == self.user_info.get("usercode")):
                self.user_info["userid"] = chk["userid"]
                self.log(f"✓ 找到匹配的用户ID: {self.user_info['userid']}")
                return True
        self.log(f"✗ 未找到匹配用户: {self.user_info.get('username')}"
                 f" ({self.user_info.get('usercode')})")
        return False

    # ---- 任务项处理 ----
    def load_task_items(self, task_code: str) -> Tuple[Optional[List[Dict]],
                                                       Optional[List[str]],
                                                       Optional[Dict[str, List[Dict]]]]:
        items = IOUtil.load(self.data_dir, f"TASKITEMLIST{task_code}.txt", self.log)
        if not items:
            return None, None, None
        groups: Dict[str, List[Dict]] = {}
        for it in items:
            groups.setdefault(it.get("areacode"), []).append(it)
        sorted_areas = sorted(groups.keys(),
                              key=lambda x: int(x) if str(x).isdigit() else 999)
        return items, sorted_areas, groups

    # ---- 时间序列生成 ----
    def generate_time_sequence(self, start: datetime, area_count: int) -> List[datetime]:
        times = [start.replace(second=random.randint(0, 59))]
        cur = times[0]
        for _ in range(area_count - 1):
            cur += timedelta(minutes=random.randint(2, 4)) + TimeUtil.rand_sec()
            times.append(cur)
        return times

    # ---- 单任务主流程 ----
    def process_single_task(self, task: Dict) -> Optional[Dict]:
        code = task.get("taskcode")
        name = task.get("taskname", "未知任务")
        plan_start_str = task.get("planstartdate")
        plan_end_str = task.get("planenddate")
        self.log(f"处理任务: {name} ({code})")

        if not all([code, plan_start_str, plan_end_str]):
            self.log("✗ 任务关键字段缺失，跳过")
            return None

        plan_start = TimeUtil.parse(plan_start_str)
        plan_end = TimeUtil.parse(plan_end_str)
        if not plan_start or not plan_end:
            self.log("✗ 时间格式错误，跳过")
            return None

        items, sorted_areas, groups = self.load_task_items(code)
        if not items:
            return None
        if not sorted_areas:
            self.log("✗ 无有效区域数据，跳过")
            return None

        duration = plan_end - plan_start
        if duration >= timedelta(hours=4):
            start = (plan_start
                     + timedelta(hours=random.randint(1, 3),
                                 minutes=random.randint(1, 10))
                     + TimeUtil.rand_sec())
        else:
            start = plan_start + timedelta(minutes=random.randint(1, 5)) + TimeUtil.rand_sec()

        check_times = self.generate_time_sequence(start, len(sorted_areas))
        latest = check_times[-1]
        end = latest + timedelta(minutes=random.randint(1, 2)) + TimeUtil.rand_sec()
        if end > plan_end:
            end = plan_end - TimeUtil.rand_sec(30)

        for area, chk_time in zip(sorted_areas, check_times):
            for it in groups[area]:
                it.update({
                    "checkusrid": self.user_info["userid"],
                    "checkusrname": self.user_info["username"],
                    "checktime": TimeUtil.format(chk_time),
                    "checkresult": "ZC",
                    "fdesc": "正常",
                })

        if IOUtil.save(self.data_dir, f"TASKITEMLIST{code}.txt", items, self.log):
            new_task = task.copy()
            new_task.update({"startdate": TimeUtil.format(start),
                             "donedate": TimeUtil.format(end)})
            return new_task
        return None

    # ---- 总入口 ----
    def run(self, username: str, usercode: str) -> None:
        self.log("=== 开始执行巡检自动化 ===")
        self.user_info = {"username": username, "usercode": usercode}
        self.log(f"✓ 用户信息已设置: {username} ({usercode})")

        if not self.data_dir.exists():
            self.log(f"错误: 数据目录不存在: {self.data_dir}")
            return
        if not self.load_checker_list() or not self.load_task_list():
            return
        if not self.find_user_id():
            return

        updated_tasks: List[Dict] = []
        ok_cnt = 0
        for tsk in self.task_list:
            ret = self.process_single_task(tsk)
            if ret:
                updated_tasks.append(ret)
                ok_cnt += 1

        if updated_tasks and IOUtil.save(self.data_dir, "TASK.txt",
                                         updated_tasks, self.log):
            self.log("✓ 成功更新 TASK.txt")

        self.log("=== 巡检自动化完成 ===")
        self.log(f"总任务数: {len(self.task_list)} | 成功处理: {ok_cnt}")


# ============================================================
# 安卓权限部分（仅安卓平台生效）
# ============================================================
def request_storage_permissions(callback):
    """申请运行时权限；Android 11+ 额外引导"所有文件访问"。完成后回调 callback()。"""
    if not IS_ANDROID:
        callback()
        return

    from android.permissions import request_permissions, check_permission, Permission

    def after_runtime(*_):
        # Android 11+ (SDK 30) 需要 MANAGE_EXTERNAL_STORAGE
        try:
            from jnius import autoclass
            VERSION = autoclass("android.os.Build$VERSION")
            if VERSION.SDK_INT >= 30:
                env = autoclass("android.os.Environment")
                if not env.isExternalStorageManager():
                    _guide_all_files_access()
                    return  # 用户从设置页返回后手动点"重新执行"
        except Exception:
            pass
        callback()

    perms = [Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]
    request_permissions(perms, after_runtime)


def _guide_all_files_access():
    """引导用户到设置页开启『所有文件访问』"""
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    "package:" + PythonActivity.mActivity.getPackageName())
    PythonActivity.mActivity.startActivity(intent)


def has_all_files_access() -> bool:
    """检查是否已具备全部文件访问权（Android 11+ 判断 All Files Access）。"""
    if not IS_ANDROID:
        return True
    try:
        from android.permissions import check_permission, Permission
        if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
            return False
        from jnius import autoclass
        VERSION = autoclass("android.os.Build$VERSION")
        if VERSION.SDK_INT >= 30:
            env = autoclass("android.os.Environment")
            return bool(env.isExternalStorageManager())
        return True
    except Exception:
        return False


# ============================================================
# UI 组件
# ============================================================
class CjkLabel(Label):
    """使用内置中文字体的标签"""

    def __init__(self, **kw):
        kw.setdefault("font_name", "Cjk" if os.path.exists(FONT_PATH) else "Roboto")
        super().__init__(**kw)


class CjkInput(TextInput):
    """使用内置中文字体的输入框"""

    def __init__(self, **kw):
        kw.setdefault("font_name", "Cjk" if os.path.exists(FONT_PATH) else "Roboto")
        super().__init__(**kw)


class TopBar(BoxLayout):
    """顶部标题栏"""


class LoginScreen(BoxLayout):
    """登录页：密码校验"""

    def __init__(self, on_success, **kw):
        super().__init__(orientation="vertical", padding=dp(24),
                         spacing=dp(14), **kw)
        self.on_success = on_success

        self.add_widget(CjkLabel(text="巡 检 助 手", font_size=sp(30),
                                 bold=True, size_hint_y=0.28))
        self.add_widget(CjkLabel(text="Inspection Assistant",
                                 font_size=sp(14), opacity=0.55,
                                 size_hint_y=None, height=dp(22)))

        box = BoxLayout(orientation="vertical", spacing=dp(10),
                        size_hint_y=None, height=dp(160))
        self.pw_input = CjkInput(password=True, multiline=False,
                                 font_size=sp(20), halign="center",
                                 hint_text="请输入密码", write_tab=False)
        self.pw_input.bind(on_text_validate=self.try_login)
        box.add_widget(self.pw_input)

        self.msg = CjkLabel(text="", font_size=sp(14),
                            color=(0.95, 0.35, 0.35, 1),
                            size_hint_y=None, height=dp(24))
        box.add_widget(self.msg)

        btn = Button(text="登 录", font_size=sp(20),
                     size_hint_y=None, height=dp(52),
                     background_color=(0.05, 0.45, 0.85, 1))
        btn.bind(on_press=self.try_login)
        box.add_widget(btn)
        self.add_widget(box)
        self.add_widget(Widget())  # 底部占位

    def try_login(self, *_):
        if self.pw_input.text == APP_PASSWORD:
            self.on_success()
        else:
            self.msg.text = "密码错误，请重试"
            self.pw_input.text = ""


class MainScreen(BoxLayout):
    """主页面：权限检查 + 用户信息输入 + 执行 + 日志"""

    running = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(16),
                         spacing=dp(10), **kw)

        # ---- 标题栏 ----
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        top.add_widget(CjkLabel(text="巡检自动化", font_size=sp(22),
                                bold=True, size_hint_x=0.7))
        self.status_dot = CjkLabel(text="●", font_size=sp(18),
                                   color=(0.3, 0.8, 0.3, 1),
                                   size_hint_x=0.05)
        top.add_widget(self.status_dot)
        self.perm_label = CjkLabel(text="检查权限…", font_size=sp(13),
                                   size_hint_x=0.5, halign="left")
        top.add_widget(self.perm_label)
        self.add_widget(top)

        # ---- 数据目录 ----
        dir_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        dir_row.add_widget(CjkLabel(text="数据目录", font_size=sp(14),
                                    size_hint_x=0.24))
        self.dir_input = CjkInput(text=DATA_DIR, multiline=False,
                                  font_size=sp(13), write_tab=False,
                                  size_hint_x=0.76)
        dir_row.add_widget(self.dir_input)
        self.add_widget(dir_row)

        # ---- 用户信息 ----
        grid = GridLayout(cols=2, size_hint_y=None, height=dp(40),
                          spacing=dp(6))
        grid.add_widget(CjkLabel(text="用户名", font_size=sp(14)))
        self.u_input = CjkInput(multiline=False, font_size=sp(15),
                                hint_text="username", write_tab=False)
        grid.add_widget(self.u_input)
        grid.add_widget(CjkLabel(text="用户代码", font_size=sp(14)))
        self.c_input = CjkInput(multiline=False, font_size=sp(15),
                                hint_text="usercode", write_tab=False)
        grid.add_widget(self.c_input)
        self.add_widget(grid)

        # ---- 执行按钮 ----
        self.run_btn = Button(text="一键执行巡检", font_size=sp(19),
                              size_hint_y=None, height=dp(54),
                              background_color=(0.05, 0.55, 0.35, 1))
        self.run_btn.bind(on_press=self.on_run)
        self.add_widget(self.run_btn)

        # ---- 日志区 ----
        self.add_widget(CjkLabel(text="执行日志", font_size=sp(14),
                                 size_hint_y=None, height=dp(26),
                                 halign="left"))
        scroll = ScrollView()
        self.log_label = CjkLabel(text="等待执行…\n", font_size=sp(13),
                                  size_hint_y=None, halign="left",
                                  valign="top")
        self.log_label.bind(texture_size=lambda inst, val:
                            setattr(inst, "height", val[1]))
        self.log_label.bind(width=lambda inst, val:
                            setattr(inst, "text_size", (val, None)))
        scroll.add_widget(self.log_label)
        self.add_widget(scroll)

        self._lines: List[str] = []
        Clock.schedule_once(lambda *_: self.refresh_perm(), 0.5)

    # ---- 权限 ----
    def refresh_perm(self, *_):
        ok = has_all_files_access()
        self.perm_label.text = "权限已就绪" if ok else "缺少文件权限"
        self.status_dot.color = (0.3, 0.8, 0.3, 1) if ok else (0.9, 0.5, 0.1, 1)

    def ask_permissions(self, done_cb=None):
        def _done():
            Clock.schedule_once(lambda *_: self.refresh_perm(), 1.5)
            if done_cb:
                done_cb()
        request_storage_permissions(_done)

    # ---- 日志 ----
    def log(self, msg: str):
        self._lines.append(str(msg))
        if len(self._lines) > 500:
            self._lines = self._lines[-500:]
        Clock.schedule_once(lambda *_: self._update_label(), 0)

    def _update_label(self):
        self.log_label.text = "\n".join(self._lines[-200:])
        self.log_label.texture_update()

    # ---- 执行 ----
    def on_run(self, *_):
        if self.running:
            self.log("⚠ 正在执行中，请稍候…")
            return
        if not self.u_input.text.strip() or not self.c_input.text.strip():
            self._popup("提示", "请填写用户名和用户代码")
            return

        if not has_all_files_access():
            self._popup("需要权限",
                        "首次使用请授予存储权限（Android 11+ 请开启『所有文件访问』），"
                        "授权后点击『一键执行巡检』重新运行。")
            self.ask_permissions()
            return

        self.running = True
        self.run_btn.disabled = True
        self.run_btn.text = "正在执行…"
        self._lines = []
        self.log("===== 巡检助手 启动 =====")

        username = self.u_input.text.strip()
        usercode = self.c_input.text.strip()
        data_dir = self.dir_input.text.strip() or DATA_DIR

        def worker():
            try:
                auto = InspectionAutomator(data_dir, log=lambda m: self.log(m))
                auto.run(username, usercode)
            finally:
                Clock.schedule_once(lambda *_: self._finish(), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self):
        self.running = False
        self.run_btn.disabled = False
        self.run_btn.text = "一键执行巡检"
        if any("完成" in ln for ln in self._lines[-40:]):
            self._popup("完成", "巡检自动化执行完成，详见日志。")

    def _popup(self, title: str, msg: str):
        content = BoxLayout(orientation="vertical", padding=dp(14),
                            spacing=dp(10))
        content.add_widget(CjkLabel(text=msg, font_size=sp(15),
                                    size_hint_y=0.75))
        btn = Button(text="知道了", font_size=sp(16),
                     size_hint_y=None, height=dp(46))
        content.add_widget(btn)
        popup = Popup(title=title, content=content,
                      title_size=sp(18), size_hint=(0.85, 0.4))
        btn.bind(on_press=popup.dismiss)
        popup.open()


class InspectionApp(App):
    def build(self):
        self.title = "巡检助手"
        self.login = LoginScreen(on_success=self.enter_main)
        return self.login

    def enter_main(self):
        self.main = MainScreen()
        self.root.clear_widgets()
        self.root.add_widget(self.main)
        # 首次进入直接申请权限
        Clock.schedule_once(lambda *_: self.main.ask_permissions(), 0.3)


if __name__ == "__main__":
    InspectionApp().run()
