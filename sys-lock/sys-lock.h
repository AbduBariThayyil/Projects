#ifndef SYS_LOCK_H
#define SYS_LOCK_H

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <time.h>
#include <math.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/poll.h>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <X11/XF86keysym.h>
#include <X11/extensions/Xinerama.h>
#include <X11/extensions/XShm.h>
#include <sys/ipc.h>
#include <sys/shm.h>

#include <cairo/cairo.h>
#include <cairo/cairo-xlib.h>
#include <pango/pangocairo.h>
#include <gdk-pixbuf/gdk-pixbuf.h>

#define SYS_LOCK_VERSION "1.0.0"

/* IPC Message codes between worker threads and main event loop */
typedef enum {
    MSG_NONE = 0,
    MSG_PAM_SUCCESS,
    MSG_PAM_FAILURE,
    MSG_FPRINT_ACTIVE,
    MSG_FPRINT_SUCCESS,
    MSG_FPRINT_FAILURE,
    MSG_FPRINT_SWIPE_SHORT,
    MSG_FPRINT_NOT_CENTERED,
    MSG_FPRINT_RETRY
} IpcMessageCode;

typedef struct {
    IpcMessageCode code;
    char text[128];
} IpcMessage;

/* UI State */
typedef enum {
    UI_STATE_IDLE = 0,
    UI_STATE_TYPING,
    UI_STATE_VERIFYING,
    UI_STATE_AUTH_FAILED,
    UI_STATE_FPRINT_MATCH,
    UI_STATE_FPRINT_WARNING
} UiState;

/* Dusk Horizon Color Palette (matched to wallpaper2.jpg) */
#define COLOR_BASE_R      (24.0  / 255.0)
#define COLOR_BASE_G      (26.0  / 255.0)
#define COLOR_BASE_B      (44.0  / 255.0)

#define COLOR_MANTLE_R    (19.0  / 255.0)
#define COLOR_MANTLE_G    (21.0  / 255.0)
#define COLOR_MANTLE_B    (35.0  / 255.0)

#define COLOR_CRUST_R     (14.0  / 255.0)
#define COLOR_CRUST_G     (16.0  / 255.0)
#define COLOR_CRUST_B     (28.0  / 255.0)

#define COLOR_TEXT_R      (243.0 / 255.0)
#define COLOR_TEXT_G      (230.0 / 255.0)
#define COLOR_TEXT_B      (220.0 / 255.0)

#define COLOR_SUBTEXT_R   (184.0 / 255.0)
#define COLOR_SUBTEXT_G   (173.0 / 255.0)
#define COLOR_SUBTEXT_B   (196.0 / 255.0)

#define COLOR_MAUVE_R     (247.0 / 255.0)
#define COLOR_MAUVE_G     (178.0 / 255.0)
#define COLOR_MAUVE_B     (119.0 / 255.0)

#define COLOR_LAVENDER_R  (200.0 / 255.0)
#define COLOR_LAVENDER_G  (132.0 / 255.0)
#define COLOR_LAVENDER_B  (166.0 / 255.0)

#define COLOR_YELLOW_R    (249.0 / 255.0)
#define COLOR_YELLOW_G    (214.0 / 255.0)
#define COLOR_YELLOW_B    (139.0 / 255.0)

#define COLOR_RED_R       (235.0 / 255.0)
#define COLOR_RED_G       (111.0 / 255.0)
#define COLOR_RED_B       (124.0 / 255.0)

#define COLOR_GREEN_R     (141.0 / 255.0)
#define COLOR_GREEN_G     (211.0 / 255.0)
#define COLOR_GREEN_B     (158.0 / 255.0)

#define COLOR_PEACH_R     (247.0 / 255.0)
#define COLOR_PEACH_G     (178.0 / 255.0)
#define COLOR_PEACH_B     (119.0 / 255.0)

/* Maximum lengths */
#define MAX_PASSWORD_LEN 256
#define MAX_PATH_LEN     512

#endif /* SYS_LOCK_H */
