<template>
  <article class="md-report" v-html="html"></article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ content: string }>()

/** V2.6: 基于 DOMParser 白名单的 XSS 过滤（替代不安全的黑名单正则） */
function sanitizeHtml(rawHtml: string): string {
  if (!rawHtml) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(rawHtml, 'text/html')

  const allowedTags = new Set([
    'p','br','div','span','h1','h2','h3','h4','h5','h6',
    'ul','ol','li','strong','em','b','i','a','img','table',
    'thead','tbody','tr','th','td','blockquote','code','pre',
    'hr','del','s','sup','sub',
  ])

  const allowedAttrs = new Set([
    'href','src','alt','title','class','style','target','rel',
    'width','height','colspan','rowspan','align',
  ])

  function walk(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) return
    if (node.nodeType !== Node.ELEMENT_NODE) {
      node.parentNode?.removeChild(node)
      return
    }
    const el = node as Element
    const tag = el.tagName.toLowerCase()

    // 1. 非法标签 → 替换为 span 并保留纯文本
    if (!allowedTags.has(tag)) {
      const span = doc.createElement('span')
      span.textContent = el.textContent || ''
      el.parentNode?.replaceChild(span, el)
      return
    }

    // 2. 过滤属性
    Array.from(el.attributes).forEach((attr) => {
      if (!allowedAttrs.has(attr.name.toLowerCase())) {
        el.removeAttribute(attr.name)
      }
    })

    // 3. 伪协议过滤 + 安全属性
    if (tag === 'a') {
      const href = el.getAttribute('href')
      if (href && /^javascript:/i.test(href)) {
        el.setAttribute('href', 'about:blank')
      }
      el.setAttribute('target', '_blank')
      el.setAttribute('rel', 'noopener noreferrer')
    }
    if (tag === 'img') {
      const src = el.getAttribute('src')
      if (src && /^javascript:/i.test(src)) {
        el.setAttribute('src', '')
      }
    }

    // 4. 递归处理子节点（先复制数组避免遍历中修改）
    Array.from(el.childNodes).forEach((child) => walk(child))
  }

  Array.from(doc.body.childNodes).forEach((child) => walk(child))
  return doc.body.innerHTML
}

const html = computed(() => {
  if (!props.content) return ''
  return sanitizeHtml(marked(props.content) as string)
})
</script>

<style scoped>
.md-report {
  color: var(--dm-text);
  line-height: 1.85;
  max-width: 64rem;
}

/* Headings */
.md-report :deep(h2) {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  color: var(--dm-text);
  margin: 32px 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--dm-border);
  letter-spacing: -0.01em;
}
.md-report :deep(h3) {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--dm-text2);
  margin: 24px 0 10px;
}

/* Blockquote */
.md-report :deep(blockquote) {
  background: linear-gradient(135deg, var(--dm-primary-soft), rgba(91,95,227,0.03));
  border-left: 4px solid var(--dm-primary);
  padding: 16px 20px;
  margin: 16px 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--dm-text2);
  font-size: 14px;
}
.md-report :deep(blockquote strong) {
  color: var(--dm-primary);
}

/* Tables */
.md-report :deep(table) {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 16px 0;
  font-size: 13px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 1px solid var(--dm-border);
}
.md-report :deep(th) {
  background: #F8FAFD;
  padding: 10px 14px;
  text-align: left;
  font-weight: 700;
  font-size: 11px;
  color: var(--dm-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid var(--dm-border);
}
.md-report :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid var(--dm-border2);
  color: var(--dm-text);
}
.md-report :deep(tr:last-child td) {
  border-bottom: none;
}
.md-report :deep(tr:hover td) {
  background: var(--dm-surface);
}

/* Code */
.md-report :deep(code) {
  background: var(--dm-surface);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: var(--dm-primary);
}
.md-report :deep(pre) {
  background: var(--dm-deep);
  padding: 20px 22px;
  border-radius: var(--radius);
  overflow-x: auto;
  margin: 16px 0;
}
.md-report :deep(pre code) {
  background: none;
  color: #E2E8F0;
  padding: 0;
}

/* Lists */
.md-report :deep(ul), .md-report :deep(ol) {
  padding-left: 22px;
}
.md-report :deep(li) {
  margin-bottom: 4px;
}

/* Links */
.md-report :deep(a) {
  color: var(--dm-primary);
  text-decoration: none;
  font-weight: 600;
}
.md-report :deep(a:hover) {
  text-decoration: underline;
}
</style>
