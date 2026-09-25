# -*- coding: utf-8 -*-
"""MTK LK 去警告工具 —— 图形界面（仅 GUI，依赖 tkinter）"""
from __future__ import annotations

import os
import sys
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import lk_core as core

APP_TITLE = 'MTK LK 去警告工具'
APP_VER = 'v1.0'
LOG_FILE = os.path.join(os.path.expanduser('~'), 'LKTool_error.log')

C_BG = '#F7F7F5'
C_PANEL = '#FFFFFF'
C_TEXT = '#2C2C2A'
C_MUTED = '#5F5E5A'
C_OK = '#0F6E56'
C_WARN = '#854F0B'
C_ERR = '#A32D2D'
C_HEAD = '#185FA5'


class App(tk.Tk):

    def __init__(self, start_dir: str = ''):
        super().__init__()
        self.title('%s  %s' % (APP_TITLE, APP_VER))
        self.geometry('900x720')
        self.minsize(780, 600)
        self.configure(bg=C_BG)

        self.files = []          # [(path, BooleanVar)]
        self.start_dir = start_dir

        self._setup_style()
        self._build_ui()
        self._autodetect()

    # ---------------- 外观 ----------------
    def _setup_style(self):
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        self.font_ui = next((f for f in ('Microsoft YaHei UI', 'Microsoft YaHei',
                                         'PingFang SC', 'Segoe UI') if f in fams),
                            'TkDefaultFont')
        self.font_mono = next((f for f in ('Consolas', 'Cascadia Mono', 'Courier New')
                               if f in fams), 'TkFixedFont')
        st = ttk.Style(self)
        try:
            st.theme_use('clam')
        except tk.TclError:
            pass
        st.configure('TFrame', background=C_BG)
        st.configure('TLabelframe', background=C_BG, bordercolor='#D3D1C7')
        st.configure('TLabelframe.Label', background=C_BG, foreground=C_MUTED,
                     font=(self.font_ui, 9))
        st.configure('TLabel', background=C_BG, foreground=C_TEXT, font=(self.font_ui, 9))
        st.configure('Hint.TLabel', background=C_BG, foreground=C_MUTED,
                     font=(self.font_ui, 8))
        st.configure('TCheckbutton', background=C_BG, foreground=C_TEXT,
                     font=(self.font_ui, 9))
        st.configure('TButton', font=(self.font_ui, 9), padding=(10, 5))
        st.configure('Accent.TButton', font=(self.font_ui, 9, 'bold'), padding=(12, 5))

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        # 1. 目录
        f1 = ttk.Labelframe(root, text=' 1. 选择固件目录 ', padding=10)
        f1.grid(row=0, column=0, sticky='ew')
        f1.columnconfigure(1, weight=1)
        ttk.Label(f1, text='目录').grid(row=0, column=0, sticky='w')
        self.dir_var = tk.StringVar()
        ent = ttk.Entry(f1, textvariable=self.dir_var, font=(self.font_ui, 9))
        ent.grid(row=0, column=1, sticky='ew', padx=8)
        ent.bind('<Return>', lambda e: self._detect())
        ttk.Button(f1, text='浏览…', command=self._browse).grid(row=0, column=2)
        ttk.Button(f1, text='重新检测', command=self._detect).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(f1, text='目录中同时存在 lk.img 与 lk2.img 时会一起处理 —— '
                           'A/B 双槽必须都刷，只刷一个警告可能依旧存在',
                  style='Hint.TLabel').grid(row=1, column=0, columnspan=4,
                                            sticky='w', pady=(6, 0))

        # 2. 文件
        f2 = ttk.Labelframe(root, text=' 2. 待处理镜像 ', padding=10)
        f2.grid(row=1, column=0, sticky='ew', pady=(10, 0))
        f2.columnconfigure(0, weight=1)
        self.file_box = ttk.Frame(f2)
        self.file_box.grid(row=0, column=0, sticky='ew')
        self.file_hint = ttk.Label(f2, text='尚未检测到镜像', style='Hint.TLabel')
        self.file_hint.grid(row=1, column=0, sticky='w', pady=(4, 0))

        # 3. 选项
        f3 = ttk.Labelframe(root, text=' 3. 补丁选项 ', padding=10)
        f3.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        self.var_a = tk.BooleanVar(value=True)
        self.var_b = tk.BooleanVar(value=True)
        self.var_bak = tk.BooleanVar(value=True)
        self.var_ver = tk.BooleanVar(value=True)
        self.var_inplace = tk.BooleanVar(value=False)
        tk.Checkbutton(f3, variable=self.var_a,
                        text='补丁 A（关键）：跳过橙/红状态警告与 5 秒启动延时',
                        bg=C_BG, fg=C_TEXT, activebackground=C_BG,
                        activeforeground=C_TEXT, highlightthickness=0,
                        bd=0, font=(self.font_ui, 9)
                        ).grid(row=0, column=0, sticky='w')
        tk.Checkbutton(f3, variable=self.var_b,
                        text='补丁 B：清空警告文本字符串（额外保险，不影响内核参数）',
                        bg=C_BG, fg=C_TEXT, activebackground=C_BG,
                        activeforeground=C_TEXT, highlightthickness=0,
                        bd=0, font=(self.font_ui, 9)
                        ).grid(row=1, column=0, sticky='w')
        sub = tk.Frame(f3, bg=C_BG)
        sub.grid(row=2, column=0, sticky='w', pady=(6, 0))
        tk.Checkbutton(sub, variable=self.var_bak,
                        text='自动备份原始镜像', bg=C_BG, fg=C_TEXT,
                        activebackground=C_BG, activeforeground=C_TEXT,
                        highlightthickness=0, bd=0, font=(self.font_ui, 9)
                        ).grid(row=0, column=0)
        tk.Checkbutton(sub, variable=self.var_ver,
                        text='生成校验报告', bg=C_BG, fg=C_TEXT,
                        activebackground=C_BG, activeforeground=C_TEXT,
                        highlightthickness=0, bd=0, font=(self.font_ui, 9)
                        ).grid(row=0, column=1, padx=16)
        tk.Checkbutton(sub, variable=self.var_inplace,
                        text='直接覆盖原文件（覆盖前强制备份）', bg=C_BG, fg=C_TEXT,
                        activebackground=C_BG, activeforeground=C_TEXT,
                        highlightthickness=0, bd=0, font=(self.font_ui, 9)
                        ).grid(row=0, column=2)

        # 4. 按钮
        f4 = ttk.Frame(root)
        f4.grid(row=3, column=0, sticky='ew', pady=(10, 6))
        ttk.Button(f4, text='扫描', command=self.do_scan).pack(side='left')
        ttk.Button(f4, text='打补丁', style='Accent.TButton',
                   command=self.do_patch).pack(side='left', padx=6)
        ttk.Button(f4, text='校验', command=self.do_verify).pack(side='left')
        ttk.Button(f4, text='还原备份', command=self.do_restore).pack(side='left', padx=6)
        ttk.Button(f4, text='打开目录', command=self.do_open_dir).pack(side='left')
        ttk.Button(f4, text='清空日志', command=self.clear_log).pack(side='right')

        # 5. 日志
        f5 = ttk.Labelframe(root, text=' 4. 输出 ', padding=6)
        f5.grid(row=4, column=0, sticky='nsew')
        f5.rowconfigure(0, weight=1)
        f5.columnconfigure(0, weight=1)
        self.txt = tk.Text(f5, wrap='none', font=(self.font_mono, 9),
                           bg=C_PANEL, fg=C_TEXT, relief='flat',
                           insertbackground=C_TEXT, padx=8, pady=6)
        self.txt.grid(row=0, column=0, sticky='nsew')
        ys = ttk.Scrollbar(f5, orient='vertical', command=self.txt.yview)
        ys.grid(row=0, column=1, sticky='ns')
        xs = ttk.Scrollbar(f5, orient='horizontal', command=self.txt.xview)
        xs.grid(row=1, column=0, sticky='ew')
        self.txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set, state='disabled')
        for tag, fg in (('ok', C_OK), ('warn', C_WARN), ('err', C_ERR),
                        ('head', C_HEAD), ('muted', C_MUTED)):
            self.txt.tag_configure(tag, foreground=fg,
                                   font=(self.font_mono, 9, 'bold' if tag == 'head' else 'normal'))

        self.status = tk.StringVar(value='就绪')
        ttk.Label(root, textvariable=self.status, style='Hint.TLabel'
                  ).grid(row=5, column=0, sticky='w', pady=(6, 0))

    # ---------------- 日志 ----------------
    def log(self, text='', tag=None):
        self.txt.configure(state='normal')
        self.txt.insert('end', text + '\n', tag or ())
        self.txt.see('end')
        self.txt.configure(state='disabled')

    def clear_log(self):
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        self.txt.configure(state='disabled')

    def rule(self, title=''):
        self.log('')
        self.log('─' * 72, 'muted')
        if title:
            self.log(title, 'head')

    # ---------------- 目录 ----------------
    def _browse(self):
        d = filedialog.askdirectory(title='选择固件目录（GeekFlashTool readback 目录）')
        if d:
            self.dir_var.set(d)
            self._detect()

    def _autodetect(self):
        cands = []
        if self.start_dir:
            cands.append(self.start_dir)
        cands += [os.path.dirname(os.path.abspath(sys.argv[0])), os.getcwd()]
        for c in cands:
            if c and core.detect_lk_files(c):
                self.dir_var.set(c)
                self._detect()
                return
        self.dir_var.set(cands[-1] if cands else '')
        self._detect()

    def _detect(self):
        folder = self.dir_var.get().strip().strip('"')
        for w in self.file_box.winfo_children():
            w.destroy()
        self.files.clear()
        if not os.path.isdir(folder):
            self.file_hint.configure(text='目录不存在')
            return
        found = core.detect_lk_files(folder)
        if not found:
            self.file_hint.configure(text='该目录下没有 lk.img / lk2.img')
            self.status.set('未检测到镜像')
            return
        for p in found:
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(self.file_box, variable=v,
                           text='%s   (%s)' % (os.path.basename(p),
                                               core.human_size(os.path.getsize(p))),
                           bg=C_BG, fg=C_TEXT, activebackground=C_BG,
                           activeforeground=C_TEXT, highlightthickness=0,
                           bd=0, font=(self.font_ui, 9)
                           ).pack(side='left', padx=(0, 20))
            self.files.append((p, v))
        same = ''
        if len(found) >= 2:
            try:
                d0 = core.read_file(found[0])
                if all(core.read_file(f) == d0 for f in found[1:]):
                    same = '  ·  内容完全相同（A/B 双槽，需同时刷入）'
            except OSError:
                pass
        self.file_hint.configure(text='检测到 %d 个镜像%s' % (len(found), same))
        self.status.set('检测到 %d 个镜像' % len(found))

    def _selected(self):
        return [p for p, v in self.files if v.get()]

    # ---------------- 扫描 ----------------
    def do_scan(self):
        paths = self._selected()
        if not paths:
            messagebox.showinfo(APP_TITLE, '请先选择目录并勾选要处理的镜像。')
            return
        self.clear_log()
        self.rule('扫描结果')
        for p in paths:
            try:
                data = core.read_file(p)
            except OSError as e:
                self.log('读取失败 %s: %s' % (p, e), 'err')
                continue
            s = core.scan(data)
            self.log('【%s】 %s   MD5 %s' % (os.path.basename(p),
                                            core.human_size(s['size']), s['md5']), 'head')
            self.log('  适配状态: %s' % s['fit'], 'ok' if s['fit_ok'] else 'err')
            h = s['header']
            if h['valid']:
                self.log('  头部: magic 0x%08X · ext 0x%08X · size 0x%X · name %r'
                         % (h['magic'], h['ext_magic'], h['size'], h['name']))
            else:
                self.log('  头部: 异常 —— %s' % h['reason'], 'err')
            self.log('  负载结束于 0x%06X，其后 %d 个非零字节'
                     % (s['payload_end'], s['tail_nonzero']))
            if s['warnings']:
                self.log('  警告文本 %d 段:' % len(s['warnings']))
                for off, t in s['warnings']:
                    self.log('    @0x%06X  %s' % (off, t), 'warn')
            else:
                self.log('  警告文本: 无（可能已清空）', 'ok')
            if s['patch_a']:
                pa = s['patch_a']
                self.log('  补丁点: @0x%06X   %s' % (pa['offset'], pa['arch']), 'ok')
                self.log('          %s  ->  %s'
                         % (pa['old12'].hex().upper(), pa['new12'].hex().upper()))
            else:
                if s['already_patched']:
                    self.log('  补丁点: 未找到（检测到已打补丁的痕迹）', 'ok')
                else:
                    self.log('  补丁点: 未找到 —— 镜像可能不匹配，请勿打补丁', 'err')
            for k, vals in s['params'].items():
                if vals:
                    self.log('  内核参数: %-28s %d 项（不会被改动）' % (k, len(vals)))
            self.log('')
        self.status.set('扫描完成，共 %d 个文件' % len(paths))

    # ---------------- 打补丁 ----------------
    def do_patch(self):
        paths = self._selected()
        if not paths:
            messagebox.showinfo(APP_TITLE, '请先选择目录并勾选要处理的镜像。')
            return
        if not self.var_a.get() and not self.var_b.get():
            messagebox.showwarning(APP_TITLE, '至少要勾选一个补丁。')
            return
        if self.var_inplace.get() and not messagebox.askyesno(
                APP_TITLE, '将直接覆盖原文件（会先自动备份）。\n\n确认继续？'):
            return

        self.clear_log()
        self.rule('开始打补丁')
        self.log('补丁A: %s    补丁B: %s    自动备份: %s    覆盖原文件: %s'
                 % ('开' if self.var_a.get() else '关',
                    '开' if self.var_b.get() else '关',
                    '开' if self.var_bak.get() else '关',
                    '是' if self.var_inplace.get() else '否'))
        outputs, problems, blocked = [], [], []

        for idx, p in enumerate(paths, 1):
            name = os.path.basename(p)
            self.log('')
            self.log('[%d/%d] %s' % (idx, len(paths), name), 'head')
            try:
                data = core.read_file(p)
            except OSError as e:
                self.log('  读取失败: %s' % e, 'err')
                problems.append(name)
                continue
            # 不匹配镜像直接拦截：不备份、不打补丁、不输出
            s = core.scan(data)
            if not s['fit_ok']:
                self.log('  已拦截: %s' % s['fit'], 'err')
                blocked.append('%s（%s）' % (name, s['fit']))
                continue
            self.log('  原始 MD5 : %s' % core.md5(data))

            bak = core.backup_path(p)
            if self.var_bak.get() and not os.path.exists(bak):
                try:
                    core.write_file(bak, data)
                    self.log('  已备份   : %s' % os.path.basename(bak), 'ok')
                except OSError as e:
                    self.log('  备份失败: %s' % e, 'err')
                    problems.append(name)
                    continue
            elif os.path.exists(bak):
                self.log('  备份已存在: %s' % os.path.basename(bak), 'muted')

            new, log = core.apply(data, patch_a=self.var_a.get(), patch_b=self.var_b.get())
            for lvl, txt in log:
                self.log('  ' + txt, lvl)

            if new == data:
                self.log('  文件内容未发生变化（可能已经是补丁状态）', 'warn')

            out = p if self.var_inplace.get() else core.patched_path(p)
            try:
                core.write_file(out, new)
            except OSError as e:
                self.log('  写出失败: %s' % e, 'err')
                problems.append(name)
                continue
            self.log('  新   MD5 : %s' % core.md5(new))
            self.log('  输出     : %s' % os.path.basename(out), 'ok')
            outputs.append(out)

            if self.var_ver.get():
                v = core.verify(data, new)
                total = sum(e - b + 1 for b, e in v['diff_ranges'])
                guard_ok = all(a == b for a, b in v['guards'].values())
                residual = sum(v['residual'].values())
                good = guard_ok and residual == 0 and v['header_ok']
                self.log('  校验: 差异 %d 字节 / %d 段 · 内核参数%s · 警告残留 %d · 头部%s'
                         % (total, len(v['diff_ranges']),
                            '完好' if guard_ok else '异常', residual,
                            '未变' if v['header_ok'] else '异常'),
                         'ok' if good else 'warn')
                if v.get('patch_a_offset') is not None:
                    for line in core.disasm_patch(new, v['patch_a_offset'], 3):
                        self.log('    ' + line, 'muted')
                    if not v['patch_a_ok']:
                        self.log('    !! 补丁点反汇编与预期不符', 'err')
                        problems.append(name)

        self.rule('完成')
        self.log('成功输出 %d 个文件' % len(outputs), 'ok' if not problems else 'warn')
        if blocked:
            self.log('已拦截 %d 个不匹配镜像（未做任何处理）:' % len(blocked), 'err')
            for b in blocked:
                self.log('  - ' + b, 'err')
        if problems:
            self.log('以下文件有问题: %s' % ', '.join(problems), 'err')
        self.log('')
        self.log('刷入提醒：lk 与 lk2 是 A/B 双槽，两个都要刷；', 'warn')
        self.log('          只刷一个的话设备可能从另一个槽启动，警告依旧存在。', 'warn')
        self.status.set('补丁完成')

        msg = '补丁完成，输出 %d 个文件。' % len(outputs)
        if blocked:
            msg += '\n\n已拦截 %d 个不匹配镜像（未做任何处理）：\n  %s' \
                   % (len(blocked), '\n  '.join(blocked))
        if problems:
            msg += '\n\n注意：%s 处理异常，请看日志。' % ', '.join(problems)
        msg += '\n\n刷入提醒：lk 与 lk2 都要刷，只刷一个警告可能依旧存在。'
        messagebox.showinfo(APP_TITLE, msg)

    # ---------------- 校验 ----------------
    def do_verify(self):
        paths = self._selected()
        if not paths:
            messagebox.showinfo(APP_TITLE, '请先选择目录并勾选要处理的镜像。')
            return
        self.clear_log()
        self.rule('校验（原始备份 vs 当前输出）')
        for p in paths:
            bak = core.backup_path(p)
            if not os.path.isfile(bak):
                # 区分"不匹配被拦截"与"从未处理"，给出完整说明
                blocked_fit = ''
                try:
                    s = core.scan(core.read_file(p))
                    if not s['fit_ok']:
                        blocked_fit = s['fit']
                except OSError:
                    pass
                if blocked_fit:
                    self.log('%s: 不匹配镜像，已拦截未处理 —— %s（因此无备份、无补丁输出可对比）'
                             % (os.path.basename(p), blocked_fit), 'warn')
                else:
                    self.log('%s: 没有备份 %s，无法对比'
                             % (os.path.basename(p), os.path.basename(bak)), 'warn')
                continue
            cand = [c for c in (core.patched_path(p), p) if os.path.isfile(c)]
            if not cand:
                self.log('%s: 没有可校验的输出文件' % os.path.basename(p), 'warn')
                continue
            out = cand[0]
            o, n = core.read_file(bak), core.read_file(out)
            v = core.verify(o, n)
            self.log('【%s】 vs %s' % (os.path.basename(out), os.path.basename(bak)), 'head')
            self.log('  大小一致 : %s' % ('是' if v['size_same'] else '否'),
                     'ok' if v['size_same'] else 'err')
            total = sum(e - b + 1 for b, e in v['diff_ranges'])
            self.log('  差异     : %d 字节 / %d 段' % (total, len(v['diff_ranges'])))
            for b, e in v['diff_ranges']:
                self.log('     0x%06X-0x%06X  (%d 字节)' % (b, e, e - b + 1), 'muted')
            for k, (a, c) in v['guards'].items():
                self.log('  内核参数 %-30s %d -> %d  %s'
                         % (k, a, c, 'OK' if a == c else '异常'),
                         'ok' if a == c else 'err')
            res = sum(v['residual'].values())
            self.log('  警告文本残留: %d  %s' % (res, 'OK' if res == 0 else '仍有残留'),
                     'ok' if res == 0 else 'warn')
            self.log('  头部未变 : %s' % ('是' if v['header_ok'] else '否'),
                     'ok' if v['header_ok'] else 'err')
            self.log('  MD5 原始 : %s' % v['md5_orig'])
            self.log('  MD5 补丁 : %s' % v['md5_new'])
            if v.get('patch_a_offset') is not None:
                for line in core.disasm_patch(n, v['patch_a_offset'], 3):
                    self.log('    ' + line, 'muted')
            self.log('')
        self.status.set('校验完成')

    # ---------------- 还原 ----------------
    def do_restore(self):
        paths = self._selected()
        if not paths:
            messagebox.showinfo(APP_TITLE, '请先选择目录并勾选要处理的镜像。')
            return
        todo = [(p, core.backup_path(p)) for p in paths
                if os.path.isfile(core.backup_path(p))]
        if not todo:
            messagebox.showinfo(APP_TITLE, '没有找到备份文件，无需还原。')
            return
        names = '\n'.join('  ' + os.path.basename(p) for p, _ in todo)
        if not messagebox.askyesno(APP_TITLE, '将用备份覆盖以下文件：\n\n%s\n\n确认还原？' % names):
            return
        self.clear_log()
        self.rule('还原备份')
        for p, bak in todo:
            try:
                core.write_file(p, core.read_file(bak))
                self.log('已还原 %s  <-  %s'
                         % (os.path.basename(p), os.path.basename(bak)), 'ok')
            except OSError as e:
                self.log('还原失败 %s: %s' % (os.path.basename(p), e), 'err')
        self.status.set('还原完成')

    def do_open_dir(self):
        folder = self.dir_var.get().strip().strip('"')
        if not os.path.isdir(folder):
            messagebox.showinfo(APP_TITLE, '目录不存在。')
            return
        try:
            os.startfile(folder)          # noqa: S606
        except Exception as e:
            messagebox.showerror(APP_TITLE, '打开目录失败：%s' % e)


def run(start_dir: str = '') -> int:
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    def on_error(exc, val, tb):
        msg = ''.join(traceback.format_exception(exc, val, tb))
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except OSError:
            pass
        try:
            messagebox.showerror(APP_TITLE, '发生错误：\n%s\n\n详情见 %s' % (val, LOG_FILE))
        except Exception:
            pass

    app = App(start_dir)
    app.report_callback_exception = on_error
    app.mainloop()
    return 0
