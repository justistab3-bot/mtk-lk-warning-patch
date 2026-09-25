# -*- coding: utf-8 -*-
"""
MTK LK 去警告补丁 —— 核心库（无 GUI 依赖，可单独调用）

参考: https://www.hovatek.com/forum/thread-31664.html
"""
from __future__ import annotations

import hashlib
import os
import struct
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
MAGIC = 0x58881688
EXT_MAGIC = 0x58891689
PART_SIZE = 0x100000                      # lk 分区大小 1MB

# 5 秒延时 / 警告分发函数的特征码
SIG_PRE_A10 = bytes.fromhex('7B441B681B68012B')      # Android 10 以下
SIG_A10PLUS = bytes.fromhex('7B441B681B68022B')      # Android 10 及以上
SIGS = [('Android 10 以下', SIG_PRE_A10),
        ('Android 10 及以上', SIG_A10PLUS)]

PATCH_A_LEAD = bytes.fromhex('08B5002008BD')         # push {r3,lr}; movs r0,#0; pop {r3,pc}
PREFIX = bytes.fromhex('08B5')                       # 命中处前 4 字节必须是 08B5****

# 警告文本（补丁 B 要清空的内容）
WARN_KEYS = [
    b'Orange State',
    b'Red State',
    b'Your device will boot in 5 seconds',
    b"Your device has been unlocked and can't be trusted",
    b'Your device has failed verification and may not',
    b'work properly',
]

# 内核启动参数 —— 绝对不能动
GUARD_KEYS = [
    b'androidboot.verifiedbootstate',
    b'androidboot.veritymode',
    b'androidboot.atm',
]


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def find_all(data: bytes, needle: bytes) -> List[int]:
    out, s = [], 0
    while True:
        i = data.find(needle, s)
        if i < 0:
            return out
        out.append(i)
        s = i + 1


def cstr(data: bytes, off: int, limit: int = 96) -> str:
    if not (0 <= off < len(data)):
        return ''
    e = data.find(b'\0', off)
    if e < 0 or e - off > limit:
        e = off + limit
    return data[off:e].decode('utf-8', 'replace').replace('\n', ' ').strip()


def diff_ranges(a: bytes, b: bytes) -> List[Tuple[int, int]]:
    """返回 [a, b] 中所有不同的连续区间 (start, end_inclusive)"""
    out, s = [], None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if s is None:
                s = i
        elif s is not None:
            out.append((s, i - 1))
            s = None
    if s is not None:
        out.append((s, min(len(a), len(b)) - 1))
    return out


# ----------------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------------
def parse_header(data: bytes) -> Dict:
    if len(data) < 0x38:
        return {'valid': False, 'reason': '文件太小'}
    magic, size = struct.unpack_from('<II', data, 0)
    ext = struct.unpack_from('<I', data, 0x30)[0]
    name = data[8:20].split(b'\0')[0].decode('latin1', 'replace')
    return {
        'valid': magic == MAGIC,
        'magic': magic,
        'size': size,
        'ext_magic': ext,
        'name': name,
        'reason': '' if magic == MAGIC else 'magic 不匹配（可能不是 MTK LK 镜像）',
    }


def find_patch_a(data: bytes) -> Optional[Dict]:
    """定位警告分发函数（教程方法二的特征码）"""
    for arch, sig in SIGS:
        for sig_off in find_all(data, sig):
            pre = data[sig_off - 4:sig_off]
            if len(pre) == 4 and pre[:2] == PREFIX:
                off = sig_off - 4
                old12 = bytes(data[off:off + 12])
                if len(old12) < 12:
                    continue
                new12 = PATCH_A_LEAD + old12[6:12]
                return {
                    'offset': off,
                    'sig_offset': sig_off,
                    'arch': arch,
                    'old12': old12,
                    'new12': new12,
                }
    return None


def find_warnings(data: bytes) -> List[Tuple[int, int, str]]:
    """返回需要清空的文本区间 [(start, end_exclusive, 文本)]"""
    found = []
    for k in WARN_KEYS:
        for i in find_all(data, k):
            found.append((i, len(k)))
    if not found:
        return []
    found.sort()
    guard = data.find(GUARD_KEYS[0])
    out = []
    for n, (s, klen) in enumerate(found):
        e = found[n + 1][0] if n + 1 < len(found) else s + klen + 1
        if guard > 0:
            e = min(e, guard)
        if e > s:
            out.append((s, e, cstr(data, s)))
    return out


def scan(data: bytes) -> Dict:
    """完整扫描，供界面展示"""
    hdr = parse_header(data)
    warns = [(s, cstr(data, s)) for s, _e, _t in find_warnings(data)]
    p = find_patch_a(data)
    already = bool(find_all(data, PATCH_A_LEAD)) and p is None
    params = {}
    for g in GUARD_KEYS:
        vals = []
        for i in find_all(data, g):
            vals.append(cstr(data, i))
        params[g.decode()] = vals
    # 尾部填充
    tail_off = 0x200 + hdr.get('size', 0)
    tail = data[tail_off:] if 0 < tail_off < len(data) else b''
    tail_nonzero = sum(1 for b in tail if b != 0)
    # 适配结论：一眼判断该镜像能否打补丁
    if not hdr['valid']:
        if not any(data):
            fit, fit_ok = '不匹配（全零文件，疑似空占位槽位，无需打补丁）', False
        else:
            fit, fit_ok = '不匹配（非 MTK LK 镜像：magic 错误）', False
    elif p:
        fit, fit_ok = '适配（%s平台，可打补丁）' % p['arch'], True
    elif already:
        fit, fit_ok = '已打过补丁（无原始特征码）', True
    elif not warns:
        fit, fit_ok = '不匹配（无特征码且无警告文本，可能是空占位文件）', False
    else:
        fit, fit_ok = '不匹配（特征码未找到，该镜像不支持去延时）', False
    return {
        'size': len(data),
        'md5': md5(data),
        'header': hdr,
        'warnings': warns,
        'patch_a': p,
        'already_patched': already,
        'params': params,
        'payload_end': tail_off,
        'tail_nonzero': tail_nonzero,
        'fit': fit,
        'fit_ok': fit_ok,
    }


# ----------------------------------------------------------------------------
# 打补丁
# ----------------------------------------------------------------------------
def apply(data: bytes, patch_a: bool = True, patch_b: bool = True):
    """返回 (新数据, 日志列表[(级别, 文本)])"""
    d = bytearray(data)
    log: List[Tuple[str, str]] = []

    if patch_a:
        p = find_patch_a(d)
        if p is None:
            if find_all(d, PATCH_A_LEAD):
                log.append(('warn', '补丁A：特征码未找到，但检测到已打补丁的痕迹，跳过'))
            else:
                log.append(('warn', '补丁A：未找到 5 秒延时特征码，镜像可能不匹配，跳过'))
        else:
            d[p['offset']:p['offset'] + 12] = p['new12']
            log.append(('ok', '补丁A @0x%06X  %s -> %s  (%s)'
                        % (p['offset'], p['old12'].hex().upper(),
                           p['new12'].hex().upper(), p['arch'])))
            log.append(('info', '       该函数是橙/红状态警告分发器，改为 return 0 后'
                                '警告文本与 5 秒等待一并跳过'))
    else:
        log.append(('info', '补丁A：未启用'))

    if patch_b:
        ws = find_warnings(d)
        if not ws:
            log.append(('warn', '补丁B：未找到警告文本（可能已清空）'))
        for s, e, t in ws:
            d[s:e] = b'\x00' * (e - s)
            log.append(('ok', '补丁B @0x%06X-0x%06X (%2d 字节) 清空: %s'
                        % (s, e - 1, e - s, t[:46])))
        log.append(('info', '       内核参数 androidboot.* 未改动'))
    else:
        log.append(('info', '补丁B：未启用'))

    return bytes(d), log


# ----------------------------------------------------------------------------
# 校验
# ----------------------------------------------------------------------------
def verify(orig: bytes, new: bytes) -> Dict:
    r = {
        'size_same': len(orig) == len(new),
        'diff_ranges': diff_ranges(orig, new),
        'header_ok': orig[:0x50] == new[:0x50],
        'guards': {},
        'residual': {},
        'patch_a_ok': False,
        'md5_orig': md5(orig),
        'md5_new': md5(new),
    }
    for g in GUARD_KEYS:
        r['guards'][g.decode()] = (orig.count(g), new.count(g))
    for k in WARN_KEYS:
        r['residual'][k.decode()] = new.count(k)

    # 反汇编验证（capstone 可选）
    p = find_patch_a(orig)
    if p:
        seg = new[p['offset']:p['offset'] + 6]
        r['patch_a_ok'] = seg == PATCH_A_LEAD
        r['patch_a_offset'] = p['offset']
    return r


def disasm_patch(data: bytes, offset: int, count: int = 5) -> List[str]:
    """尝试反汇编补丁点，需要 capstone；不可用时返回空列表"""
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    except ImportError:
        return []
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    out = []
    p = offset
    end = offset + 0x20
    while p < end and len(out) < count:
        got = False
        for ins in md.disasm(data[p:end], p):
            out.append('%06X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
            p = ins.address + ins.size
            got = True
            break
        if not got:
            p += 2
    return out


# ----------------------------------------------------------------------------
# 文件辅助
# ----------------------------------------------------------------------------
LK_NAMES = ['lk.img', 'lk2.img', 'lk.bin', 'lk2.bin',
            'lk_a.img', 'lk_b.img', 'lk_a.bin', 'lk_b.bin']


def detect_lk_files(folder: str) -> List[str]:
    """在目录中找出 lk / lk2 镜像（含 A/B 双槽）"""
    if not os.path.isdir(folder):
        return []
    out = []
    for n in LK_NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            out.append(p)
    if out:
        return out
    # 退路：按前缀匹配
    for n in sorted(os.listdir(folder)):
        low = n.lower()
        if low.startswith('lk') and low.endswith(('.img', '.bin')):
            out.append(os.path.join(folder, n))
    return out


def backup_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    return base + '_original_backup' + ext


def patched_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    return base + '_patched' + ext


def read_file(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()


def write_file(path: str, data: bytes) -> None:
    with open(path, 'wb') as f:
        f.write(data)


def human_size(n: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0
    return str(n)
