# Gateway Autofix (macOS)

OpenClaw gateway 崩溃自动修复方案，基于 launchd watchdog + Claude Code。

## 架构

```
ai.openclaw.gateway (KeepAlive=true)
        │ 反复崩溃
        ▼
ai.openclaw.watchdog (每 60s 检查)
        │ 检测到 ≥5 次崩溃 / 120s
        ▼
  Claude Code 自动诊断修复 config
        │
        ▼
  launchctl kickstart 重启 gateway
```

## 文件

| 文件 | 用途 |
|------|------|
| `scripts/openclaw-watchdog.sh` | Watchdog 主脚本：健康检查 → 崩溃计数 → Claude Code 修复 |
| `scripts/safe-gateway-restart.sh` | 手动安全重启（带错误检测 + 自动修复） |
| `ai.openclaw.watchdog.plist` | LaunchAgent 配置 |

## 安装

```bash
# 1. 给脚本执行权限
chmod +x ~/work/openclaw-skills/gateway-autofix/scripts/*.sh

# 2. 复制 plist 到 LaunchAgents
cp ~/work/openclaw-skills/gateway-autofix/ai.openclaw.watchdog.plist ~/Library/LaunchAgents/

# 3. 加载 watchdog
launchctl load ~/Library/LaunchAgents/ai.openclaw.watchdog.plist

# 4. (可选) 启用 Telegram 通知：编辑 plist 取消注释 OPENCLAW_FIX_TELEGRAM_TARGET
```

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/ai.openclaw.watchdog.plist
rm ~/Library/LaunchAgents/ai.openclaw.watchdog.plist
```

## 配置 (环境变量)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCLAW_WATCHDOG_CRASH_THRESHOLD` | 5 | 触发修复的崩溃次数 |
| `OPENCLAW_WATCHDOG_WINDOW_SECS` | 120 | 崩溃计数时间窗口 |
| `OPENCLAW_WATCHDOG_MAX_FIX` | 2 | 最大修复尝试次数 |
| `OPENCLAW_WATCHDOG_CLAUDE_TIMEOUT` | 300 | Claude Code 超时(秒) |
| `OPENCLAW_WATCHDOG_COOLDOWN_SECS` | 600 | 两次修复之间最小间隔 |
| `OPENCLAW_FIX_TELEGRAM_TARGET` | (空) | Telegram 通知目标 |

## 手动安全重启

```bash
~/work/openclaw-skills/gateway-autofix/scripts/safe-gateway-restart.sh "upgrade"
```

## 日志

- Watchdog: `~/.openclaw/logs/watchdog.log`
- 状态: `~/.openclaw/logs/watchdog-state.json`
