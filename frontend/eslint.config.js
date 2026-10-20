import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  { name: 'app/files-to-lint', files: ['**/*.{ts,mts,vue}'] },
  // schema.d.ts is generated from the backend's OpenAPI schema and never edited by hand.
  globalIgnores(['**/dist/**', '**/coverage/**', 'src/api/schema.d.ts']),
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    name: 'app/rules',
    rules: {
      // `_request`: a parameter that must exist for the signature but is not used.
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  // Formatting is Prettier's job; ESLint only checks code quality.
  skipFormatting,
)
