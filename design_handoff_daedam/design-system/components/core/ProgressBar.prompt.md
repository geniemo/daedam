```jsx
<ProgressBar pct={62} />
<ProgressBar pct={78} height={6} fill="var(--color-ink)" track="var(--color-line-3)" />  {/* 점수 바 */}
```
Rule from the codebase: never fake a percentage. Deep Research gives none, so the research screen uses IndeterminateBar.
