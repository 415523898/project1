import { cpSync, existsSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { execFileSync } from 'node:child_process'

import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { frontendConfig } from './src/config.ts'

const project = fileURLToPath(new URL('..', import.meta.url))
const interpreter = process.platform === 'win32' ? ['Scripts', 'python.exe'] : ['bin', 'python']
// 依次尝试：显式指定的解释器、项目根的 .venv、.local 下的独立环境。
// 源码版把虚拟环境放在项目根，安装版放在 .local，两者都保留以兼容既有安装。
const candidates = [
  process.env.FOREST_PYTHON,
  resolve(project, '.venv', ...interpreter),
  resolve(project, '.local', '.venv', ...interpreter),
].filter((value): value is string => Boolean(value))
const python = candidates.find(existsSync)
if (!python) {
  throw new Error(
    `找不到 Python 解释器。已尝试：\n  ${candidates.join('\n  ')}\n` +
      '请在项目根目录执行 python -m venv .venv 创建环境，或用 FOREST_PYTHON 指向 python.exe。',
  )
}
const server = JSON.parse(
  execFileSync(python, ['-B', 'backend/config.py'], { cwd: project, encoding: 'utf8' }),
) as {
  host: string
  port: number
  local_root: string
  public_dir: string
  dist: string
  cert_dir: string
}
mkdirSync(server.public_dir, { recursive: true })
cpSync(resolve(project, 'frontend/public'), server.public_dir, { recursive: true })
const BACKEND = process.env.FOREST_BACKEND_URL || `http://${server.host}:${server.port}`
const CERT_FILE = process.env.FOREST_HTTPS_CERT || resolve(server.cert_dir, 'dev-cert.pem')
const KEY_FILE = process.env.FOREST_HTTPS_KEY || resolve(server.cert_dir, 'dev-key.pem')
// 开发服务器与预览服务器共用同一个代理，保证 npm run dev 与 npm run preview 行为一致。
const proxy = {
  '/api': {
    target: BACKEND,
    changeOrigin: true,
    secure: false,
  },
}

function tls() {
  if (process.env.FOREST_HTTPS === '0') return undefined
  if (!existsSync(CERT_FILE) || !existsSync(KEY_FILE)) return undefined
  return { cert: readFileSync(CERT_FILE), key: readFileSync(KEY_FILE) }
}

const https = tls()

export default defineConfig({
  cacheDir: resolve(server.local_root, 'cache/vite'),
  publicDir: server.public_dir,
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: frontendConfig.server.host,
    port: frontendConfig.server.port,
    strictPort: true,
    https,
    proxy,
  },
  preview: {
    host: frontendConfig.server.host,
    port: frontendConfig.server.port,
    https,
    proxy,
  },
  build: {
    outDir: resolve(project, 'frontend/dist'),
    emptyOutDir: true,
  },
})
