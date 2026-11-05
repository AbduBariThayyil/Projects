#include "grab.h"

int grab_get_screen_geometry(Display *dpy, ScreenGeometry *geom) {
    if (!dpy || !geom) return -1;

    memset(geom, 0, sizeof(ScreenGeometry));
    int screen = DefaultScreen(dpy);

    if (XineramaIsActive(dpy)) {
        int n_screens = 0;
        XineramaScreenInfo *info = XineramaQueryScreens(dpy, &n_screens);
        if (info && n_screens > 0) {
            int min_x = info[0].x_org;
            int min_y = info[0].y_org;
            int max_x = info[0].x_org + info[0].width;
            int max_y = info[0].y_org + info[0].height;

            for (int i = 1; i < n_screens; i++) {
                if (info[i].x_org < min_x) min_x = info[i].x_org;
                if (info[i].y_org < min_y) min_y = info[i].y_org;
                if (info[i].x_org + info[i].width > max_x)
                    max_x = info[i].x_org + info[i].width;
                if (info[i].y_org + info[i].height > max_y)
                    max_y = info[i].y_org + info[i].height;
            }

            geom->x = min_x;
            geom->y = min_y;
            geom->width = max_x - min_x;
            geom->height = max_y - min_y;
            /* Use primary / first monitor center */
            geom->center_x = info[0].x_org + (info[0].width / 2);
            geom->center_y = info[0].y_org + (info[0].height / 2);

            XFree(info);
            return 0;
        }
    }

    /* Fallback to DefaultScreen */
    geom->x = 0;
    geom->y = 0;
    geom->width = DisplayWidth(dpy, screen);
    geom->height = DisplayHeight(dpy, screen);
    geom->center_x = geom->width / 2;
    geom->center_y = geom->height / 2;
    return 0;
}

Window grab_create_lock_window(Display *dpy, int screen, const ScreenGeometry *geom) {
    if (!dpy || !geom) return None;

    Window root = RootWindow(dpy, screen);

    XSetWindowAttributes attr;
    memset(&attr, 0, sizeof(attr));
    attr.override_redirect = True;
    attr.background_pixel = BlackPixel(dpy, screen);
    attr.event_mask = ExposureMask | KeyPressMask | KeyReleaseMask |
                      ButtonPressMask | ButtonReleaseMask | PointerMotionMask |
                      StructureNotifyMask | VisibilityChangeMask;

    Window win = XCreateWindow(
        dpy, root,
        geom->x, geom->y,
        geom->width, geom->height,
        0, CopyFromParent, InputOutput, CopyFromParent,
        CWOverrideRedirect | CWBackPixel | CWEventMask,
        &attr
    );

    if (win == None) return None;

    /* Set fullscreen atoms for standard compliance */
    Atom wm_state = XInternAtom(dpy, "_NET_WM_STATE", False);
    Atom wm_fullscreen = XInternAtom(dpy, "_NET_WM_STATE_FULLSCREEN", False);
    if (wm_state != None && wm_fullscreen != None) {
        XChangeProperty(dpy, win, wm_state, XA_ATOM, 32, PropModeReplace,
                        (unsigned char *)&wm_fullscreen, 1);
    }

    XMapRaised(dpy, win);
    XSync(dpy, False);
    return win;
}

int grab_inputs(Display *dpy, Window win, int max_retries, int delay_us) {
    if (!dpy || win == None) return -1;

    for (int i = 0; i < max_retries; i++) {
        int kgrab = XGrabKeyboard(dpy, win, True, GrabModeAsync, GrabModeAsync, CurrentTime);
        int pgrab = XGrabPointer(dpy, win, True,
                                ButtonPressMask | ButtonReleaseMask | PointerMotionMask,
                                GrabModeAsync, GrabModeAsync, None, None, CurrentTime);

        if (kgrab == GrabSuccess && pgrab == GrabSuccess) {
            return 0;
        }

        if (kgrab == GrabSuccess) XUngrabKeyboard(dpy, CurrentTime);
        if (pgrab == GrabSuccess) XUngrabPointer(dpy, CurrentTime);

        usleep(delay_us);
    }

    return -1;
}

Cursor grab_create_blank_cursor(Display *dpy, Window win) {
    if (!dpy || win == None) return None;

    char data[1] = {0};
    Pixmap blank = XCreateBitmapFromData(dpy, win, data, 1, 1);
    if (blank == None) return None;

    XColor dummy;
    memset(&dummy, 0, sizeof(dummy));
    Cursor cursor = XCreatePixmapCursor(dpy, blank, blank, &dummy, &dummy, 0, 0);
    XFreePixmap(dpy, blank);
    return cursor;
}

void grab_release(Display *dpy, Window win, Cursor cursor) {
    if (!dpy) return;
    XUngrabKeyboard(dpy, CurrentTime);
    XUngrabPointer(dpy, CurrentTime);
    if (cursor != None) {
        XFreeCursor(dpy, cursor);
    }
    if (win != None) {
        XDestroyWindow(dpy, win);
    }
    XSync(dpy, False);
}
