# de-confounded open-ended — cross-vendor の*多様性*は genuine に効くか

同じ合成器(opus)で **同ベンダ合成**(opus×2案) と **異ベンダ合成**(opus+codex案) を作り、中立 judge(sonnet, haiku＝生成器でも合成器でもない)で比較。両方 2案 merge・同筆・同長＝情報優位/長さ/自己judge を相殺し、**差はソースの多様性だけ**。

## 多様性 gain（異ベンダ − 同ベンダ合成）= **-0.083**
| task | 同ベンダ合成 | 異ベンダ合成 | 多様性 gain |
|---|---|---|---|
| Design a token-bucket rate limiter for a web API: the p... | 8.75 | 8.5 | **-0.25** |
| Cache results of an expensive idempotent function in a ... | 9.0 | 8.5 | **-0.5** |
| Design a backoff-and-retry policy for calls to a flaky ... | 8.5 | 9.0 | **+0.5** |

## 読み
- **gain>0 なら cross-vendor の*多様性*が genuine に効く**（merge/長さを相殺した上で）＝mesh の真の燃料は*異種性*。
- gain≈0 なら open-ended の +0.83 は『2案 merge＋長さ』が主因で、cross-vendor 固有の利得は小さい。
- 位置バイアスは task index で X/Y 入替えて相殺。judge は2機の平均。少標本・主観。
