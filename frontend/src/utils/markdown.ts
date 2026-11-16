import { extractMath } from '@/utils/math'

const INLINE_SOURCE = /(`[^`\n]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))/

function inline(parent: HTMLElement, text: string, depth = 0): void {
  if (depth > 4) {
    parent.append(document.createTextNode(text))
    return
  }
  const pattern = new RegExp(INLINE_SOURCE.source, 'g')
  let last = 0
  let match = pattern.exec(text)
  while (match) {
    parent.append(document.createTextNode(text.slice(last, match.index)))
    const token = match[0]
    let node: Node
    if (token.startsWith('`')) {
      const code = document.createElement('code')
      code.textContent = token.slice(1, -1)
      node = code
    } else if (token.startsWith('**') || token.startsWith('__')) {
      const strong = document.createElement('strong')
      inline(strong, token.slice(2, -2), depth + 1)
      node = strong
    } else if (token.startsWith('*')) {
      const em = document.createElement('em')
      inline(em, token.slice(1, -1), depth + 1)
      node = em
    } else {
      const parts = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token)
      let link: Node
      try {
        const url = new URL(parts?.[2] ?? '')
        if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('protocol')
        const anchor = document.createElement('a')
        anchor.href = url.href
        anchor.target = '_blank'
        anchor.rel = 'noopener noreferrer'
        anchor.textContent = parts?.[1] ?? url.href
        link = anchor
      } catch {
        link = document.createTextNode(token)
      }
      node = link
    }
    parent.append(node)
    last = pattern.lastIndex
    match = pattern.exec(text)
  }
  parent.append(document.createTextNode(text.slice(last)))
}

const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?(\s*\|\s*:?-{2,}:?)+\s*\|?\s*$/
const LIST_LINE = /^\s*(?:(\d+)\.|[-*+])\s+(.+)$/
const FENCE = /^ {0,3}(`{3,}|~{3,})(.*)$/
const HEADING = /^#{1,6}\s+(.+)$/
const QUOTE = /^>\s?(.*)$/
const RULE = /^ {0,3}(?:(?:\* *){3,}|(?:- *){3,}|(?:_ *){3,})$/
const SETEXT = /^ {0,3}(?:=+|-+)\s*$/
const BLOCK_START = /^\s*(`{3,}|~{3,}|#{1,6}\s|>|(?:\d+\.|[-*+])\s)/

function tableCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isTableStart(lines: string[], index: number): boolean {
  const head = lines[index] ?? ''
  const separator = lines[index + 1] ?? ''
  return head.includes('|') && TABLE_SEPARATOR.test(separator) && tableCells(head).length >= 2
}

function table(lines: string[], index: number): { node: HTMLElement; next: number } | null {
  if (!isTableStart(lines, index)) return null
  const headers = tableCells(lines[index] ?? '')
  const body: string[][] = []
  let cursor = index + 2
  while (cursor < lines.length) {
    const row = lines[cursor] ?? ''
    if (!row.trim() || !row.includes('|')) break
    body.push(tableCells(row))
    cursor += 1
  }
  const wrapper = document.createElement('div')
  wrapper.className = 'md-table-scroll'
  const node = document.createElement('table')
  node.style.minWidth = `${headers.length * 140}px`
  const head_row = document.createElement('tr')
  for (const label of headers) {
    const cell = document.createElement('th')
    inline(cell, label)
    head_row.append(cell)
  }
  const thead = document.createElement('thead')
  thead.append(head_row)
  node.append(thead)
  const tbody = document.createElement('tbody')
  for (const row of body) {
    const tr = document.createElement('tr')
    for (let column = 0; column < headers.length; column += 1) {
      const cell = document.createElement('td')
      inline(cell, row[column] ?? '')
      tr.append(cell)
    }
    tbody.append(tr)
  }
  node.append(tbody)
  wrapper.append(node)
  return { node: wrapper, next: cursor }
}

export function renderMarkdown(parent: HTMLElement, text: string): void {
  const math = extractMath(text)
  renderBlocks(parent, math.text)
  math.restore(parent)
}

function renderBlocks(parent: HTMLElement, text: string): void {
  parent.replaceChildren()
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  let index = 0
  while (index < lines.length) {
    const line = lines[index] ?? ''
    if (!line.trim()) {
      index += 1
      continue
    }
    const fence = FENCE.exec(line)
    if (fence) {
      index += 1
      const code: string[] = []
      const closes = (value: string) => {
        const end = FENCE.exec(value)
        return (
          end &&
          end[1]![0] === fence[1]![0] &&
          end[1]!.length >= fence[1]!.length &&
          !end[2]?.trim()
        )
      }
      while (index < lines.length && !closes(lines[index] ?? '')) code.push(lines[index++] ?? '')
      if (index < lines.length) index += 1
      const pre = document.createElement('pre')
      const codeNode = document.createElement('code')
      codeNode.textContent = code.join('\n')
      pre.append(codeNode)
      parent.append(pre)
      continue
    }
    const grid = table(lines, index)
    if (grid) {
      parent.append(grid.node)
      index = grid.next
      continue
    }
    // A delimiter following paragraph text is a Setext heading. On its own it
    // is a thematic break. Fenced code was consumed above and stays literal.
    if (!RULE.test(line) && !BLOCK_START.test(line) && SETEXT.test(lines[index + 1] ?? '')) {
      const heading = document.createElement(
        (lines[index + 1] ?? '').trim().startsWith('=') ? 'h2' : 'h3',
      )
      inline(heading, line)
      parent.append(heading)
      index += 2
      continue
    }
    if (RULE.test(line)) {
      parent.append(document.createElement('hr'))
      index += 1
      continue
    }
    const list = LIST_LINE.exec(line)
    if (list) {
      const ordered = Boolean(list[1])
      const node: HTMLOListElement | HTMLUListElement = ordered
        ? document.createElement('ol')
        : document.createElement('ul')
      if (node instanceof HTMLOListElement) node.start = Number(list[1])
      while (index < lines.length) {
        const item = LIST_LINE.exec(lines[index] ?? '')
        if (!item || Boolean(item[1]) !== ordered || RULE.test(lines[index] ?? '')) break
        const li = document.createElement('li')
        inline(li, item[2] ?? '')
        node.append(li)
        index += 1
      }
      parent.append(node)
      continue
    }
    const heading = HEADING.exec(line)
    const quote = QUOTE.exec(line)
    let node = document.createElement(heading ? 'h4' : quote ? 'blockquote' : 'p')
    if (heading || quote) {
      inline(node, (heading ?? quote)?.[1] ?? '')
      index += 1
    } else {
      const paragraph = [lines[index++] ?? '']
      while (
        index < lines.length &&
        (lines[index] ?? '').trim() &&
        !BLOCK_START.test(lines[index] ?? '') &&
        !SETEXT.test(lines[index] ?? '') &&
        !RULE.test(lines[index] ?? '') &&
        !isTableStart(lines, index)
      ) {
        paragraph.push(lines[index++] ?? '')
      }
      if (SETEXT.test(lines[index] ?? '')) {
        node = document.createElement((lines[index++] ?? '').trim().startsWith('=') ? 'h2' : 'h3')
      }
      paragraph.forEach((value, position) => {
        if (position) node.append(document.createElement('br'))
        inline(node, value)
      })
    }
    parent.append(node)
  }
}
