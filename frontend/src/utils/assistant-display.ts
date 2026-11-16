/** Preserve the original log while hiding malformed tool markup in old replies. */
export function assistantDisplay(text: string): { text: string; malformed: boolean } {
  let code: { mark: string; width: number } | null = null
  for (let index = 0; index < text.length;) {
    const char = text[index]!
    if (char === '`' || char === '~') {
      let end = index + 1
      while (text[end] === char) end++
      const width = end - index
      if (code) {
        if (
          char === code.mark &&
          (width === code.width || (code.width >= 3 && width >= code.width))
        )
          code = null
      } else if (char === '`' || width >= 3) code = { mark: char, width }
      index = end
      continue
    }
    if (
      char === '<' &&
      !code &&
      /^<(?:tool_calls?(?:>|\s)|function=)/i.test(text.slice(index, index + 16))
    ) {
      return { text: text.slice(0, index), malformed: true }
    }
    index++
  }
  return { text, malformed: false }
}
