(async () => {
  // ==================== 辅助函数 ====================

  // blob → data URI
  function blobToDataUri(blob) {
    return new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });
  }

  // 将 CSS 转义的 URL 还原为实际 URL（\: → :, \/ → /, \. → . 等）
  function unescapeCss(str) {
    return str.replace(/\\([0-9a-fA-F]{1,6}\s?|.)/g, (_, c) => c);
  }

  // ==================== 收集所有样式 ====================

  const styles = [];

  // 1. 内联样式
  document.querySelectorAll('style').forEach(style => {
    styles.push(style.innerHTML);
  });

  // 2. 外部样式表
  const links = document.querySelectorAll('link[rel="stylesheet"]');
  const fetchPromises = Array.from(links).map(async link => {
    try {
      const response = await fetch(link.href);
      const css = await response.text();
      styles.push(css);
    } catch (e) {
      console.warn('获取样式失败:', link.href, e);
    }
  });

  await Promise.all(fetchPromises);

  // ==================== 嵌入 vscode-file:// 资源 ====================

  async function extractVscodeResources(styles) {
    const combined = styles.join('\n\n');
    const seen = new Set();
    const resources = [];

    // 匹配 CSS 转义形式的 URL: vscode-file\:\/\/vscode-app\/...
    const escapedRe = /vscode-file(?:\\[^\s"']|[^\s"'\\])+?\.(?:svg|png|jpg|jpeg|gif|webp|woff2?|ttf|otf|eot)/gi;
    let m;
    while ((m = escapedRe.exec(combined)) !== null) {
      const escapedUrl = m[0];
      if (!seen.has(escapedUrl)) {
        seen.add(escapedUrl);
        resources.push({ escaped: escapedUrl, clean: unescapeCss(escapedUrl) });
      }
    }

    // 匹配常规形式的 URL: vscode-file://vscode-app/...
    const normalRe = /vscode-file:\/\/vscode-app\/[^\s'")]+(?:\.(?:svg|png|jpg|jpeg|gif|webp|woff2?|ttf|otf|eot))/gi;
    while ((m = normalRe.exec(combined)) !== null) {
      const url = m[0];
      if (!seen.has(url)) {
        seen.add(url);
        resources.push({ escaped: url, clean: url });
      }
    }

    if (resources.length === 0) return {};

    console.log(`📦 发现 ${resources.length} 个 vscode-file:// 资源，正在获取…`);

    const assetMap = {};
    const nameCount = {};

    for (const { escaped, clean } of resources) {
      try {
        const res = await fetch(clean);
        if (!res.ok) {
          console.warn(`  ⚠️ HTTP ${res.status}: ${clean.slice(0, 60)}`);
          continue;
        }
        const blob = await res.blob();
        const dataUri = await blobToDataUri(blob);

        // 生成唯一文件名（保留原始扩展名）
        const basename = clean.split('/').pop().split('?')[0].split('#')[0] || 'resource';
        nameCount[basename] = (nameCount[basename] || 0) + 1;
        const filename = nameCount[basename] > 1
          ? `${nameCount[basename]}_${basename}`
          : basename;

        assetMap[filename] = dataUri;

        // 在样式字符串中将 URL 替换为 ./assets/<filename>
        for (let i = 0; i < styles.length; i++) {
          styles[i] = styles[i].split(escaped).join(`./assets/${filename}`);
          if (clean !== escaped) {
            styles[i] = styles[i].split(clean).join(`./assets/${filename}`);
          }
        }

        console.log(`  ✅ ${(blob.size / 1024).toFixed(1)} KB — ${filename}`);
      } catch (e) {
        console.warn(`  ❌ ${clean.slice(0, 60)}… — ${e.message}`);
      }
    }

    return assetMap;
  }

  const assetMap = await extractVscodeResources(styles);

  // ==================== 添加字体定义 ====================

  const fontFaceRule = `
@font-face {
  font-family: 'qoder-seti';
  src: url('./aicoding-seti.woff') format('woff');
  font-weight: normal;
  font-style: normal;
}
`;

  // 把字体定义加到样式最前面
  styles.unshift(fontFaceRule);

  // ==================== 克隆 DOM 并注入样式 ====================

  const htmlContent = document.documentElement.cloneNode(true);
  htmlContent.querySelectorAll('link[rel="stylesheet"]').forEach(link => link.remove());

  const combinedStyle = document.createElement('style');
  combinedStyle.textContent = styles.join('\n\n');

  const head = htmlContent.querySelector('head');
  if (head) {
    head.appendChild(combinedStyle);
  } else {
    htmlContent.insertBefore(combinedStyle, htmlContent.firstChild);
  }

  // ==================== 将资源映射嵌入 HTML ====================

  const timestamp = Date.now();
  const doctype = '<!DOCTYPE html>\n';
  const assetKeys = Object.keys(assetMap);

  if (assetKeys.length > 0) {
    const assetsScript = document.createElement('script');
    assetsScript.id = '__qoder_assets__';
    assetsScript.type = 'application/json';
    assetsScript.textContent = JSON.stringify(assetMap);
    htmlContent.appendChild(assetsScript);
    console.log(`📦 已嵌入 ${assetKeys.length} 个资源数据到 HTML 中`);
  } else {
    console.log('ℹ️ 无内联资源需要提取');
  }

  // ==================== 导出单一 HTML 文件 ====================

  const finalHtml = doctype + htmlContent.outerHTML;

  const htmlBlob = new Blob([finalHtml], { type: 'text/html' });
  const htmlUrl = URL.createObjectURL(htmlBlob);
  const a = document.createElement('a');
  a.href = htmlUrl;
  a.download = `exported_${timestamp}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(htmlUrl);
  console.log(`✅ 已导出：exported_${timestamp}.html`);
  console.log('📌 运行 fix-font.py 即可自动拆分资源与修复字体');
})();