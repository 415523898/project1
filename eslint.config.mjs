import { createRequire } from 'node:module'

const require = createRequire(new URL('./frontend/package.json', import.meta.url))
const js = require('@eslint/js')
const ts = require('typescript-eslint')
const vue = require('eslint-plugin-vue')
const vueParser = require('vue-eslint-parser')
const globals = require('globals')
const prettier = require('eslint-config-prettier/flat')
const tsFiles = ['frontend/src/**/*.ts', 'frontend/src/**/*.vue', 'frontend/*.ts']
const jsFiles = ['eslint.config.mjs']

// Reserve the compatibility names for exactly one exported function and arity.
const modelDefaultsAbiRule = {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      scope: '{{name}} is reserved for the exact modelDefaults compatibility parameter.',
    },
  },
  create(context) {
    return {
      'Program:exit'() {
        for (const scope of context.sourceCode.scopeManager.scopes) {
          for (const variable of scope.variables) {
            if (!['_upstream', '_protocol'].includes(variable.name)) continue
            const index = variable.name === '_upstream' ? 1 : 2
            for (const definition of variable.defs) {
              if (definition.type !== 'Parameter') continue
              const fn = scope.block
              if (
                fn.type !== 'FunctionDeclaration' ||
                fn.id?.name !== 'modelDefaults' ||
                fn.parent?.type !== 'ExportNamedDeclaration' ||
                fn.params.length !== 3 ||
                fn.params[index] !== definition.name
              )
                context.report({
                  node: definition.name,
                  messageId: 'scope',
                  data: { name: variable.name },
                })
            }
          }
        }
      },
    }
  },
}

export default [
  {
    name: 'project/protected-source-boundaries',
    ignores: [
      '**/node_modules/**',
      'frontend/src/data/method-graph.ts',
      'frontend/src/data/method-embeddings.ts',
    ],
  },
  { ...js.configs.recommended, files: [...tsFiles, ...jsFiles] },
  ...ts.configs.recommended.map((config) => ({ ...config, files: tsFiles })),
  ...vue.configs['flat/essential'].map((config) => ({
    ...config,
    files: ['frontend/src/**/*.vue'],
  })),
  {
    name: 'project/vue-typescript-parser',
    files: ['frontend/src/**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: { parser: ts.parser, extraFileExtensions: ['.vue'] },
    },
  },
  {
    name: 'project/browser-application',
    files: ['frontend/src/**/*.ts', 'frontend/src/**/*.vue'],
    ignores: ['frontend/src/models/**'],
    languageOptions: { globals: globals.browser },
  },
  {
    name: 'project/web-worker',
    files: ['frontend/src/models/**/*.ts'],
    languageOptions: { globals: globals.worker },
  },
  {
    name: 'project/node',
    files: [...jsFiles, 'frontend/*.ts'],
    languageOptions: { globals: globals.node },
  },
  {
    name: 'project/explicit-model-defaults-abi',
    files: ['frontend/src/utils/model-config.ts'],
    plugins: { 'project-abi': { rules: { 'reserved-parameters': modelDefaultsAbiRule } } },
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_(?:upstream|protocol)$' },
      ],
      'project-abi/reserved-parameters': 'error',
    },
  },
  { linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: 'error' } },
  // Layout is owned by Prettier; correctness/unused/explicit-any rules remain active.
  prettier,
]
