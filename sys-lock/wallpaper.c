#include "wallpaper.h"
#include <dirent.h>

static bool is_image_file(const char *name) {
    const char *exts[] = {".jpg", ".jpeg", ".png", ".webp", NULL};
    size_t len = strlen(name);
    for (int i = 0; exts[i]; i++) {
        size_t elen = strlen(exts[i]);
        if (len >= elen && strcasecmp(name + len - elen, exts[i]) == 0) {
            return true;
        }
    }
    return false;
}

static char *find_first_image_in_dir(const char *dir_path) {
    DIR *d = opendir(dir_path);
    if (!d) return NULL;

    struct dirent *ent;
    char *result = NULL;
    while ((ent = readdir(d)) != NULL) {
        if (ent->d_name[0] == '.') continue;
        if (is_image_file(ent->d_name)) {
            size_t full_len = strlen(dir_path) + 1 + strlen(ent->d_name) + 1;
            result = malloc(full_len);
            if (result) {
                snprintf(result, full_len, "%s/%s", dir_path, ent->d_name);
            }
            break;
        }
    }
    closedir(d);
    return result;
}

static char *find_fehbg_image(const char *fehbg_path) {
    FILE *f = fopen(fehbg_path, "r");
    if (!f) return NULL;

    char line[1024];
    char *result = NULL;
    while (fgets(line, sizeof(line), f)) {
        /* Look for single-quoted path: 'path' */
        char *start = strchr(line, '\'');
        if (start) {
            char *end = strchr(start + 1, '\'');
            if (end) {
                *end = '\0';
                result = strdup(start + 1);
                break;
            }
        }
    }
    fclose(f);
    return result;
}

static char *discover_rice_wallpaper(void) {
    const char *home = getenv("HOME");
    if (!home) return NULL;

    char rice_file[MAX_PATH_LEN];
    snprintf(rice_file, sizeof(rice_file), "%s/.config/bspwm/.rice", home);
    FILE *f = fopen(rice_file, "r");
    char rice_name[64] = {0};
    if (f) {
        if (fgets(rice_name, sizeof(rice_name), f)) {
            size_t l = strlen(rice_name);
            while (l > 0 && (rice_name[l - 1] == '\n' || rice_name[l - 1] == '\r' || rice_name[l - 1] == ' ')) {
                rice_name[--l] = '\0';
            }
        }
        fclose(f);
    }

    if (rice_name[0] != '\0') {
        char dir1[MAX_PATH_LEN];
        snprintf(dir1, sizeof(dir1), "%s/.config/bspwm/rices/%s/walls", home, rice_name);
        char *img = find_first_image_in_dir(dir1);
        if (img) return img;

        char dir2[MAX_PATH_LEN];
        snprintf(dir2, sizeof(dir2), "%s/.config/bspwm/rices/%s/Walls", home, rice_name);
        img = find_first_image_in_dir(dir2);
        if (img) return img;
    }

    /* Check ~/.fehbg */
    char fehbg_path[MAX_PATH_LEN];
    snprintf(fehbg_path, sizeof(fehbg_path), "%s/.fehbg", home);
    return find_fehbg_image(fehbg_path);
}

cairo_surface_t *load_wallpaper_surface(int width, int height,
                                       const char *custom_path,
                                       bool use_rice,
                                       bool solid_dark) {
    if (width <= 0 || height <= 0) return NULL;

    cairo_surface_t *surf = cairo_image_surface_create(CAIRO_FORMAT_RGB24, width, height);
    if (!surf) return NULL;

    cairo_t *cr = cairo_create(surf);

    if (solid_dark) {
        cairo_set_source_rgb(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B);
        cairo_paint(cr);
        cairo_destroy(cr);
        return surf;
    }

    char *wall_path = NULL;
    if (custom_path && custom_path[0] != '\0') {
        wall_path = strdup(custom_path);
    } else if (use_rice) {
        wall_path = discover_rice_wallpaper();
    }

    bool loaded = false;
    if (wall_path) {
        GError *err = NULL;
        GdkPixbuf *pixbuf = gdk_pixbuf_new_from_file_at_scale(wall_path, width, height, FALSE, &err);
        if (pixbuf) {
            int pw = gdk_pixbuf_get_width(pixbuf);
            int ph = gdk_pixbuf_get_height(pixbuf);
            int pstride = gdk_pixbuf_get_rowstride(pixbuf);
            int channels = gdk_pixbuf_get_n_channels(pixbuf);
            const guchar *src = gdk_pixbuf_read_pixels(pixbuf);

            cairo_surface_flush(surf);
            unsigned char *dst = cairo_image_surface_get_data(surf);
            int dstride = cairo_image_surface_get_stride(surf);

            for (int y = 0; y < ph && y < height; y++) {
                const guchar *srow = src + (y * pstride);
                uint32_t *drow = (uint32_t *)(dst + (y * dstride));
                for (int x = 0; x < pw && x < width; x++) {
                    uint8_t r = srow[x * channels + 0];
                    uint8_t g = srow[x * channels + 1];
                    uint8_t b = srow[x * channels + 2];
                    drow[x] = 0xff000000 | ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
                }
            }
            cairo_surface_mark_dirty(surf);
            g_object_unref(pixbuf);
            loaded = true;

            /* Dark Catppuccin tint overlay so text remains readable */
            cairo_set_source_rgba(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B, 0.45);
            cairo_paint(cr);
        }
        if (err) g_error_free(err);
        free(wall_path);
    }

    if (!loaded) {
        /* Fallback to solid dark background */
        cairo_set_source_rgb(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B);
        cairo_paint(cr);
    }

    cairo_destroy(cr);
    return surf;
}
