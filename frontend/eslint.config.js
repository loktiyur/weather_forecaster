import { readdirSync } from 'node:fs'

import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

// Import rules between the folders of src/ (ARCHITECTURE.md §9.1), the frontend counterpart
// of the backend's import-linter contracts. Every folder in src/features/ gets a boundary.
// The phase that adds a feature also adds the imports it may make here, e.g. trips: ['weather'].
const ALLOWED_FEATURE_IMPORTS = {}

const FEATURES = readdirSync(new URL('./src/features', import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)

// Imports across folders use `@/...`, so the rules below can see where an import points.
const NO_PARENT_IMPORTS = { regex: '^\\.\\./', message: "Import across folders with '@/...'." }
// main.ts, App.vue and router.ts assemble the app from the features; nothing imports them.
const APP_SHELL = '@/(App\\.vue|router)$'

function importRules(name, files, ...patterns) {
  return {
    name: `app/imports/${name}`,
    files,
    rules: { 'no-restricted-imports': ['error', { patterns: [NO_PARENT_IMPORTS, ...patterns] }] },
  }
}

export default defineConfigWithVueTs(
  { name: 'app/files-to-lint', files: ['**/*.{ts,mts,vue}'] },
  // schema.d.ts is generated from the backend's OpenAPI schema and never edited by hand.
  globalIgnores(['**/dist/**', '**/coverage/**', 'src/shared/api/schema.d.ts']),
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    name: 'app/rules',
    rules: {
      // `_request`: a parameter that must exist for the signature but is not used.
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  importRules('src', ['src/**/*.{ts,vue}']),
  importRules('shared', ['src/shared/**/*.{ts,vue}'], {
    regex: `^(@/features/|${APP_SHELL})`,
    message: 'shared/ is used by every feature, so it must not import one (or the app shell).',
  }),
  ...FEATURES.map((feature) => {
    const allowed = [feature, ...(ALLOWED_FEATURE_IMPORTS[feature] ?? [])].join('|')
    return importRules(feature, [`src/features/${feature}/**/*.{ts,vue}`], {
      regex: `^(@/features/(?!(${allowed})(/|$))|${APP_SHELL})`,
      message: `features/${feature} may import only shared/ and the features listed in ALLOWED_FEATURE_IMPORTS (eslint.config.js).`,
    })
  }),
  // Formatting is Prettier's job; ESLint only checks code quality.
  skipFormatting,
)
