Four tiny status marks used in front of list rows.

```jsx
<AccentDot />                      {/* 면접 준비 완료 */}
<CheckDot size={15} /> 마이크가 소리를 잡았습니다
<EmptyDot size={15} /> 조용한 곳에서 진행합니다
<Spinner /> 조사를 시작하고 있습니다
```
Done rows use CheckDot + ink text; pending rows EmptyDot + muted text; the active row Spinner + accent text.
