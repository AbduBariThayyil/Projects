#include "blur.h"

static void box_blur_h(const uint32_t *src, uint32_t *dst, int w, int h, int r) {
    float inv = 1.0f / (float)(r + r + 1);
    for (int y = 0; y < h; y++) {
        int yi = y * w;
        const uint32_t *line_src = src + yi;
        uint32_t *line_dst = dst + yi;

        int r_val = 0, g_val = 0, b_val = 0;
        for (int x = -r; x <= r; x++) {
            int cx = (x < 0) ? 0 : ((x >= w) ? (w - 1) : x);
            uint32_t p = line_src[cx];
            r_val += (p >> 16) & 0xff;
            g_val += (p >> 8) & 0xff;
            b_val += p & 0xff;
        }

        for (int x = 0; x < w; x++) {
            uint8_t ro = (uint8_t)(r_val * inv);
            uint8_t go = (uint8_t)(g_val * inv);
            uint8_t bo = (uint8_t)(b_val * inv);
            line_dst[x] = 0xff000000 | ((uint32_t)ro << 16) | ((uint32_t)go << 8) | bo;

            int left = x - r;
            int right = x + r + 1;
            int cleft = (left < 0) ? 0 : left;
            int cright = (right >= w) ? (w - 1) : right;

            uint32_t pl = line_src[cleft];
            uint32_t pr = line_src[cright];

            r_val += ((pr >> 16) & 0xff) - ((pl >> 16) & 0xff);
            g_val += ((pr >> 8) & 0xff) - ((pl >> 8) & 0xff);
            b_val += (pr & 0xff) - (pl & 0xff);
        }
    }
}

static void box_blur_v(const uint32_t *src, uint32_t *dst, int w, int h, int r) {
    float inv = 1.0f / (float)(r + r + 1);
    for (int x = 0; x < w; x++) {
        int r_val = 0, g_val = 0, b_val = 0;
        for (int y = -r; y <= r; y++) {
            int cy = (y < 0) ? 0 : ((y >= h) ? (h - 1) : y);
            uint32_t p = src[cy * w + x];
            r_val += (p >> 16) & 0xff;
            g_val += (p >> 8) & 0xff;
            b_val += p & 0xff;
        }

        for (int y = 0; y < h; y++) {
            uint8_t ro = (uint8_t)(r_val * inv);
            uint8_t go = (uint8_t)(g_val * inv);
            uint8_t bo = (uint8_t)(b_val * inv);
            dst[y * w + x] = 0xff000000 | ((uint32_t)ro << 16) | ((uint32_t)go << 8) | bo;

            int top = y - r;
            int bot = y + r + 1;
            int ctop = (top < 0) ? 0 : top;
            int cbot = (bot >= h) ? (h - 1) : bot;

            uint32_t pt = src[ctop * w + x];
            uint32_t pb = src[cbot * w + x];

            r_val += ((pb >> 16) & 0xff) - ((pt >> 16) & 0xff);
            g_val += ((pb >> 8) & 0xff) - ((pt >> 8) & 0xff);
            b_val += (pb & 0xff) - (pt & 0xff);
        }
    }
}

void blur_apply_3pass_box(uint32_t *src_dst, uint32_t *tmp, int w, int h, int radius) {
    if (!src_dst || !tmp || w <= 0 || h <= 0 || radius <= 0) return;
    for (int p = 0; p < 3; p++) {
        box_blur_h(src_dst, tmp, w, h, radius);
        box_blur_v(tmp, src_dst, w, h, radius);
    }
}

static XImage *capture_root(Display *dpy, int screen, int width, int height,
                            XShmSegmentInfo *shminfo, bool *used_shm) {
    Window root = RootWindow(dpy, screen);
    *used_shm = false;

    if (XShmQueryExtension(dpy)) {
        XImage *img = XShmCreateImage(
            dpy, DefaultVisual(dpy, screen), DefaultDepth(dpy, screen),
            ZPixmap, NULL, shminfo, width, height
        );
        if (img) {
            shminfo->shmid = shmget(IPC_PRIVATE, img->bytes_per_line * img->height, IPC_CREAT | 0777);
            if (shminfo->shmid >= 0) {
                shminfo->shmaddr = img->data = (char *)shmat(shminfo->shmid, 0, 0);
                if (shminfo->shmaddr != (char *)-1) {
                    shminfo->readOnly = False;
                    if (XShmAttach(dpy, shminfo)) {
                        XSync(dpy, False);
                        if (XShmGetImage(dpy, root, img, 0, 0, AllPlanes)) {
                            *used_shm = true;
                            return img;
                        }
                        XShmDetach(dpy, shminfo);
                    }
                    shmdt(shminfo->shmaddr);
                }
                shmctl(shminfo->shmid, IPC_RMID, 0);
            }
            XDestroyImage(img);
        }
    }

    /* Fallback to standard XGetImage */
    return XGetImage(dpy, root, 0, 0, width, height, AllPlanes, ZPixmap);
}

static void release_captured_root(Display *dpy, XImage *img,
                                  XShmSegmentInfo *shminfo, bool used_shm) {
    if (!img) return;
    if (used_shm) {
        XShmDetach(dpy, shminfo);
        XDestroyImage(img);
        shmdt(shminfo->shmaddr);
        shmctl(shminfo->shmid, IPC_RMID, 0);
    } else {
        XDestroyImage(img);
    }
}

cairo_surface_t *capture_and_blur_root(Display *dpy, int screen, int width, int height) {
    if (!dpy || width <= 0 || height <= 0) return NULL;

    XShmSegmentInfo shminfo;
    memset(&shminfo, 0, sizeof(shminfo));
    bool used_shm = false;

    XImage *img = capture_root(dpy, screen, width, height, &shminfo, &used_shm);
    if (!img) return NULL;

    /* 4x downsampling */
    const int scale = 4;
    int sw = width / scale;
    int sh = height / scale;
    if (sw < 1) sw = 1;
    if (sh < 1) sh = 1;

    uint32_t *buf1 = malloc(sw * sh * sizeof(uint32_t));
    uint32_t *buf2 = malloc(sw * sh * sizeof(uint32_t));
    if (!buf1 || !buf2) {
        free(buf1);
        free(buf2);
        release_captured_root(dpy, img, &shminfo, used_shm);
        return NULL;
    }

    uint32_t *src_pixels = (uint32_t *)img->data;
    int src_stride = img->bytes_per_line / 4;

    for (int y = 0; y < sh; y++) {
        int sy = y * scale;
        if (sy >= height) sy = height - 1;
        int row_off = sy * src_stride;
        for (int x = 0; x < sw; x++) {
            int sx = x * scale;
            if (sx >= width) sx = width - 1;
            buf1[y * sw + x] = src_pixels[row_off + sx];
        }
    }

    /* Release captured raw X image as early as possible to free memory */
    release_captured_root(dpy, img, &shminfo, used_shm);

    /* 3 passes of horizontal + vertical box blur (radius 6 at 4x scale = ~24px blur) */
    blur_apply_3pass_box(buf1, buf2, sw, sh, 6);
    free(buf2);

    /* Create small cairo surface */
    cairo_surface_t *small_surf = cairo_image_surface_create_for_data(
        (unsigned char *)buf1, CAIRO_FORMAT_RGB24, sw, sh, sw * sizeof(uint32_t)
    );

    /* Create target full-size surface */
    cairo_surface_t *final_surf = cairo_image_surface_create(CAIRO_FORMAT_RGB24, width, height);
    cairo_t *cr = cairo_create(final_surf);

    /* Upscale blurred surface with bilinear interpolation */
    cairo_save(cr);
    cairo_scale(cr, (double)width / (double)sw, (double)height / (double)sh);
    cairo_set_source_surface(cr, small_surf, 0, 0);
    cairo_pattern_set_filter(cairo_get_source(cr), CAIRO_FILTER_BILINEAR);
    cairo_paint(cr);
    cairo_restore(cr);

    /* Clean up small surface and buffer */
    cairo_surface_destroy(small_surf);
    free(buf1);

    /* Apply Catppuccin Mocha dark tint overlay (rgba(30, 30, 46, 0.70)) */
    cairo_set_source_rgba(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B, 0.70);
    cairo_paint(cr);

    cairo_destroy(cr);
    return final_surf;
}
