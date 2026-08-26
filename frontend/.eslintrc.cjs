module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: ["eslint:recommended", "plugin:vue/vue3-recommended"],
  parser: "vue-eslint-parser",
  parserOptions: {
    ecmaVersion: "latest",
    parser: "@typescript-eslint/parser",
    sourceType: "module",
  },
  rules: {
    "no-undef": "off",
    "no-unused-vars": "off",
    "vue/html-indent": "off",
    "vue/max-attributes-per-line": "off",
    "vue/multi-word-component-names": "off",
    "vue/singleline-html-element-content-newline": "off",
  },
};
