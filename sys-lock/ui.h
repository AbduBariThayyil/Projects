#ifndef UI_H
#define UI_H

#include "sys-lock.h"
#include "grab.h"

typedef struct {
    UiState state;
    int pw_length;
    char status_text[128];
    bool fprint_available;
    double shake_start_time;
    double shake_duration;
    bool is_shaking;
    int center_x;
    int center_y;
} UiContext;

void ui_init(UiContext *ui, const ScreenGeometry *geom, bool fprint_available);
void ui_set_state(UiContext *ui, UiState state, const char *custom_msg);
void ui_set_pw_length(UiContext *ui, int len);
void ui_trigger_shake(UiContext *ui);
bool ui_update_shake(UiContext *ui, double current_time, double *out_offset_x);
void ui_render(UiContext *ui, cairo_t *cr, cairo_surface_t *bg_surface,
               int win_w, int win_h, double current_time);

/* Sysfs Battery query */
int ui_get_battery_info(int *capacity, char *status_str, size_t status_len);

#endif /* UI_H */
