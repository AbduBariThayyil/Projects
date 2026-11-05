#ifndef GRAB_H
#define GRAB_H

#include "sys-lock.h"

typedef struct {
    int x;
    int y;
    int width;
    int height;
    /* Primary screen center for UI elements */
    int center_x;
    int center_y;
} ScreenGeometry;

int grab_get_screen_geometry(Display *dpy, ScreenGeometry *geom);
Window grab_create_lock_window(Display *dpy, int screen, const ScreenGeometry *geom);
int grab_inputs(Display *dpy, Window win, int max_retries, int delay_us);
Cursor grab_create_blank_cursor(Display *dpy, Window win);
void grab_release(Display *dpy, Window win, Cursor cursor);

#endif /* GRAB_H */
