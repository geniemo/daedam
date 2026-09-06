The one filled button on a screen — 회사 등록하기, 등록하고 준비 시작, 면접 시작하기, 이 회사로 다시 면접 보기.

```jsx
<PrimaryButton size="lg" onClick={start}>면접 시작하기</PrimaryButton>
<PrimaryButton disabled>다음</PrimaryButton>
```

Disabled is `--color-faintest` fill with white text (used while preflight is incomplete). Never use the accent color as a button fill on light surfaces; the only accent-filled button is 이어서 진행 on the dark stage.
