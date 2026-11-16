export type CopyKind = 'code' | 'table'

const LABELS: Record<CopyKind, string> = {
  code: '复制代码',
  table: '复制表格',
}

export async function writeClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const active = document.activeElement
  const selection = window.getSelection()
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i).cloneRange())
    : []
  const input =
    active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement ? active : null
  const start = input?.selectionStart,
    end = input?.selectionEnd
  const field = document.createElement('textarea')
  field.value = text
  field.readOnly = true
  field.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
  ;(active?.closest('dialog[open]') ?? document.body).append(field)
  try {
    field.select()
    if (!document.execCommand('copy')) throw new Error('copy_failed')
  } finally {
    field.remove()
    if (active instanceof HTMLElement && active.isConnected) active.focus({ preventScroll: true })
    if (input && typeof start === 'number' && typeof end === 'number')
      input.setSelectionRange(start, end)
    if (selection && ranges.length) {
      selection.removeAllRanges()
      for (const range of ranges) selection.addRange(range)
    }
  }
}

function readableText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? ''
  if (!(node instanceof HTMLElement) || node.matches('.copy-toolbar, button')) return ''
  if (node.tagName === 'BR') return '\n'
  if (node.matches('.katex-display, .katex')) {
    const tex = node.querySelector('annotation[encoding="application/x-tex"]')?.textContent
    if (tex) return node.matches('.katex-display') ? `$$${tex}$$` : `$${tex}$`
  }
  const text = Array.from(node.childNodes, readableText).join('')
  if (node.tagName === 'LI') {
    const parent = node.parentElement
    const prefix =
      parent instanceof HTMLOListElement
        ? `${parent.start + Array.from(parent.children).indexOf(node)}. `
        : '- '
    return prefix + text + '\n'
  }
  return text + (/^(P|DIV|H[1-6]|BLOCKQUOTE|UL|OL)$/.test(node.tagName) ? '\n\n' : '')
}

export function copyContent(host: HTMLElement, kind: CopyKind): string {
  if (kind === 'code')
    return host.querySelector('pre code, pre')?.textContent ?? host.textContent ?? ''
  const table = host.querySelector('table')
  if (!table) return ''
  return Array.from(table.rows, (row) =>
    Array.from(row.cells, (cell) => {
      const value = readableText(cell).trim()
      return /[\t\n"]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
    }).join('\t'),
  ).join('\n')
}

/** Native adapter shared by Vue regions and the imperative Markdown renderer. */
export function bindCopyButton(
  button: HTMLButtonElement,
  text: () => string,
  kind: CopyKind,
): () => void {
  let disposed = false
  let pending = false
  let timer: ReturnType<typeof setTimeout> | undefined
  const reset = () => {
    button.setAttribute('aria-label', LABELS[kind])
    button.title = LABELS[kind]
    button.dataset.copyState = 'idle'
  }
  const copy = async () => {
    if (pending) return
    pending = true
    if (timer) clearTimeout(timer)
    try {
      await writeClipboard(text())
      if (disposed) return
      button.setAttribute('aria-label', '已复制')
      button.title = '已复制'
      button.dataset.copyState = 'success'
    } catch {
      if (disposed) return
      button.title = '复制未成功，请选中内容复制。'
      button.setAttribute('aria-label', button.title)
      button.dataset.copyState = 'error'
    } finally {
      pending = false
      if (!disposed) timer = setTimeout(reset, 1800)
    }
  }
  reset()
  button.addEventListener('click', copy)
  return () => {
    disposed = true
    if (timer) clearTimeout(timer)
    button.removeEventListener('click', copy)
  }
}

export function addMarkdownCopies(host: HTMLElement): () => void {
  const cleanups: Array<() => void> = []
  for (const child of Array.from(host.children)) {
    if (!(child instanceof HTMLElement)) continue
    if (!child.matches('pre, .md-table-scroll')) continue
    const kind: CopyKind = child.matches('pre') ? 'code' : 'table'
    const region = document.createElement('div')
    region.className = 'copy-region md-copy-region'
    region.dataset.copyKind = kind
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'content-copy-button'
    button.dataset.action = 'copy-content'
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    icon.setAttribute('viewBox', '0 0 24 24')
    icon.setAttribute('aria-hidden', 'true')
    icon.setAttribute('fill', 'none')
    icon.setAttribute('stroke', 'currentColor')
    icon.setAttribute('stroke-width', '1.6')
    const outline = document.createElementNS(icon.namespaceURI, 'path')
    outline.setAttribute('d', 'M8 8h12v13H8z M16 4V3H4v13h1')
    icon.append(outline)
    button.append(icon)
    const content = document.createElement('div')
    content.className = 'copy-content'
    child.before(region)
    region.append(button, content)
    content.append(child)
    cleanups.push(bindCopyButton(button, () => copyContent(content, kind), kind))
  }
  return () => cleanups.forEach((cleanup) => cleanup())
}
