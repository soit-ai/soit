// ESLint for the web app. Type checking is tsgo's job (npm run typecheck);
// this catches what types do not: hook misuse, unused code, accessibility.
import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['build/', '.react-router/', 'test-results/', 'playwright-report/', 'public/'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser } },
    plugins: { 'react-hooks': reactHooks, 'jsx-a11y': jsxA11y },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // Focus moves on purpose where a screen has one thing to do: the
      // second-factor code, the command palette, the chat composer.
      'jsx-a11y/no-autofocus': 'off',
      // Switch and Checkbox render a native input inside a wrapping label.
      'jsx-a11y/label-has-associated-control': [
        'error',
        { controlComponents: ['Switch', 'Checkbox'], depth: 3 },
      ],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // 220-odd existing uses, mostly at API and workflow-node boundaries.
      // Reported, not failed, until they are typed; new code should not add more.
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
    },
  },
  {
    files: ['scripts/**', '*.config.{js,ts,mjs}', 'e2e/**', 'e2e-real/**'],
    languageOptions: { globals: { ...globals.node } },
  },
)
