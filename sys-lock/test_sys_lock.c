#include "sys-lock.h"
#include "grab.h"
#include "blur.h"
#include "wallpaper.h"
#include "ui.h"
#include <assert.h>

static int g_tests_passed = 0;
static int g_tests_failed = 0;

#define TEST_ASSERT(cond, msg) do { \
    if (!(cond)) { \
        fprintf(stderr, "[-] FAILED: %s (%s:%d)\n", msg, __FILE__, __LINE__); \
        g_tests_failed++; \
        return; \
    } \
} while (0)

static void test_box_blur_algorithm(void) {
    printf("[*] Running test_box_blur_algorithm...\n");
    int w = 341;
    int h = 192;
    uint32_t *buf1 = malloc(w * h * sizeof(uint32_t));
    uint32_t *buf2 = malloc(w * h * sizeof(uint32_t));
    assert(buf1 && buf2);

    /* Generate synthetic pattern: left half white, right half black */
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            buf1[y * w + x] = (x < w / 2) ? 0xffffffff : 0xff000000;
        }
    }

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    /* Apply 3-pass box blur */
    blur_apply_3pass_box(buf1, buf2, w, h, 6);

    clock_gettime(CLOCK_MONOTONIC, &t1);
    double elapsed_ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;

    printf("    3-pass box blur on %dx%d took: %.2f ms\n", w, h, elapsed_ms);

    /* Execution must be under 20ms */
    TEST_ASSERT(elapsed_ms < 20.0, "Blur performance exceeds 20ms threshold");

    /* Midpoint pixel should now be blurred between white and black (around 0x7f) */
    int mid_x = w / 2;
    uint32_t mid_pixel = buf1[(h / 2) * w + mid_x];
    uint8_t mid_r = (mid_pixel >> 16) & 0xff;
    TEST_ASSERT(mid_r > 30 && mid_r < 225, "Blur boundary smoothing failed");

    free(buf1);
    free(buf2);
    printf("[+] PASSED: test_box_blur_algorithm\n");
    g_tests_passed++;
}

static void test_battery_sysfs(void) {
    printf("[*] Running test_battery_sysfs...\n");
    int capacity = -1;
    char status[64] = {0};

    int ret = ui_get_battery_info(&capacity, status, sizeof(status));
    printf("    Battery check returned: %d, capacity: %d, status: '%s'\n", ret, capacity, status);

    /* If on battery-equipped device (like Portege R700), capacity must be 0-100 */
    if (ret == 0) {
        TEST_ASSERT(capacity >= 0 && capacity <= 100, "Battery capacity out of range");
        TEST_ASSERT(strlen(status) > 0, "Battery status empty");
    }

    printf("[+] PASSED: test_battery_sysfs\n");
    g_tests_passed++;
}

static void test_ui_shake_math(void) {
    printf("[*] Running test_ui_shake_math...\n");
    UiContext ui;
    ScreenGeometry geom = {0, 0, 1366, 768, 683, 384};
    ui_init(&ui, &geom, true);

    TEST_ASSERT(!ui.is_shaking, "UI should not start in shaking state");

    ui_trigger_shake(&ui);
    TEST_ASSERT(ui.is_shaking, "UI should be shaking after trigger");

    double offset = 0.0;
    double now = ui.shake_start_time + 0.10;
    bool active = ui_update_shake(&ui, now, &offset);
    TEST_ASSERT(active, "Shake should be active at t=0.10s");
    TEST_ASSERT(fabs(offset) > 0.001, "Shake offset should be non-zero during animation");

    /* After duration, shake must finish */
    now = ui.shake_start_time + 0.50;
    active = ui_update_shake(&ui, now, &offset);
    TEST_ASSERT(!active, "Shake should expire after duration");
    TEST_ASSERT(!ui.is_shaking, "is_shaking flag must be reset to false");
    TEST_ASSERT(offset == 0.0, "Offset should reset to 0.0");

    printf("[+] PASSED: test_ui_shake_math\n");
    g_tests_passed++;
}

static void test_ui_cairo_rendering(void) {
    printf("[*] Running test_ui_cairo_rendering...\n");
    int w = 1366;
    int h = 768;

    cairo_surface_t *surf = cairo_image_surface_create(CAIRO_FORMAT_RGB24, w, h);
    TEST_ASSERT(surf != NULL, "Failed to create cairo image surface");
    cairo_t *cr = cairo_create(surf);
    TEST_ASSERT(cr != NULL, "Failed to create cairo_t");

    ScreenGeometry geom = {0, 0, w, h, w / 2, h / 2};
    UiContext ui;
    ui_init(&ui, &geom, true);

    double now = 1000.0;

    /* Render IDLE state */
    ui_set_state(&ui, UI_STATE_IDLE, NULL);
    ui_render(&ui, cr, NULL, w, h, now);

    /* Render TYPING state with dots */
    ui_set_pw_length(&ui, 6);
    ui_render(&ui, cr, NULL, w, h, now);

    /* Render VERIFYING state */
    ui_set_state(&ui, UI_STATE_VERIFYING, NULL);
    ui_render(&ui, cr, NULL, w, h, now);

    /* Render AUTH FAILED state */
    ui_set_state(&ui, UI_STATE_AUTH_FAILED, "Authentication Failed");
    ui_render(&ui, cr, NULL, w, h, now);

    /* Render FPRINT MATCH state */
    ui_set_state(&ui, UI_STATE_FPRINT_MATCH, "Fingerprint Recognized");
    ui_render(&ui, cr, NULL, w, h, now);

    cairo_destroy(cr);
    cairo_surface_destroy(surf);

    printf("[+] PASSED: test_ui_cairo_rendering\n");
    g_tests_passed++;
}

static void test_wallpaper_modes(void) {
    printf("[*] Running test_wallpaper_modes...\n");
    int w = 800;
    int h = 600;

    /* Test solid dark mode */
    cairo_surface_t *surf = load_wallpaper_surface(w, h, NULL, false, true);
    TEST_ASSERT(surf != NULL, "Failed to create solid dark surface");
    TEST_ASSERT(cairo_image_surface_get_width(surf) == w, "Surface width mismatch");
    TEST_ASSERT(cairo_image_surface_get_height(surf) == h, "Surface height mismatch");
    cairo_surface_destroy(surf);

    printf("[+] PASSED: test_wallpaper_modes\n");
    g_tests_passed++;
}

static void test_headless_x11_window_and_grab(void) {
    printf("[*] Running test_headless_x11_window_and_grab...\n");
    Display *dpy = XOpenDisplay(NULL);
    if (!dpy) {
        printf("    [SKIP] Cannot open X display (test outside X server)\n");
        return;
    }

    ScreenGeometry geom;
    int ret = grab_get_screen_geometry(dpy, &geom);
    TEST_ASSERT(ret == 0, "grab_get_screen_geometry failed");
    TEST_ASSERT(geom.width > 0 && geom.height > 0, "Invalid screen geometry");

    int screen = DefaultScreen(dpy);
    Window win = grab_create_lock_window(dpy, screen, &geom);
    TEST_ASSERT(win != None, "Failed to create lock window");

    Cursor cursor = grab_create_blank_cursor(dpy, win);
    TEST_ASSERT(cursor != None, "Failed to create blank cursor");

    ret = grab_inputs(dpy, win, 10, 5000);
    TEST_ASSERT(ret == 0, "grab_inputs failed on test X server");

    grab_release(dpy, win, cursor);
    XCloseDisplay(dpy);

    printf("[+] PASSED: test_headless_x11_window_and_grab\n");
    g_tests_passed++;
}

static void test_cli_flags(void) {
    printf("[*] Running test_cli_flags...\n");
    int ret = system("./sys-lock --version >/dev/null 2>&1");
    TEST_ASSERT(ret == 0, "--version failed");
    ret = system("./sys-lock --help >/dev/null 2>&1");
    TEST_ASSERT(ret == 0, "--help failed");
    ret = system("xvfb-run -a ./sys-lock --test >/dev/null 2>&1");
    TEST_ASSERT(ret == 0, "--test failed");
    printf("[+] PASSED: test_cli_flags\n");
    g_tests_passed++;
}

int main(void) {
    printf("=========================================\n");
    printf("sys-lock Test Suite\n");
    printf("=========================================\n");

    test_box_blur_algorithm();
    test_battery_sysfs();
    test_ui_shake_math();
    test_ui_cairo_rendering();
    test_wallpaper_modes();
    test_headless_x11_window_and_grab();
    test_cli_flags();

    printf("=========================================\n");
    printf("Results: %d Passed, %d Failed\n", g_tests_passed, g_tests_failed);
    printf("=========================================\n");

    return (g_tests_failed == 0) ? 0 : 1;
}
