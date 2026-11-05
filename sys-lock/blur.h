#ifndef BLUR_H
#define BLUR_H

#include "sys-lock.h"

/*
 * Capture root window using XShm / XGetImage, apply 4x downsampling
 * and an ultra-fast in-memory 3-pass box blur in C (< 20ms execution on CPU),
 * and apply a dark Catppuccin Mocha tint overlay (rgba(30, 30, 46, 0.70)).
 * Returns a full-screen cairo image surface ready for double buffering.
 */
cairo_surface_t *capture_and_blur_root(Display *dpy, int screen, int width, int height);

/* Standalone box blur algorithm for testing */
void blur_apply_3pass_box(uint32_t *src_dst, uint32_t *tmp, int w, int h, int radius);

#endif /* BLUR_H */
