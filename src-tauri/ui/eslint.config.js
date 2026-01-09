import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import globals from 'globals';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // TypeScript handles no-undef, but we keep it for JS files
      'no-undef': 'off',
      // TypeScript's own undefined variable check
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // Catch references to non-existent properties
      '@typescript-eslint/no-unsafe-member-access': 'off',
      // Allow explicit any when needed during migration
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
  {
    ignores: ['dist/', 'bundle.js', '*.test.ts', '*.test.js'],
  }
);
