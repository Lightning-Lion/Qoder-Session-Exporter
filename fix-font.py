#!/usr/bin/env python3
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import unquote
import json
import base64

# ===== 配置区域 =====
#
# 工作流程说明：
#   1. export-session.js（在 Qoder 浏览器控制台中运行）
#      - 收集页面全部样式
#      - 扫描 vscode-file:// 资源，用 fetch() 获取；在样式中将 URL 替换为 ./assets/<filename>
#      - 将资源数据以 <script id="__qoder_assets__"> 形式嵌入 HTML
#      - 在样式中注入 @font-face { font-family: 'qoder-seti'; src: url('./aicoding-seti.woff') }
#      - 下载单一 HTML 文件
#
#   2. fix-font.py（在终端运行，处理上一步导出的 HTML）
#      - 从 HTML 的 __qoder_assets__ 数据块解码 data URI，拆分为 sessions/assets/ 中的单独文件
#      - 自动移除 HTML 中的数据块（得到干净的小 HTML）
#      - 将 aicoding-seti.woff 复制到 sessions 目录
#      - 处理 HTML 中残留的 vscode-file://vscode-app/ 引用（fetch 失败的回退）
#      - 将 ../../media/ 等相对路径字体引用替换为本地路径
#      - CSS 优化：去重、压缩、外置为 styles.css，HTML 中仅保留 <link> 引用
#      - 最终 HTML ~1 MB，CSS 异步加载，打开速度大幅提升

QODER_APP = "/Applications/Qoder.app/Contents/Resources/app"

# 已知的固定字体文件（由 export-session.js 注入的 @font-face 引用）
# export-session.js 在样式开头添加了如下规则：
#   @font-face { font-family: 'qoder-seti'; src: url('./aicoding-seti.woff'); }
# 此处将其复制到 sessions 目录，使该引用能正确加载
FONT_SOURCE = os.path.join(
    QODER_APP,
    "extensions/aicoding-file-icons/icons/aicoding-seti.woff"
)

# Qoder 内 media 目录，包含 codicon.ttf、iconfont.woff、InstrumentSans.ttf
MEDIA_DIR = os.path.join(QODER_APP, "out/media")

# 已知的相对路径字体映射：CSS 中的相对路径 → Qoder 中的实际文件
RELATIVE_FONT_MAP = {
    "../../media/codicon.ttf": os.path.join(MEDIA_DIR, "codicon.ttf"),
    "../../media/iconfont.woff": os.path.join(MEDIA_DIR, "iconfont.woff"),
    "../../media/InstrumentSans-VariableFont_wdth,wght.ttf": os.path.join(MEDIA_DIR, "InstrumentSans-VariableFont_wdth,wght.ttf"),
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(SCRIPT_DIR, "sessions")
# ===================


def unescape_css_url(escaped: str) -> str:
    r"""将 CSS 转义的 URL 还原：\: → :, \/ → /, \. → . 等"""
    return re.sub(r'\\(.)', r'\1', escaped)


def resolve_vscode_file(escaped_url: str) -> Optional[str]:
    """解析 vscode-file://vscode-app/... 为本地文件系统路径
    返回绝对路径，若无法解析则返回 None"""
    clean = unescape_css_url(escaped_url)
    prefix = "vscode-file://vscode-app/"
    if clean.startswith(prefix):
        return "/" + clean[len(prefix):]
    return None


def find_all_vscode_app_urls(html: str) -> list[dict]:
    """在 HTML 中查找所有 vscode-file://vscode-app/ 引用"""
    # 匹配 CSS 转义形式和常规形式的 vscode-file URL
    pattern = r'vscode-file(?:\\[.:\/\\a-zA-Z0-9_ -]|[.:\/\\a-zA-Z0-9_ -])+?\.(?:svg|png|jpg|jpeg|gif|webp|woff2?|ttf|otf|eot)'
    seen = set()
    results = []
    for m in re.finditer(pattern, html, re.IGNORECASE):
        escaped_url = m.group(0)
        if escaped_url not in seen:
            seen.add(escaped_url)
            local_path = resolve_vscode_file(escaped_url)
            if local_path and os.path.exists(local_path):
                results.append({
                    'escaped': escaped_url,
                    'local_path': local_path,
                    'filename': os.path.basename(local_path),
                })
    return results


def find_all_relative_font_refs(html: str) -> list[dict]:
    """在 HTML 中查找已知的相对路径字体引用"""
    results = []
    for rel_path, local_path in RELATIVE_FONT_MAP.items():
        if rel_path in html:
            results.append({
                'escaped': rel_path,
                'local_path': local_path,
                'filename': os.path.basename(local_path),
            })
    return results


def copy_to_sessions(src: str, subdir: str = "") -> Optional[str]:
    """将文件复制到 sessions 目录（可选子目录），返回相对路径"""
    dest_dir = SESSIONS_DIR
    if subdir:
        dest_dir = os.path.join(dest_dir, subdir)
    os.makedirs(dest_dir, exist_ok=True)

    filename = os.path.basename(src)
    dest = os.path.join(dest_dir, filename)

    # 处理重名：如果已存在同名但不同路径的文件，加前缀
    if os.path.exists(dest) and os.path.getsize(dest) != os.path.getsize(src):
        name, ext = os.path.splitext(filename)
        prefix = os.path.basename(os.path.dirname(src)).replace(".", "_")
        filename = f"{name}_{prefix}{ext}"
        dest = os.path.join(dest_dir, filename)

    if not os.path.exists(dest):
        shutil.copy2(src, dest)

    return f"./{filename}" if not subdir else f"./{subdir}/{filename}"


def extract_font_face_definitions(html_content):
    """提取 HTML 中所有的 @font-face 定义"""
    pattern = r'@font-face\s*\{[^}]*\}'
    matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
    return matches


def parse_font_face_block(block):
    """解析一个 @font-face 块，返回 {font-family, src_urls}"""
    result = {
        'font_family': None,
        'src_urls': [],
        'full_block': block
    }
    family_match = re.search(r'font-family\s*:\s*[\'"]?([^\'";}]+)[\'"]?', block, re.IGNORECASE)
    if family_match:
        result['font_family'] = family_match.group(1).strip()
    url_pattern = r'url\([\'"]?([^\'")]+)[\'"]?\)'
    url_matches = re.findall(url_pattern, block, re.IGNORECASE)
    result['src_urls'] = url_matches
    return result


def find_font_face_for_family(html_content, target_family):
    """查找指定 font-family 的 @font-face 定义"""
    blocks = extract_font_face_definitions(html_content)
    for block in blocks:
        parsed = parse_font_face_block(block)
        if parsed['font_family'] and target_family in parsed['font_family']:
            return parsed
    return None


def replace_in_html(html: str, old: str, new: str, label: str = "") -> tuple:
    """在 HTML 中替换字符串，返回 (修改后的内容, 变更记录)"""
    count = html.count(old)
    if count > 0:
        html = html.replace(old, new)
        return html, [f"   替换 [{label}]: {old[:60]}… → {new}"]
    return html, []


def process_assets_json(html_content):
    """从 HTML 中提取 __qoder_assets__ 数据块，将 data URI 解码为 assets/ 中的单独文件
    返回移除数据块后的 HTML 内容"""
    pattern = r'<script id="__qoder_assets__" type="application/json">(.*?)</script>'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        print("\n   ℹ️ HTML 中未发现 __qoder_assets__ 数据块，跳过资源拆分")
        return html_content

    print("\n" + "=" * 60)
    print("📦 资源拆分：从 HTML 提取 data URI 生成单独文件")
    print("=" * 60)

    asset_map = json.loads(match.group(1))

    assets_dir = os.path.join(SESSIONS_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    count = 0
    for filename, data_uri in asset_map.items():
        m = re.match(r'data:([^;]+);base64,(.+)', data_uri)
        if not m:
            print(f"   ⚠️ 无法解析 data URI: {filename}")
            continue
        raw_data = base64.b64decode(m.group(2))

        dest_path = os.path.join(assets_dir, filename)
        with open(dest_path, 'wb') as f:
            f.write(raw_data)
        count += 1

    print(f"\n✅ 已生成 {count} 个资源文件 → {assets_dir}/")

    # 移除 script 数据块
    html_content = html_content.replace(match.group(0), '')
    print("🗑️ 已从 HTML 中移除 __qoder_assets__ 数据块")

    return html_content


def optimize_css(html_content):
    """提取所有 <style> 内容，去重合并且写出 styles.css，用 <link> 替代
    返回 (处理后的 HTML, 变更记录列表)"""
    pattern = r'<style[^>]*>.*?</style>'
    styles = re.findall(pattern, html_content, re.DOTALL)

    if not styles:
        return html_content, []

    changes = []

    # 提取纯 CSS 内容
    css_list = []
    for s in styles:
        content = re.sub(r'<style[^>]*>', '', s, count=1).replace('</style>', '')
        css_list.append(content)

    original_total = sum(len(c) for c in css_list)

    # ── 去重（保留首次出现的顺序）──
    seen = set()
    unique = []
    dedup_count = 0
    for content in css_list:
        if content in seen:
            dedup_count += 1
            continue
        seen.add(content)
        unique.append(content)

    if dedup_count > 0:
        changes.append(f"   ✅ 去重: 移除 {dedup_count} 个完全重复的样式块")

    # ── 合并 ──
    combined = '\n\n'.join(unique)

    # ── 压缩（移除注释、多余空白）──
    minified = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', combined)
    minified = re.sub(r'[\r\n]+', ' ', minified)
    minified = re.sub(r'\s{2,}', ' ', minified)
    minified = re.sub(r'\s*([{}:;,])\s*', r'\1', minified)
    minified = minified.strip()

    minified_total = len(minified)
    savings = original_total - minified_total

    if savings <= 0:
        changes.append("   ℹ️ 压缩后无收益，跳过外置")
        return html_content, changes

    pct = savings * 100 // original_total
    changes.append(f"   📉 压缩: {original_total/1024:.0f} KB → {minified_total/1024:.0f} KB (节省 {savings/1024:.0f} KB, {pct}%)")

    # ── 写出 styles.css ──
    styles_css_path = os.path.join(SESSIONS_DIR, 'styles.css')
    with open(styles_css_path, 'w', encoding='utf-8') as f:
        f.write(minified)
    changes.append(f"   📄 写出: styles.css ({minified_total/1024:.0f} KB)")

    # ── HTML 中删除所有 <style>，注入 <link> ──
    html_content = re.sub(pattern, '', html_content, count=0, flags=re.DOTALL)
    link_tag = '\n  <link rel="stylesheet" href="./styles.css">\n'
    html_content = html_content.replace('</head>', link_tag + '</head>')
    changes.append("   🔗 已替换 <style> → <link href='./styles.css'>")

    return html_content, changes


def main(html_path):
    print("=" * 60)
    print("Qoder Session 资源修复工具")
    print("=" * 60)

    # ── 0. 检查基础依赖 ──
    if not os.path.exists(QODER_APP):
        print(f"\n❌ Qoder 应用路径不存在: {QODER_APP}")
        print("   请确认 Qoder 已安装")
        return

    # ── 1. 准备 HTML ──
    print("\n📁 检查文件...")
    if not os.path.exists(html_path):
        print(f"   ❌ 找不到 HTML 文件: {html_path}")
        return
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    html_basename = os.path.basename(html_path)
    working_html = os.path.join(SESSIONS_DIR, html_basename)
    shutil.copy2(html_path, working_html)
    print(f"   ✅ 已复制: {working_html}")

    print("\n📖 读取 HTML...")
    with open(working_html, 'r', encoding='utf-8') as f:
        html_content = f.read()
    modified = html_content
    all_changes = []

    # ── 2. 处理 assets 数据块（将 data URI 拆分为单独文件）──
    modified = process_assets_json(modified)

    # ── 3. 处理 aicoding-seti.woff 字体 ──
    # export-session.js 注入的 @font-face 引用了 ./aicoding-seti.woff。
    # 此处将该字体从 Qoder.app 复制到 sessions 目录。
    # 如果 HTML 中已有该 @font-face，只需修复 URL 路径；
    # 如果没有（旧版导出），则自动补插完整的 @font-face 规则。
    print("\n" + "=" * 60)
    print("🔤 第二步：处理 aicoding-seti 图标字体")
    print("=" * 60)

    if os.path.exists(FONT_SOURCE):
        existing = find_font_face_for_family(modified, "qoder-seti")
        font_filename = "aicoding-seti.woff"
        font_dest = os.path.join(SESSIONS_DIR, font_filename)

        if not os.path.exists(font_dest):
            shutil.copy2(FONT_SOURCE, font_dest)
            print(f"\n✅ 已复制字体: {FONT_SOURCE}")
            print(f"   → {font_dest}")

        if existing:
            for url in existing['src_urls']:
                new_url = f"./{font_filename}"
                if url != new_url:
                    modified, changes = replace_in_html(modified, url, new_url, f"aicoding-seti")
                    all_changes.extend(changes)
        else:
            # 没有 @font-face，手动添加
            new_ff = f"\n<style>\n@font-face {{\n    font-family: 'qoder-seti';\n    src: url('./{font_filename}') format('woff');\n    font-weight: normal;\n    font-style: normal;\n}}\n</style>\n"
            if '</head>' in modified:
                modified = modified.replace('</head>', new_ff + '</head>')
            else:
                modified = new_ff + modified
            all_changes.append(f"   ✅ 已插入 qoder-seti @font-face")

        print(f"   ✅ aicoding-seti 字体处理完成")
    else:
        print(f"   ⚠️ aicoding-seti.woff 未找到，跳过")

    # ── 4. 处理 vscode-file://vscode-app/ 资源（SVG 图标、备用字体）──
    # export-session.js 会尝试将 vscode-file:// 资源嵌入为 data URI，
    # 但对于 Qoder.app 内的字体文件（aicoding-icon-0123.ttf、logo-*.woff 等），
    # 如果嵌入失败或体积过大，这里会在文件系统中找到它们并复制到 sessions 目录。
    # 对于指向其他用户扩展路径（/Users/lion/...）的引用，因本地无对应文件而自动跳过。
    print("\n" + "=" * 60)
    print("🎨 第三步：处理 vscode-file:// 资源引用")
    print("=" * 60)

    vscode_resources = find_all_vscode_app_urls(modified)
    # 去重（按本地路径去重）
    seen_paths = {}
    for r in vscode_resources:
        seen_paths.setdefault(r['local_path'], []).append(r)

    if not seen_paths:
        print("\n   ℹ️ 未发现 vscode-file://vscode-app/ 引用")
    else:
        print(f"\n📦 发现 {len(seen_paths)} 个唯一资源:")
        for local_path, entries in seen_paths.items():
            filename = entries[0]['filename']
            size = os.path.getsize(local_path)
            rel = copy_to_sessions(local_path)
            if rel:
                print(f"\n   📄 {filename} ({size:,} 字节)")
                print(f"     来源: {local_path}")
                print(f"     目标: {SESSIONS_DIR}/{filename}")
                for entry in entries:
                    escaped = entry['escaped']
                    # 同时在 url() 内外与纯 URL 处都替换
                    modified, c1 = replace_in_html(modified, f"url('{escaped}')", f"url('{rel}')", filename)
                    modified, c2 = replace_in_html(modified, f'url("{escaped}")', f'url("{rel}")', filename)
                    modified, c3 = replace_in_html(modified, escaped, rel, filename)
                    all_changes.extend(c1)
                    all_changes.extend(c2)
                    all_changes.extend(c3)

    # ── 5. 处理 ../../media/ 相对路径字体 ──
    # HTML 中部分 @font-face 使用了相对于 Qoder.app 内 media 目录的路径
    # （如 ../../media/codicon.ttf），这些路径在离线打开时无效。
    # 此处将对应文件复制到 sessions 目录并将路径替换为 ./filename。
    print("\n" + "=" * 60)
    print("📦 第四步：处理 ../../media/ 相对路径字体")
    print("=" * 60)

    relative_fonts = find_all_relative_font_refs(modified)
    if not relative_fonts:
        print("\n   ℹ️ 未发现 ../../media/ 引用")
    else:
        print(f"\n📦 发现 {len(relative_fonts)} 个相对路径字体:")
        for entry in relative_fonts:
            if os.path.exists(entry['local_path']):
                filename = entry['filename']
                size = os.path.getsize(entry['local_path'])
                rel = copy_to_sessions(entry['local_path'])
                if rel:
                    print(f"\n   📄 {filename} ({size:,} 字节)")
                    print(f"     来源: {entry['local_path']}")
                    print(f"     目标: {SESSIONS_DIR}/{filename}")
                    # 替换路径中可能携带的 ?hash 参数
                    old_path = entry['escaped']
                    modified, c1 = replace_in_html(modified, old_path, rel, filename)
                    all_changes.extend(c1)
                    # 也处理带 hash 的版本
                    if '?' in old_path:
                        base = old_path.split('?')[0]
                        modified, c2 = replace_in_html(modified, base, rel, f"{filename} (base)")
                        all_changes.extend(c2)
            else:
                print(f"\n   ⚠️ {entry['filename']} 未找到: {entry['local_path']}")

    # ── 6. CSS 优化（去重 + 外置 + 压缩）──
    print("\n" + "=" * 60)
    print("📄 第六步：CSS 优化")
    print("=" * 60)
    modified, css_changes = optimize_css(modified)
    if css_changes:
        all_changes.extend(css_changes)
    else:
        print("   ℹ️ 无 <style> 块需处理")

    # ── 7. 写回文件 ──
    if all_changes:
        print("\n💾 保存修改...")
        with open(working_html, 'w', encoding='utf-8') as f:
            f.write(modified)
        print(f"   ✅ 已保存: {working_html}")
    else:
        print("\n   ℹ️ 无需修改")

    # ── 8. 报告 ──
    print("\n" + "=" * 60)
    print("📊 执行报告")
    print("=" * 60)
    print(f"\n   🔄 共执行 {len(all_changes)} 次替换")
    for c in all_changes:
        print(c)

    # 列出 sessions 目录中的文件（含 assets/ 子目录）
    print(f"\n📁 sessions 目录内容:")
    if os.path.isdir(SESSIONS_DIR):
        for root, dirs, files in os.walk(SESSIONS_DIR):
            rel_root = os.path.relpath(root, SESSIONS_DIR)
            for f in sorted(files):
                fp = os.path.join(root, f)
                size = os.path.getsize(fp)
                label = os.path.join(rel_root, f) if rel_root != '.' else f
                print(f"   📄 {label} ({size:,} 字节)")

    print("\n" + "=" * 60)
    print("🎉 处理完成！")
    print("=" * 60)
    print("\n📖 直接打开 sessions 目录中的 HTML 即可离线浏览")
    print("   提示：如需重新导出，先在 Qoder 控制台运行 export-session.js，再运行本脚本")
    print("   💡 CSS 已外置为 styles.css，打开速度主要取决于该文件体积")



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python fix-font.py <HTML文件路径>")
        print("示例: python fix-font.py /path/to/exported_session.html")
        sys.exit(1)
    main(sys.argv[1])