(async () => {
  // 收集所有样式
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
    } catch(e) {
      console.warn('获取样式失败:', link.href, e);
    }
  });
  
  await Promise.all(fetchPromises);
  
  // 3. 添加字体定义（使用相对路径）
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
  
  // 克隆 DOM
  const htmlContent = document.documentElement.cloneNode(true);
  htmlContent.querySelectorAll('link[rel="stylesheet"]').forEach(link => link.remove());
  
  // 创建样式标签
  const combinedStyle = document.createElement('style');
  combinedStyle.textContent = styles.join('\n\n');
  
  const head = htmlContent.querySelector('head');
  if (head) {
    head.appendChild(combinedStyle);
  } else {
    htmlContent.insertBefore(combinedStyle, htmlContent.firstChild);
  }
  
  // 生成并下载 HTML
  const doctype = '<!DOCTYPE html>\n';
  const finalHtml = doctype + htmlContent.outerHTML;
  const blob = new Blob([finalHtml], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `exported_${Date.now()}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
  console.log('✅ 导出完成！');
  console.log('📁 请执行以下操作：');
  console.log('   1. 将字体文件复制到与 HTML 同一目录');
  console.log(`   2. 字体文件路径: /Applications/Qoder.app/Contents/Resources/app/extensions/aicoding-file-icons/icons/aicoding-seti.woff`);
  console.log('   3. 重命名复制后的字体文件为: aicoding-seti.woff');
})();