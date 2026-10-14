# 巡检助手（安卓 APK）

把 `kimi.py`（巡检自动化脚本）打包成安卓 App，通过 **GitHub Actions 云端编译**，
本地无需安装任何安卓开发环境。

## 功能

- 启动需密码登录（**默认密码：12138**，修改位置：`main.py` 中 `APP_PASSWORD`）
- 登录后自动申请存储权限（Android 11+ 引导开启"所有文件访问"）
- 输入用户名 / 用户代码，一键执行巡检自动化（逻辑与 `kimi.py` 完全一致）
- 实时滚动日志：加载记录数、每个任务处理结果、成功/失败统计
- 数据目录可在界面修改（默认 `/storage/emulated/0/widgetone/apps/NormalPIM/data`）

## 目录结构

```
kimi-android-app/
├── main.py                                   # App 主程序（登录 + UI + 巡检逻辑）
├── buildozer.spec                            # 打包配置
├── extra_manifest_application_arguments.xml   # Android 10 legacy 存储声明
├── .github/workflows/build.yml               # GitHub Actions 云端打包
├── .gitignore
└── assets/
    ├── icon.png / icon_fg.png / icon_bg.png   # 应用图标（含自适应图标）
    ├── presplash.png                          # 启动画面
    └── fonts/cjk.ttf                          # 内置中文字体（SimHei 子集）
```

## 打包步骤（重要，按顺序）

1. 登录 GitHub，新建一个仓库（public 免费；private 也能跑 Actions，每月有免费额度）
2. 把本目录所有文件上传到仓库根目录（网页端 *Add file → Upload files* 即可，
   注意 `.github/workflows/build.yml` 需要保留路径；移动端/网页不支持空文件夹，
   `assets/fonts` 里有字体文件所以没问题）
3. 上传完成后，仓库 *Actions* 标签页会自动触发 **Build Android APK** 工作流
   （若没有触发，进入 Actions 页手动点 *Run workflow*）
4. 等待约 15–30 分钟（首次构建需要下载 SDK/NDK，较慢）
5. 构建完成后，点击该次运行记录 → 页面底部 *Artifacts* → 下载
   `inspection-helper-apk` 压缩包，解压得到 `.apk` 文件
6. 将 APK 传到安卓手机安装（需允许"安装未知来源应用"）

## 使用说明（手机上）

1. 打开"巡检助手"，输入密码 `12138` 登录
2. 首次使用会弹出权限申请；Android 11+ 会跳到系统设置页，
   开启 **"允许管理所有文件"** 后返回 App
3. 确认数据目录正确（手机需已装 NormalPIM 并生成过数据）
4. 填写用户名 / 用户代码（须与 CHECKERLIST.txt 中的记录匹配）
5. 点击 **"一键执行巡检"**，完成后底部日志显示统计结果

## 修改默认密码

编辑 `main.py` 顶部：

```python
APP_PASSWORD = "12138"   # 改成你的密码
```

上传到 GitHub 后 Actions 自动重新打包。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| 安装时提示"未知来源" | 设置里允许该来源安装（浏览器/文件管理器） |
| 提示"数据目录不存在" | 手机上没有 `/storage/emulated/0/widgetone/...`，确认 NormalPIM 已运行过；或在界面里改目录 |
| 提示"未找到匹配用户" | 用户名/代码与 CHECKERLIST.txt 不一致 |
| Android 11+ 点执行没反应/无权限 | 去系统设置 → 应用 → 巡检助手 → 权限 → 允许管理所有文件 |
| 构建失败 | 看 Actions 日志；常见是文件没传全（尤其 assets/ 与 .github/） |

## 技术栈

- UI：Kivy 2.3.1
- 打包：Buildozer + python-for-android（官方 Docker 镜像）
- CI：GitHub Actions（ubuntu-latest + ArtemSBulgakov/buildozer-action@v1）
- 目标平台：Android 7.0+（min API 24，target API 33），arm64-v8a / armeabi-v7a 双架构
