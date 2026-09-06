Surface container for everything that isn't page background: company cards, metric cards, the research report, answer feedback rows.

```jsx
<Card padding={20} onClick={open}>…</Card>
<Card padding="36px 40px">{/* 문서 */}</Card>
```

One soft ink shadow (`--shadow-card`), no hover elevation. Interactive cards only change the cursor. Inner dividers use `--color-hair` (1px), never a second border color.
