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
- [x] **New Notification System** (sys-notif native C/Cairo/D-Bus daemon & sys-notif-center GTK3 history GUI replacing Dunst/Mako)
- [x] **Low battery warning** (Natively integrated into sys-notif via UPower D-Bus & direct sysfs, eliminated polling Bash daemon)
- [x] **Make Keyholder ignore sxhkd binds**
- [x] **Blueman sxhkd integration / keybindings** (Added Win + Alt + Shift + B scratchpad hotkey & sys-control --blueman integration)
- [x] **Add mod keys to mouse** (Mapped via ant-gm320, keyd, and ~/.Xmodmap: BTN_SIDE -> mod3/Hyper_L, BTN_EXTRA -> mod5/ISO_Level5_Shift, Button 6 -> Meta layer)
- [x] **Upgrade zsh** (Verified zsh 5.9.2 latest upstream Arch extra package, compdump cached & fast-compiled, plugins up-to-date)

## Fixes & Gaming
- [ ] **Fix tModLoader 4.5.6**

## Known Bugs & Backlog (Marked Down — Do Not Fix Yet)
- [ ] **Instagram "Sent a reel to your group" parsed as contact "you"**
  - **Details:** When multiple reels are shared to a group chat ("Sent a reel to your group"), the card title is parsed as `"you"` instead of the group name. The card displays the friend group's avatar (goldfish), but repeats `"• Sent a reel to your group"` without attributing the real sender or group chat name. (Flagged on 2026-11-02 per user request).
