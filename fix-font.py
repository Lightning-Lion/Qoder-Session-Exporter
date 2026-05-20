#!/usr/bin/env python3
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

# ===== 配置区域 =====
FONT_SOURCE = "/Applications/Qoder.app/Contents/Resources/app/extensions/aicoding-file-icons/icons/aicoding-seti.woff"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(SCRIPT_DIR, "sessions")
# ===================

def extract_font_face_definitions(html_content):
    """提取 HTML 中所有的 @font-face 定义"""
    # 匹配 @font-face { ... } 块
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
    
    # 提取 font-family
    family_match = re.search(r'font-family\s*:\s*[\'"]?([^\'";}]+)[\'"]?', block, re.IGNORECASE)
    if family_match:
        result['font_family'] = family_match.group(1).strip()
    
    # 提取 src 中的所有 url()
    url_pattern = r'url\([\'"]?([^\'")]+)[\'"]?\)'
    url_matches = re.findall(url_pattern, block, re.IGNORECASE)
    result['src_urls'] = url_matches
    
    return result

def find_font_face_for_family(html_content, target_family):
    """查找指定 font-family 的 @font-face 定义"""
    blocks = extract_font_face_definitions(html_content)
    
    print(f"\n🔍 正在搜索 font-family 包含 '{target_family}' 的 @font-face 定义...")
    print(f"   共找到 {len(blocks)} 个 @font-face 块")
    
    for i, block in enumerate(blocks):
        parsed = parse_font_face_block(block)
        print(f"\n   --- 第 {i+1} 个 @font-face ---")
        print(f"   font-family: {parsed['font_family']}")
        print(f"   src 中的 URL: {parsed['src_urls']}")
        
        if parsed['font_family'] and target_family in parsed['font_family']:
            print(f"   ✅ 匹配成功！")
            return parsed
    
    print(f"\n   ❌ 未找到匹配 '{target_family}' 的 @font-face 定义")
    return None

def replace_font_urls(html_content, old_urls, new_url):
    """替换 HTML 中的字体 URL"""
    modified_content = html_content
    changes_made = []
    
    for old_url in old_urls:
        # 解码 URL（处理 %20 等转义）
        decoded_old = unquote(old_url)
        
        # 构建多种可能的匹配模式
        patterns = [
            (f"url('{old_url}')", f"url('{new_url}')"),
            (f'url("{old_url}")', f'url("{new_url}")'),
            (f"url({old_url})", f"url({new_url})"),
            (f"url('{decoded_old}')", f"url('{new_url}')"),
            (f'url("{decoded_old}")', f'url("{new_url}")'),
            (f"url({decoded_old})", f"url({new_url})"),
        ]
        
        for pattern, replacement in patterns:
            if pattern in modified_content:
                modified_content = modified_content.replace(pattern, replacement)
                changes_made.append(f"   替换: {pattern} -> {replacement}")
                break
        else:
            # 如果精确匹配失败，尝试正则替换
            new_pattern = r'url\([\'"]?[^\'")]*' + re.escape(os.path.basename(old_url)) + r'[\'"]?\)'
            replacement = f"url('{new_url}')"
            if re.search(new_pattern, modified_content):
                modified_content = re.sub(new_pattern, replacement, modified_content)
                changes_made.append(f"   正则替换: {os.path.basename(old_url)} -> {new_url}")
    
    return modified_content, changes_made

def main(html_path):
    print("=" * 60)
    print("字体路径修复工具")
    print("=" * 60)
    
    # 1. 检查文件是否存在
    print("\n📁 检查文件...")
    if not os.path.exists(html_path):
        print(f"   ❌ 找不到 HTML 文件: {html_path}")
        return
    
    if not os.path.exists(FONT_SOURCE):
        print(f"   ❌ 找不到字体文件: {FONT_SOURCE}")
        return
    print(f"   ✅ HTML 文件: {html_path}")
    print(f"   ✅ 字体文件: {FONT_SOURCE}")
    
    # 2. 复制 HTML 到 sessions 目录并读取
    print("\n📁 准备 sessions 目录...")
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    html_basename = os.path.basename(html_path)
    working_html = os.path.join(SESSIONS_DIR, html_basename)
    shutil.copy2(html_path, working_html)
    print(f"   ✅ 已复制 HTML 到 sessions: {working_html}")
    
    print("\n📖 读取 HTML 文件...")
    with open(working_html, 'r', encoding='utf-8') as f:
        html_content = f.read()
    print(f"   ✅ 已读取 {len(html_content)} 字符")
    
    # 3. 查找现有的 @font-face 定义
    print("\n" + "=" * 60)
    print("🔍 第一步：分析现有 @font-face 定义")
    print("=" * 60)
    
    # 先列出所有 @font-face
    all_font_faces = extract_font_face_definitions(html_content)
    print(f"\n📊 统计: HTML 中共有 {len(all_font_faces)} 个 @font-face 规则")
    
    # 查找 aicoding-seti 的定义
    target_family = "aicoding-seti"
    existing_font_face = find_font_face_for_family(html_content, target_family)
    
    # 4. 确定目标路径
    font_filename = os.path.basename(FONT_SOURCE)  # aicoding-seti.woff
    font_dest = os.path.join(SESSIONS_DIR, font_filename)
    relative_url = f"./{font_filename}"
    
    print("\n" + "=" * 60)
    print("📝 第二步：处理字体文件")
    print("=" * 60)
    print(f"\n📄 字体文件名: {font_filename}")
    print(f"📁 目标目录: {SESSIONS_DIR}")
    print(f"🔗 相对路径: {relative_url}")
    
    # 5. 复制字体文件
    print("\n💾 复制字体文件...")
    shutil.copy2(FONT_SOURCE, font_dest)
    print(f"   ✅ 已复制: {FONT_SOURCE}")
    print(f"   ✅   到: {font_dest}")
    print(f"   📦 文件大小: {os.path.getsize(font_dest):,} 字节")
    
    # 6. 修改 HTML
    print("\n" + "=" * 60)
    print("✏️ 第三步：修改 HTML 中的字体引用")
    print("=" * 60)
    
    modified_html = html_content
    
    if existing_font_face:
        # 找到了现有的定义，替换其中的 URL
        print(f"\n✅ 找到现有的 @font-face 定义:")
        print(f"   font-family: {existing_font_face['font_family']}")
        print(f"   原始 URL: {existing_font_face['src_urls']}")
        
        modified_html, changes = replace_font_urls(
            modified_html, 
            existing_font_face['src_urls'], 
            relative_url
        )
        
        if changes:
            print(f"\n🔄 执行了以下替换:")
            for change in changes:
                print(change)
        else:
            print(f"\n⚠️ 未找到需要替换的 URL，可能需要手动检查")
            
    else:
        # 没有找到定义，需要添加新的 @font-face
        print(f"\n⚠️ 未找到现有的 'qoder-seti' 定义")
        print(f"   将自动添加新的 @font-face 规则")
        
        new_font_face = f"""
<style>
@font-face {{
    font-family: '{target_family}';
    src: url('{relative_url}') format('woff');
    font-weight: normal;
    font-style: normal;
}}
</style>
"""
        # 插入到 </head> 之前
        if '</head>' in modified_html:
            modified_html = modified_html.replace('</head>', new_font_face + '</head>')
            print(f"\n   ✅ 已插入到 </head> 之前")
        else:
            modified_html = new_font_face + modified_html
            print(f"\n   ✅ 已插入到 HTML 开头")
    
    # 7. 写回文件
    print("\n💾 保存修改后的 HTML...")
    with open(working_html, 'w', encoding='utf-8') as f:
        f.write(modified_html)
    
    # 8. 验证并显示结果
    print("\n" + "=" * 60)
    print("✅ 完成！验证结果")
    print("=" * 60)
    
    # 验证新文件中的引用
    with open(working_html, 'r', encoding='utf-8') as f:
        final_content = f.read()
    
    # 检查相对路径是否出现
    if relative_url in final_content:
        print(f"\n✅ 确认: 相对路径 '{relative_url}' 已存在于 HTML 中")
    else:
        print(f"\n⚠️ 警告: 相对路径 '{relative_url}' 未在 HTML 中找到")
    
    # 统计最终结果
    final_font_faces = extract_font_face_definitions(final_content)
    print(f"\n📊 最终统计:")
    print(f"   - HTML 文件: {working_html}")
    print(f"   - 字体文件: {font_dest}")
    print(f"   - @font-face 规则数: {len(final_font_faces)}")
    
    print("\n" + "=" * 60)
    print("🎉 处理完成！")
    print("=" * 60)
    print("\n📖 使用说明:")
    print("   1. 这两个文件在同一目录下：")
    print(f"      {SESSIONS_DIR}/")
    print(f"      ├── {html_basename}")
    print(f"      └── {font_filename}")
    print("   2. 断开网络，用浏览器打开 HTML 文件")
    print("   3. 图标字体应该正常显示\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python fix-font.py <HTML文件路径>")
        print("示例: python fix-font.py /path/to/exported_session.html")
        sys.exit(1)
    main(sys.argv[1])