#ifndef WALLPAPER_H
#define WALLPAPER_H

#include "sys-lock.h"

/*
 * Load wallpaper or solid color background.
 * If custom_path is provided, loads that specific image.
 * If use_rice is true, discovers the current bspwm rice wallpaper.
 * If solid_dark is true, returns a solid Catppuccin Mocha (#1e1e2e) surface.
 * Returns NULL if loading fails.
 */
cairo_surface_t *load_wallpaper_surface(int width, int height,
                                       const char *custom_path,
                                       bool use_rice,
                                       bool solid_dark);

#endif /* WALLPAPER_H */
