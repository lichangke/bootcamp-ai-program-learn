# Instructions

## code review command

帮我参照 @.codex/prompts/speckit.specify.md 的结构，think ultra hard, 构建一个对构建一个对Python 和 Typescript代码进行深度代码审查的命令，放在  @.codex/prompts/下 。主要考虑几个方面：
- 架构和设计：是否考虑python 和 typescript的架构和设计最佳实践？是否有清晰的接口设计？是否考虑一定程度的可扩展性
- KISS原则
- 代码质量：DRY，YAGNI，SOLID，etc.函数原则上不超过 150行，参数原则上不超过7个。
- 使用 builder 模式


## 构建详细的设计

根据 @specs/w3/raflow/0001-spec.md 的内容，进行系统的 web search 确保信息的准确性，尤其是使用最新版本的 dependencies。根据你了解的知识，构建一个详细的设计文档，放在 ./specs/w3/raflow/0002-design.md 文件中,输出为中文，使用 mermaid 绘制架构，设计，组件，流程等图表并详细说明。

## 实现

根据 @specs/w3/raflow/0002-design.md 和./specs/w3/raflow/0003-implementation-plan.md 文件中的设计，完整实现 phase 0。

## 问题

**填写了ELEVENLABS_KEY还是 读取不到**
数据库持久话问题

**出现 Error: websocket closed: invalid_request ：**
```
2026-02-20T14:38:10.670057Z  WARN ThreadId(05) src-tauri\src\lib.rs:236: network transport error: scribe error: invalid_request: Invalid language code received: 'cn'. Please leave blank if you want to automatically detect the language or use one of: afr, amh, ara, asm, ast, aze, bak, bas, bel, ben, bhr, bod, bos, bre, bul, cat, ceb, ces, chv, ckb, cnh, cre, cym, dan, dav, deu, div, dyu, ell, eng, epo, est, eus, fao, fas, fil, fin, fra, fry, ful, gla, gle, glg, guj, hat, hau, heb, hin, hrv, hsb, hun, hye, ibo, ina, ind, isl, ita, jav, jpn, kab, kan, kas, kat, kaz, kea, khm, kin, kir, kln, kmr, kor, kur, lao, lat, lav, lij, lin, lit, ltg, ltz, lug, luo, mal, mar, mdf, mhr, mkd, mlg, mlt, mon, mri, mrj, msa, mya, myv, nan, nep, nhi, nld, nor, nso, nya, oci, ori, orm, oss, pan, pol, por, pus, quy, roh, ron, rus, sah, san, sat, sin, skr, slk, slv, smo, sna, snd, som, sot, spa, sqi, srd, srp, sun, swa, swe, tam, tat, tel, tgk, tha, tig, tir, tok, ton, tsn, tuk, tur, twi, uig, ukr, umb, urd, uzb, vie, vot, vro, wol, xho, yid, yor, yue, zgh, zho, zul, zza.
2026-02-20T14:38:10.670344Z  WARN ThreadId(05) src-tauri\src\lib.rs:236: network transport error: websocket closed: invalid_request
```

语言类型填错了


**录制时出现问题：**
```
在录制时出现新问题，日志如下
2026-02-20T14:45:40.989904Z  INFO ThreadId(04) src-tauri\src\commands.rs:393: recording pipeline started
2026-02-20T14:45:40.990139Z  INFO ThreadId(04) src-tauri\src\lib.rs:259: scribe session started session_id="30c1523aee5f4330b319a44515cf0a95"
2026-02-20T14:45:43.597203Z ERROR ThreadId(25) C:\Users\admin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\enigo-0.2.1\src\win\win_impl.rs:448: TryFromIntError(())
2026-02-20T14:45:43.597702Z  WARN ThreadId(04) src-tauri\src\lib.rs:381: failed to inject transcript: failed to simulate keyboard input: you tried to simulate invalid input: (key state could not be converted to u32)
2026-02-20T14:45:46.700675Z ERROR ThreadId(25) C:\Users\admin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\enigo-0.2.1\src\win\win_impl.rs:448: TryFromIntError(())
2026-02-20T14:45:46.700890Z  WARN ThreadId(21) src-tauri\src\lib.rs:381: failed to inject transcript: failed to simulate keyboard input: you tried to simulate invalid input: (key state could not be converted to u32)
2026-02-20T14:45:51.014915Z ERROR ThreadId(25) C:\Users\admin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\enigo-0.2.1\src\win\win_impl.rs:448: TryFromIntError(())
2026-02-20T14:45:51.015260Z  WARN ThreadId(04) src-tauri\src\lib.rs:381: failed to inject transcript: failed to simulate keyboard input: you tried to simulate invalid input: (key state could not be converted to u32)
```
这个错误是 Windows 上 enigo 对某些字符（常见是中文/特殊 Unicode）走“逐字键盘模拟”时触发的已知兼容问题。

**任务栏图标空白问题**

**多次 启动录制 停止录制 还有点问题**

```
2026-02-20T14:59:42.695566Z  INFO ThreadId(05) src-tauri\src\commands.rs:393: recording pipeline started
2026-02-20T14:59:42.890376Z  WARN ThreadId(50) src-tauri\src\network\scribe_client.rs:224: websocket send failed, invalidating connection: IO error: A Tokio 1.x context was found, but it is being shutdown.
2026-02-20T14:59:42.890630Z  WARN ThreadId(50) src-tauri\src\network\scribe_client.rs:392: failed to shutdown websocket connection: failed to close websocket connection: IO error: A Tokio 1.x context was found, but it is being shutdown.
2026-02-20T14:59:44.803930Z  INFO ThreadId(50) src-tauri\src\network\scribe_client.rs:259: websocket connection created
2026-02-20T14:59:44.804035Z  INFO ThreadId(05) src-tauri\src\lib.rs:266: scribe session started session_id="d056d9e3b54647b4874f9d0ed28d102d"
2026-02-20T14:59:44.804097Z  WARN ThreadId(50) src-tauri\src\commands.rs:578: network send is slower than expected send_ms=1914 chunks=1 samples=1556
2026-02-20T14:59:45.351646Z  WARN ThreadId(50) src-tauri\src\commands.rs:578: network send is slower than expected send_ms=300 chunks=2 samples=3200
```

**开始录制后，不说话，等一会儿会光标处出现一些文字**


## 生成更新的 design doc

仔细阅读目前./w3/raflow 的代码，think ultra hard,构建一个更新的 design doc,放在./specs/w3/raflow/0004-design.md文件中，输出为中文,使用mermaid绘制架构,设计,组件,流程等图表并详细说明。You, 16 minutes ago + Uncommitted changes


## 降噪

请结合 w3\raflow 代码架构，搜寻合适的 降噪 处理方案，处理以下问题
1、不说话时，出现其他文字
2、说话的内容，没有转成文字

nnnoiseless   https://github.com/jneem/nnnoiseless 

