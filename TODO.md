# Todo List

## Development & Audio
- [ ] **Learn Python again**
  - Review fundamentals (syntax, data structures, OOP)
  - Practice standard library and modern Python features (asyncio, type hints)
  - Work on hands-on mini-projects
- [ ] **Make music player**
  - Design playback architecture (play, pause, skip, volume controls)
  - Build UI/CLI interface
  - Support common audio formats (MP3, WAV, etc.)
- [ ] **Web player**
  - Build frontend player interface (HTML5 Audio / Web Audio API)
  - Implement playlist management and media controls
  - Connect to backend streaming/media server
- [ ] **Host music web server on Android tablet via Tailscale**
  - Set up server environment on Android tablet (e.g., Termux)
  - Configure Tailscale for wireless tunneling and secure remote access
  - Stream and control audio wirelessly across devices

## System & Window Manager Configs
- [ ] **New Notification System**
- [x] **Low battery warning** (Natively integrated into sys-notif via UPower D-Bus & direct sysfs, eliminated polling Bash daemon)
- [ ] **Make Keyholder ignore sxhkd binds**
- [ ] **Blueman sxhkd integration / keybindings**
- [ ] **Add mod keys to mouse**
- [ ] **Upgrade zsh**

## Fixes & Gaming
- [ ] **Fix tModLoader 4.5.6**

## Known Bugs & Backlog (Marked Down — Do Not Fix Yet)
- [ ] **Instagram "Sent a reel to your group" parsed as contact "you"**
  - **Details:** When multiple reels are shared to a group chat ("Sent a reel to your group"), the card title is parsed as `"you"` instead of the group name. The card displays the friend group's avatar (goldfish), but repeats `"• Sent a reel to your group"` without attributing the real sender or group chat name. (Flagged on 2026-11-02 per user request).
