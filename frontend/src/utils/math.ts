import katex from 'katex'
import 'katex/dist/katex.min.css'

interface Formula {
  source: string
  tex: string
  display: boolean
}

/** Protect complete formulas before Markdown splits tables or interprets TeX underscores. */
export function extractMath(text: string): { text: string; restore: (host: HTMLElement) => void } {
  let prefix = '\uE000math'
  while (text.includes(prefix)) prefix += '_'
  const formulas: Formula[] = []
  let protectedText = '',
    position = 0
  while (position < text.length) {
    const rest = text.slice(position)
    const code = /^(`+|~{3,})/.exec(rest)
    if (code) {
      const end = text.indexOf(code[1]!, position + code[1]!.length)
      const next = end < 0 ? text.length : end + code[1]!.length
      protectedText += text.slice(position, next)
      position = next
      continue
    }
    if (rest.startsWith('\\\\') || rest.startsWith('\\$')) {
      protectedText += rest.slice(0, 2)
      position += 2
      continue
    }
    const delimiter = rest.startsWith('$$')
      ? (['$$', '$$', true] as const)
      : rest.startsWith('\\[')
        ? (['\\[', '\\]', true] as const)
        : rest.startsWith('\\(')
          ? (['\\(', '\\)', false] as const)
          : rest.startsWith('$')
            ? (['$', '$', false] as const)
            : null
    if (delimiter) {
      const [open, close, display] = delimiter
      let end = text.indexOf(close, position + open.length)
      while (end >= 0 && close === '$' && text[end - 1] === '\\')
        end = text.indexOf(close, end + close.length)
      if (end >= 0) {
        const tex = text.slice(position + open.length, end)
        // Keep currency fragments such as "$20 and $30" as ordinary prose.
        if (tex.trim() && (display || !/^\d[\d,.]*(?:\s+[a-zA-Z]+\s*)*$/.test(tex))) {
          const token = `${prefix}${formulas.length}\uE001`
          formulas.push({ source: text.slice(position, end + close.length), tex, display })
          protectedText += token
          position = end + close.length
          continue
        }
      }
    }
    protectedText += text[position++]
  }
  return {
    text: protectedText,
    restore(host) {
      if (!formulas.length) return
      const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT)
      const nodes: Text[] = []
      while (walker.nextNode())
        if (walker.currentNode.textContent?.includes(prefix)) nodes.push(walker.currentNode as Text)
      for (const node of nodes) {
        const pieces = document.createDocumentFragment()
        const pattern = new RegExp(`${prefix}(\\d+)\uE001`, 'g')
        let last = 0
        for (const match of node.data.matchAll(pattern)) {
          pieces.append(document.createTextNode(node.data.slice(last, match.index)))
          const formula = formulas[Number(match[1])]!
          const rendered = document.createElement('span')
          try {
            katex.render(formula.tex, rendered, {
              displayMode: formula.display,
              throwOnError: true,
              trust: false,
              strict: 'ignore',
              maxExpand: 1000,
              maxSize: 20,
              macros: {},
            })
          } catch {
            rendered.className = 'math-source'
            rendered.textContent = formula.source
          }
          pieces.append(rendered)
          last = match.index! + match[0].length
        }
        pieces.append(document.createTextNode(node.data.slice(last)))
        node.replaceWith(pieces)
      }
    },
  }
}
