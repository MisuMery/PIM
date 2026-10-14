[app]
# 应用标题（安装后桌面图标下显示的名字）
title = 巡检助手

# 包名与域名：组成安卓包标识 com.inspection.helper
package.name = inspectionhelper
package.domain = com.inspection

# 源码目录（main.py 所在地）
source.dir = .

# 打包进 APK 的文件扩展名：py 源码 + png 图标 + ttf 中文字体
source.include_exts = py,png,ttf,ttc

# 版本号（纯数字，安卓 versionCode 会由它生成）
version = 1.0.0
android.numeric_version = 1

# 依赖：python3 + kivy
# 不锁版本，使用 p4a recipe 自带的验证版本，避免 patch/版本错配导致编译失败
requirements = python3,kivy

# 图标 / 启动图
icon.filename = %(source.dir)s/assets/icon.png
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #081C3E

# 竖屏
orientation = portrait
fullscreen = 0

# ----------
# 安卓配置
# ----------
# 权限：
#   READ/WRITE_EXTERNAL_STORAGE - 安卓 10 及以下读写外部存储
#   MANAGE_EXTERNAL_STORAGE    - 安卓 11+ 访问 /storage/emulated/0/widgetone/...
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

# API 组合：target 33 / min 24
# NDK 用 25b：p4a 对 28c 会提示"尚未完全验证"，25b 是长期稳定版本且体积更小
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True

# Android 10 兼容：以旧版存储模式运行（requestLegacyExternalStorage）
android.extra_manifest_application_arguments = %(source.dir)s/extra_manifest_application_arguments.xml

# 只编译 arm64-v8a（2019 年后安卓机全支持）
# 双架构会让 CI 磁盘/内存翻倍，容易构建失败；如需兼容 32 位老设备，
# 改成：android.archs = arm64-v8a,armeabi-v7a
android.archs = arm64-v8a

# 备份策略：巡检数据在外部存储，应用数据无需云备份
android.allow_backup = False

#
# iOS 段忽略（本工程仅安卓）
#

[buildozer]
# 构建_verbose日志，便于 CI 排错
log_level = 2
warn_on_root = 1
