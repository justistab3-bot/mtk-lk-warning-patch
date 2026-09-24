# MTK LK 去警告工具

[English](README.md) | 中文

一键去除 MTK（联发科）`lk.img` / `lk.bin` 镜像的 **Orange State / Red State / dm-verity**
开机警告和 5 秒启动延时。带图形界面、自动校验、一键还原。

![界面截图](docs/screenshot.png)

> 方法来源：[Hovatek 教程 thread-31664](https://www.hovatek.com/forum/thread-31664.html)

---

## 为什么要有这个工具

原教程要求用 HxD 手工操作：搜特征码、肉眼确认前面 4 字节是不是 `08B5`、手动把一片 ASCII
字符串改成 `00`，还要小心别碰到内核命令行。慢，而且容易出错。

更关键的是，教程把"隐藏警告文本"和"去 5 秒延时"当成两个独立技巧，**其实不是**。
反汇编 LK 后可以看到，那个延时特征码所在的函数正是**警告分发器**：

| `boot state` | 原始行为 |
|---|---|
| `1`（橙） | 打印 3 行警告 → `mdelay(5000)` |
| `2` / `3`（红） | 打印 4 行警告 → `mdelay(5000)` → `return -1` |
| `0`（绿） | `return 0`，无警告 |

把这个函数改成直接 `return 0`，**警告文本和 5 秒等待会一起消失**。而且对橙状态设备来说，
改前改后控制流完全一致（`sub_348C` 本来也是返回 `0`），风险极低。

## 打了什么补丁

**补丁 A（关键）**：按教程特征码定位分发函数（Android 10 以下 `7B441B681B68012B`，
10 及以上 `7B441B681B68022B`，并要求前 4 字节为 `08B5????`），重写函数开头：

```
08 B5 0A 4B 7B 44 1B 68 1B 68 01 2B     改前
08 B5 00 20 08 BD 1B 68 1B 68 01 2B     改后（push {r3,lr}; movs r0,#0; pop {r3,pc}）
```

**补丁 B（额外保险）**：清零警告文本字符串，同时**完全不碰**
`androidboot.verifiedbootstate=*`、`androidboot.veritymode=*`、`androidboot.atm=*`
这些内核启动参数。

**每次打补丁都会自动校验**：列出精确的差异区间、复查内核参数、统计警告文本残留、确认 LK
头部未变，并反汇编补丁点让你亲眼看到 `movs r0, #0`。

## 使用

到 [Releases](../../releases) 下载 `LKTool.exe` 直接运行，不需要装 Python。

1. 选择固件目录（比如 GeekFlashTool 的 readback 目录）
2. 工具会自动识别 `lk.img` + `lk2.img` 并勾选
3. 「扫描」预览 →「打补丁」→ 需要时用「校验」「还原备份」

> ### 刷入
> `lk` 与 `lk2` 是 A/B 双槽，**两个都要刷**。只刷一个的话设备可能从另一个槽启动，警告依旧存在。
> 工具每次打完补丁都会打印这条提醒，就是因为踩过这个坑。
>
> SP Flash Tool：载入 scatter，`lk` 和 `lk2` 分别指向补丁后的镜像，模式选 **Download Only**
> （不要用 Format All + Download）。
>
> 如果开机仍出现 `.........` 黑底白字计数，改用 fastboot：
> `fastboot flash lk lk_patched.img`

### 命令行

```
LKTool.exe --cli <lk.img> [--delay-only] [--inplace]

  --delay-only   只打补丁 A，不清空文本
  --inplace      直接覆盖原文件（仍会先备份）
```

直接传文件路径也会自动进入命令行模式。

## 输出文件

| 文件 | 说明 |
|---|---|
| `lk_original_backup.img` | 原始备份，改动前自动生成 |
| `lk_patched.img` | 补丁结果（默认，不覆盖原文件） |
| `lk.img` | 勾选「直接覆盖原文件」时才会覆盖 |

## 从源码构建

需要 Python 3.10+ 且**带 tkinter**，另外可选装 `capstone`（只用于校验时的反汇编显示，
没装也能正常跑）。

```
pip install capstone
python LKTool.py            # 从源码运行
build_exe.bat               # 用 PyInstaller 打包单文件 exe
```

### 文件结构

```
LKTool.py      入口（GUI / CLI 分流）
lk_gui.py      tkinter 界面
lk_core.py     扫描 / 打补丁 / 校验核心，无 GUI 依赖，可直接 import
build_exe.bat  PyInstaller 打包脚本
```

`lk_core.py` 除标准库外无任何依赖，可以接进你自己的脚本：

```python
import lk_core

data = lk_core.read_file('lk.img')
print(lk_core.scan(data)['patch_a'])      # 定位分发函数
new, log = lk_core.apply(data)            # 补丁 A + B
lk_core.write_file('lk_patched.img', new)
```

## LK 镜像结构备注

在 MT6739 镜像上实测，方便你继续扩展：

```
0x000000-0x0001FF   头部：magic 0x58881688 | size (u32 @0x04) | name[12] @0x08 ("lk")
                          ext_magic 0x58891689 @0x30
0x000200-...        有效负载（长度 = size 字段）
尾部                零填充至分区大小（1MB）
                    无附加签名块，头部无校验和字段
```

镜像使用 **PC 相对寻址 + 相对字面量池**，所以**搜不到**指向警告字符串的绝对地址。代码形如：

```asm
ldr r3, [pc, #0x28]   ; 字面量里存的是偏移量，不是地址
add r3, pc            ; r3 = 字面量 + (本指令地址 + 4)
ldr r3, [r3]
```

解析公式：`目标偏移 = 字面量值 + add指令地址 + 4`

## 已知限制

- 界面目前**只有中文**。欢迎补英文翻译，字符串都在 `lk_gui.py` 里。
- 目前只在 MT6739 / Android 9 时代的 LK 镜像上验证过。找不到特征码时工具会拒绝打补丁
  （fail safe），但欢迎其他平台的反馈。
- 补丁 B 只在"有其他代码路径会打印这些字符串"时才有意义，通常单靠补丁 A 就够了。

## 致谢

- 原始方法：[Hovatek — Remove orange / red state warning on MTK](https://www.hovatek.com/forum/thread-31664.html)
- 反汇编引擎：[Capstone](https://www.capstone-engine.org/)

## 许可

MIT，见 [LICENSE](LICENSE)。

刷写改过的 bootloader 风险自负。务必备份工具生成的备份，并在动手前确认你知道怎么救砖。
