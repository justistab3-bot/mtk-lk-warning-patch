# -*- coding: utf-8 -*-
"""
MTK LK 去警告工具
参考教程: https://www.hovatek.com/forum/thread-31664.html

用法:
  双击 / 无参数运行          -> 打开图形界面
  LKTool.exe <lk.img>        -> 命令行模式处理单个镜像
  LKTool.exe --cli <lk.img> [--delay-only] [--inplace]

参数:
  --cli          强制命令行模式
  --delay-only   只打补丁 A（去警告 + 去 5 秒延时），不清空文本
  --inplace      直接覆盖原文件（会先备份）
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(
    sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import lk_core as core          # noqa: E402


def _fix_stdout():
    """打包为窗口程序后 sys.stdout 为 None：优先接管父控制台，否则写日志文件"""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace', buffering=1)
            sys.stderr = sys.stdout
            return
    except Exception:
        pass
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'LKTool_cli.log')
        f = open(path, 'w', encoding='utf-8')
        sys.stdout = f
        sys.stderr = f
    except Exception:
        class _Null:
            def write(self, *a):
                pass

            def flush(self):
                pass
        sys.stdout = sys.stderr = _Null()


def run_cli(argv):
    _fix_stdout()
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__)
        return 1
    src = args[0]
    delay_only = '--delay-only' in argv
    inplace = '--inplace' in argv
    if not os.path.isfile(src):
        print('找不到文件:', src)
        return 1

    data = core.read_file(src)
    s = core.scan(data)
    print('文件     :', src)
    print('大小     : %s   MD5: %s' % (core.human_size(s['size']), s['md5']))
    print('适配状态 : %s' % s['fit'])
    if not s['fit_ok']:
        print('镜像不匹配，已拦截，未做任何处理。')
        return 2
    h = s['header']
    print('头部     : %s  magic=0x%08X size=0x%X name=%r'
          % ('OK' if h['valid'] else '异常', h['magic'], h['size'], h['name']))
    print('警告文本 : %d 段' % len(s['warnings']))
    for off, t in s['warnings']:
        print('   @0x%06X  %s' % (off, t))
    if s['patch_a']:
        p = s['patch_a']
        print('补丁点   : @0x%06X (%s)  %s -> %s'
              % (p['offset'], p['arch'], p['old12'].hex().upper(), p['new12'].hex().upper()))
    else:
        print('补丁点   : 未找到' + ('（已打过补丁？）' if s['already_patched'] else ''))

    bak = core.backup_path(src)
    if not os.path.exists(bak):
        core.write_file(bak, data)
        print('备份     :', os.path.basename(bak))
    else:
        print('备份     : 已存在', os.path.basename(bak))

    new, log = core.apply(data, patch_a=True, patch_b=not delay_only)
    print('处理日志 :')
    for _lvl, txt in log:
        print('   ', txt)

    out = src if inplace else core.patched_path(src)
    core.write_file(out, new)
    print('新 MD5   :', core.md5(new))
    print('输出     :', out)

    v = core.verify(data, new)
    total = sum(e - b + 1 for b, e in v['diff_ranges'])
    print('校验     : 差异 %d 字节 / %d 段 · 内核参数%s · 警告残留 %d · 头部%s'
          % (total, len(v['diff_ranges']),
             '完好' if all(a == b for a, b in v['guards'].values()) else '异常',
             sum(v['residual'].values()),
             '未变' if v['header_ok'] else '异常'))
    print()
    print('提醒: lk 与 lk2 是 A/B 双槽，两个都要刷。')
    return 0


def main():
    argv = sys.argv[1:]
    if '--cli' in argv:
        return run_cli(argv)
    if argv and not argv[0].startswith('--') and os.path.isfile(argv[0]):
        return run_cli(argv)
    if argv and argv[0] in ('-h', '--help', '/?'):
        print(__doc__)
        return 0

    start_dir = ''
    if argv and os.path.isdir(argv[0]):
        start_dir = argv[0]
    import lk_gui
    return lk_gui.run(start_dir)


if __name__ == '__main__':
    sys.exit(main())
