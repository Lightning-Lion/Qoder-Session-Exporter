/**
 * Qoder 所有折叠区域一键展开/折叠脚本
 *
 * 支持两种 DOM 结构：
 *   1. activity-group-card（已探索/搜索类）
 *   2. answer-think-section（深度思考类）
 *
 * 展开后会自动清理内层文本的高度限制（max-height），
 * 让外层聊天框自适应内层 Text 的实际高度，避免内容被截断。
 *
 * 使用方式：在浏览器开发者控制台（F12）中，执行：
 *   1. 复制本文件全部内容
 *   2. 粘贴到 Console 面板，回车
 *
 * 可用命令：
 *   expandAll()              — 展开所有折叠区域（自动清理高度限制）
 *   collapseAll()            — 折叠所有展开区域
 *   toggleAll()              — 全部切换（展开↔折叠）
 *   expandDeepThinking()     — 展开所有「深度思考」组
 *   expandExplored()         — 展开所有「已探索/搜索」组
 *   expandByText('深度思考')  — 按文字展开
 *   removeAllConstraints()   — 清理所有聊天框高度限制（展开后调用）
 *   activityGroupStats()     — 查看统计
 */

(function () {
  'use strict';

  // ====================== DOM 结构适配 ======================
  //
  // 类型 A — activity-group-card（已探索）:
  //   <div class="activity-group-card collapsed explored">
  //     <div class="activity-group-reasoning-header cursor-pointer"> ... </div>
  //     <div class="grid grid-rows-[0fr] ...">  <!-- 折叠内容 -->  </div>
  //   </div>
  //
  // 类型 B — answer-think-section（深度思考）:
  //   <div class="answer-think-section">
  //     <div class="flex ... cursor-pointer ...">  <!-- 点击 header -->  </div>
  //     <div class="grid grid-rows-[0fr] ...">    <!-- 折叠内容 -->  </div>
  //   </div>
  //
  // ======================================================

  // ====================== DOM 查询 ======================

  /** 获取所有可折叠容器（两种类型） */
  function getAllContainers() {
    const cards = document.querySelectorAll('.activity-group-card');
    const thinks = document.querySelectorAll('.answer-think-section');
    return [...cards, ...thinks];
  }

  /** 获取所有带有 aria-label="展开全部" 的按钮（待办列表底部） */
  function getExpandAllButtons() {
    return document.querySelectorAll('button[aria-label="展开全部"]');
  }

  /** 获取容器的点击 header */
  function getHeader(container) {
    if (container.classList.contains('activity-group-card')) {
      return container.querySelector('.activity-group-reasoning-header');
    }
    // answer-think-section: 取第一个 cursor-pointer 子元素
    return container.querySelector('.cursor-pointer');
  }

  // ====================== 状态判断 ======================

  function isCollapsed(container) {
    if (container.classList.contains('activity-group-card')) {
      return container.classList.contains('collapsed');
    }
    // answer-think-section: 检查 grid 子元素是否有 grid-rows-[0fr]
    const grid = container.querySelector('.grid');
    if (!grid) return true;
    return grid.classList.contains('grid-rows-[0fr]');
  }

  // ====================== 类型判断 ======================

  /** 获取容器的类型和摘要文字 */
  function getGroupType(container) {
    const header = getHeader(container);
    const label = header?.querySelector('.text-text-tertiary');
    const summary = container.querySelector('.activity-group-summary');
    const fullText = container.textContent.trim();

    const labelText = label?.textContent?.trim() || '';
    const summaryText = summary?.textContent?.trim() || '';

    // 判断类型
    if (labelText.includes('深度思考')) {
      return { type: 'deep-thinking', label: labelText };
    }
    if (summary || summaryText) {
      const prefix = labelText || '已探索';
      return { type: 'explored', label: `${prefix} ${summaryText}`.trim() };
    }
    // 兜底：按文字内容判断
    if (fullText.includes('深度思考')) {
      return { type: 'deep-thinking', label: fullText.slice(0, 30) };
    }

    return { type: 'unknown', label: labelText || fullText.slice(0, 40) };
  }

  // ====================== 点击操作 ======================

  function clickElement(el) {
    if (!el) return false;
    try {
      el.click();
    } catch (_) {
      const evt = new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
      });
      el.dispatchEvent(evt);
    }
    return true;
  }

  // ====================== 高度约束清理 ======================

  /**
   * 移除容器内所有高度限制，让内层文本按实际需要高度显示。
   * 展开折叠区域后调用，否则即使 grid 变为 [1fr]，内层 div 仍被 max-height 截断。
   */
  function removeHeightConstraints(container) {
    // 1. custom-scrollbar 及其直接子级：移除 max-height 限制（"深度思考"内容区）
    container.querySelectorAll('.custom-scrollbar').forEach(el => {
      if (el.style.maxHeight && el.style.maxHeight !== 'none' && el.style.maxHeight !== '') {
        el.style.maxHeight = 'none';
      }
    });
    container.querySelectorAll('.custom-scrollbar > *:first-child').forEach(el => {
      if (el.style.maxHeight && el.style.maxHeight !== 'none' && el.style.maxHeight !== '') {
        el.style.maxHeight = 'none';
      }
    });

    // 2. answer-think-markdown：移除高度限制
    container.querySelectorAll('.answer-think-markdown').forEach(el => {
      if (el.style.maxHeight && el.style.maxHeight !== 'none') {
        el.style.maxHeight = 'none';
      }
    });

    // 3. 用户消息输入框：移除固定高度，还原为自适应
    container.querySelectorAll('.chat-input-contenteditable').forEach(el => {
      if (el.style.height && el.style.height !== 'auto') {
        el.style.height = 'auto';
      }
      if (el.style.maxHeight && el.style.maxHeight !== 'none') {
        el.style.maxHeight = 'none';
      }
      if (el.style.minHeight) {
        el.style.minHeight = 'auto';
      }
    });

    // 4. 混合输入容器：移除固定高度
    container.querySelectorAll('.chat-mixed-input-container').forEach(el => {
      if (el.style.height && el.style.height !== 'auto') {
        el.style.height = 'auto';
      }
    });

    // 5. 遍历所有带内联 style 且包含 max-height 的元素（兜底清理）
    container.querySelectorAll('[style*="max-height"]').forEach(el => {
      const cur = el.style.maxHeight;
      // 跳过已处理过的、显式 none 的、以及 CSS 变量
      if (cur && cur !== 'none' && !cur.startsWith('var(') && cur !== '') {
        el.style.maxHeight = 'none';
      }
    });

    // 6. 处理 collapsible-sticky-container 的 CSS 变量约束
    const sticky = container.closest('.collapsible-sticky-container') || container.querySelector('.collapsible-sticky-container');
    if (sticky) {
      sticky.style.setProperty('--collapsed-max-height', 'none');
      sticky.style.setProperty('--expanded-max-height', 'none');
    }

    // 7. 处理 activity-group-content 内的 grid 高度限制
    container.querySelectorAll('.activity-group-content [style*="max-height"]').forEach(el => {
      if (el.style.maxHeight && el.style.maxHeight !== 'none') {
        el.style.maxHeight = 'none';
      }
    });
  }

  // ====================== 全局高度约束清理 ======================

  /**
   * 清理整个页面中所有聊天框的高度限制。
   * 无论折叠状态如何，测量内容实际高度并直接设定 height。
   * 可在 expandAll() 之后调用，或在导出前单独执行。
   */
  function removeAllConstraints() {
    // 作用于整个 document
    removeHeightConstraints(document.body);

    // 额外处理 collapsible-sticky-container
    document.querySelectorAll('.collapsible-sticky-container').forEach(el => {
      el.style.setProperty('--collapsed-max-height', 'none');
      el.style.setProperty('--expanded-max-height', 'none');
      el.style.maxHeight = 'none';
    });

    // 额外处理 sticky-message
    document.querySelectorAll('.sticky-message').forEach(el => {
      el.style.maxHeight = 'none';
    });

    // 额外处理「展开全部」按钮所在的父容器（待办列表区域）
    document.querySelectorAll('button[aria-label="展开全部"]').forEach(btn => {
      const parent = btn.closest('[class*="plan"], [class*="todo"], [class*="list"]');
      if (parent) removeHeightConstraints(parent);
    });

    console.log('✅ 已清理所有聊天框的高度限制');
  }

  // ====================== 延迟 ======================

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // ====================== 核心函数 ======================

  /**
   * 展开所有折叠区域 (展开后自动清理高度约束)
   * @param {number} interval 每次点击间隔（ms）
   */
  async function expandAll(interval = 200) {
    const containers = getAllContainers();
    let count = 0;

    for (const c of containers) {
      if (isCollapsed(c)) {
        const header = getHeader(c);
        if (header) {
          clickElement(header);
          count++;
          await delay(interval);
          // 展开后等待布局完成，再移除内层高度限制
          removeHeightConstraints(c);
        }
      }
    }

    // 额外点击所有"展开全部"按钮（待办列表底部）
    const planButtons = getExpandAllButtons();
    for (const btn of planButtons) {
      clickElement(btn);
      await delay(interval);
    }
    if (planButtons.length > 0) {
      console.log(`   ↳ 并点击了 ${planButtons.length} 个「展开全部」按钮`);
    }

    console.log(`✅ 已展开 ${count} 个折叠区域，并移除了内层高度限制`);
    return count;
  }

  /**
   * 折叠所有已展开区域
   * @param {number} interval 每次点击间隔（ms）
   */
  async function collapseAll(interval = 200) {
    const containers = getAllContainers();
    let count = 0;

    for (const c of containers) {
      if (!isCollapsed(c)) {
        const header = getHeader(c);
        if (header) {
          clickElement(header);
          count++;
          await delay(interval);
        }
      }
    }

    console.log(`✅ 已折叠 ${count} 个展开区域`);
    return count;
  }

  /**
   * 切换所有区域（展开↔折叠）
   * 展开后自动清理内层高度限制；折叠时不受影响。
   * @param {number} interval 每次点击间隔（ms）
   */
  async function toggleAll(interval = 200) {
    const containers = getAllContainers();
    let count = 0;

    for (const c of containers) {
      const wasCollapsed = isCollapsed(c);
      const header = getHeader(c);
      if (header) {
        clickElement(header);
        count++;
        await delay(interval);
        // 如果是展开操作，清理高度约束
        if (wasCollapsed) {
          removeHeightConstraints(c);
        }
      }
    }

    console.log(`✅ 已切换 ${count} 个区域`);
    return count;
  }

  /**
   * 展开所有「深度思考」区域 (展开后自动清理高度约束)
   * @param {number} interval 每次点击间隔（ms）
   */
  async function expandDeepThinking(interval = 200) {
    return expandByType('deep-thinking', interval);
  }

  /**
   * 展开所有「已探索」区域 (展开后自动清理高度约束)
   * @param {number} interval 每次点击间隔（ms）
   */
  async function expandExplored(interval = 200) {
    return expandByType('explored', interval);
  }

  /**
   * 按类型展开折叠区域 (展开后自动清理高度约束)
   * @param {'deep-thinking'|'explored'} type
   * @param {number} interval 每次点击间隔（ms）
   */
  async function expandByType(type, interval = 200) {
    const containers = getAllContainers();
    let count = 0;

    for (const c of containers) {
      if (!isCollapsed(c)) continue;

      const info = getGroupType(c);
      if (info.type !== type) continue;

      const header = getHeader(c);
      if (header) {
        clickElement(header);
        count++;
        await delay(interval);
        removeHeightConstraints(c);
      }
    }

    const typeName = type === 'deep-thinking' ? '深度思考' : '已探索';
    console.log(`✅ 已展开 ${count} 个「${typeName}」区域，并移除了内层高度限制`);
    return count;
  }

  /**
   * 按摘要文字展开匹配的区域 (展开后自动清理高度约束)
   * @param {string} text 摘要文字（如 '深度思考', '已探索'）
   * @param {number} interval 每次点击间隔（ms）
   */
  async function expandByText(text, interval = 200) {
    const containers = getAllContainers();
    let count = 0;

    for (const c of containers) {
      if (!isCollapsed(c)) continue;

      const info = getGroupType(c);
      if (info.label.includes(text)) {
        const header = getHeader(c);
        if (header) {
          clickElement(header);
          count++;
          await delay(interval);
          removeHeightConstraints(c);
        }
      }
    }

    console.log(`✅ 已展开 ${count} 个包含 "${text}" 的区域，并移除了内层高度限制`);
    return count;
  }

  // ====================== 状态统计 ======================

  function stats() {
    const containers = getAllContainers();
    let collapsed = 0;
    let expanded = 0;
    const typeCount = { 'deep-thinking': 0, explored: 0, unknown: 0 };

    containers.forEach((c) => {
      if (isCollapsed(c)) collapsed++;
      else expanded++;

      const info = getGroupType(c);
      typeCount[info.type]++;
    });

    console.log(`📊 折叠区域统计:`);
    console.log(`   共 ${containers.length} 个`);
    console.log(`   🧠 深度思考: ${typeCount['deep-thinking']}`);
    console.log(`   🔍 已探索:   ${typeCount['explored']}`);
    if (typeCount['unknown']) {
      console.log(`   ❓ 未知类型: ${typeCount['unknown']}`);
    }
    console.log(`   🔒 折叠: ${collapsed}`);
    console.log(`   🔓 展开: ${expanded}`);

    return {
      total: containers.length,
      ...typeCount,
      collapsed,
      expanded,
    };
  }

  // ====================== 导出到全局 ======================

  window.expandAll = expandAll;
  window.collapseAll = collapseAll;
  window.toggleAll = toggleAll;
  window.expandDeepThinking = expandDeepThinking;
  window.expandExplored = expandExplored;
  window.expandByText = expandByText;
  window.activityGroupStats = stats;
  window.removeAllConstraints = removeAllConstraints;

  // 执行一次统计
  stats();

  console.log('可用命令:');
  console.log('  expandAll()              — 展开全部（自动清理高度限制）');
  console.log('  collapseAll()            — 折叠全部');
  console.log('  toggleAll()              — 全部切换（展开时清理高度限制）');
  console.log('  expandDeepThinking()     — 展开「深度思考」');
  console.log("  expandExplored()         — 展开「已探索」");
  console.log("  expandByText('关键字')    — 按文字展开");
  console.log('  removeAllConstraints()   — 清理所有聊天框高度限制（展开后调用）');
  console.log('  activityGroupStats()     — 查看统计');
})();
