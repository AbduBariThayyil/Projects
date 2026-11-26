#ifndef SYS_INPUT_X11_H
#define SYS_INPUT_X11_H

#include <stdbool.h>

typedef struct SysInputX11 SysInputX11;
typedef void (*SysInputGameCtxCb)(void *ctx, bool in_game);

SysInputX11 *sys_input_x11_create(SysInputGameCtxCb cb, void *ctx);
void sys_input_x11_destroy(SysInputX11 *x11);
int sys_input_x11_fd(const SysInputX11 *x11);
bool sys_input_x11_connect(SysInputX11 *x11);
void sys_input_x11_process(SysInputX11 *x11);

#endif
